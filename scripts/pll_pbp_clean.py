"""
PLL play-by-play cleaning / validation rules (Phase 2 hardening).

These rules were derived by comparing raw play-by-play events against the
official PLL box-score endpoints (players/stats, teams/stats) across 6 games
(2026-ev-1, 2026-ev-9, 2026-ev-24, 2026-ev-34, 2026-ev-41,
2026-quarterfinals-1). They operate ONLY on the normalized/processed layer —
raw JSON on disk is never modified.

Exposes `clean(df)` which takes the DataFrame produced by
`pll_pbp_extractor.normalize_play_by_play` (which must include the raw
per-event fields: shot_saved, description, home_score_raw, away_score_raw,
shot_type, event_type, player_id) and returns it with these added columns.
Every added column is a NEW column — nothing in the input is overwritten,
so raw fields (home_score_raw, away_score_raw, description, ...) always
remain available unchanged alongside their cleaned counterparts:

- is_valid_goal, goal_invalid_reason: event_type=='goal' rows only (NaN
  elsewhere). See _validate_goals.
- is_valid_penalty: event_type=='penalty' rows only (NaN elsewhere). See
  _validate_penalties.
- home_score_corrected, away_score_corrected: reconstructed running score
  on every row, trusting only pregame/gameEnd/shot events and *valid*
  goals. home_score_raw/away_score_raw are untouched. See
  _reconstruct_scores.
- shot_outcome: goal / saved / on_goal_no_save / missed / None, on every
  shot/goal row. See _classify_shots.
- is_duplicate_event: general-purpose exact-duplicate flag, every event
  type. is_duplicate_groundball/_turnover/_faceoff/_penalty are the same
  flag filtered to that event type, kept as named columns for backward
  compatibility. See _flag_duplicate_events.
- is_two_point_attempt, is_man_up_shot: booleans derived deterministically
  from shot_type, on every shot/goal row (NaN elsewhere). shot_type itself
  is untouched. See _flag_shot_type_attributes.

No column here renames or discards a raw field — event_type in particular
is never reinterpreted (there is deliberately no "event_type_cleaned";
validity concerns live entirely in the is_valid_*/is_duplicate_* flags).
"""
import pandas as pd

# Point value implied by each shotType tag seen across the 6-game sample.
# MU = man-up 1-point goal, MU_2_PT = man-up 2-point goal (seen in 2026-ev-34).
SHOT_TYPE_POINTS = {"1_PT": 1, "MU": 1, "2_PT": 2, "MU_2_PT": 2}


def _validate_goals(df: pd.DataFrame) -> pd.DataFrame:
    """
    A `goal` event is considered VALID only if ALL of the following hold,
    evaluated against the running score reconstructed so far:
      1. score_delta rule: exactly one side's raw score increases, by an
         amount matching the point value implied by shot_type (1 or 2).
      2. description is non-empty (real goals always carry descriptive text
         such as "GOAL by X." or "PP Goal by X."; the one observed
         mislabeled event had an empty description).
      3. shot_saved is not True (a shot flagged as saved cannot be a goal —
         this is the strongest signal; it caught the one known case where
         eventType=="goal" was actually a saved shot with zero score
         change and an empty description).

    This rule was verified across all 6 sample games: applying it and using
    ONLY validated goals (plus pregame/gameEnd/shot events) to reconstruct
    the running score reproduces the official final score exactly in every
    game, and flags exactly the one known bad event (2026-ev-1,
    marker shot-3004600) with zero false positives elsewhere.
    """
    is_valid = pd.Series(False, index=df.index, dtype=object)
    reason = pd.Series(None, index=df.index, dtype=object)
    running_home = 0
    running_away = 0

    for i, row in df.iterrows():
        et = row["event_type"]
        if et in ("pregame", "gameEnd"):
            running_home, running_away = row["home_score_raw"], row["away_score_raw"]
            continue
        if et == "shot":
            # non-scoring shots never change the score; nothing to validate
            continue
        if et != "goal":
            continue

        dh = row["home_score_raw"] - running_home
        da = row["away_score_raw"] - running_away
        expected = SHOT_TYPE_POINTS.get(row["shot_type"])
        desc_nonempty = isinstance(row["description"], str) and row["description"].strip() != ""
        shot_saved = row.get("shot_saved")

        reasons = []
        valid_delta = expected is not None and (
            (dh > 0 and da == 0 and dh == expected) or (da > 0 and dh == 0 and da == expected)
        )
        if not valid_delta:
            reasons.append(f"score_delta_mismatch(dh={dh},da={da},expected={expected})")
        if not desc_nonempty:
            reasons.append("empty_description")
        if shot_saved is True:
            reasons.append("shot_saved_true")

        if reasons:
            is_valid.at[i] = False
            reason.at[i] = "; ".join(reasons)
        else:
            is_valid.at[i] = True
            running_home, running_away = row["home_score_raw"], row["away_score_raw"]

    df = df.copy()
    df["is_valid_goal"] = is_valid.where(df["event_type"] == "goal")
    df["goal_invalid_reason"] = reason
    return df


def _reconstruct_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build home_score_corrected/away_score_corrected by trusting only:
      - pregame / gameEnd events (always carry the true score, 0-0 / final)
      - shot events (non-scoring; raw score never changes, verified reliable)
      - goal events where is_valid_goal == True

    All other event types (faceoff, groundball, turnover, penalty,
    shotclockexpired) forward-fill from the last trusted value, because the
    PLL API returns a placeholder (observed to equal the eventual final
    score) on those event types rather than the live score.
    """
    df = df.copy()
    trust_always = df["event_type"].isin(["pregame", "gameEnd", "shot"])
    trust_valid_goal = (df["event_type"] == "goal") & (df["is_valid_goal"] == True)  # noqa: E712
    trustworthy = trust_always | trust_valid_goal

    df["home_score_corrected"] = df["home_score_raw"].where(trustworthy).ffill().fillna(0).astype(int)
    df["away_score_corrected"] = df["away_score_raw"].where(trustworthy).ffill().fillna(0).astype(int)
    return df


def _classify_shots(df: pd.DataFrame) -> pd.DataFrame:
    """
    shot_outcome values:
      - "goal"            : event_type=='goal' and is_valid_goal==True
      - "saved"            : event_type=='shot' and shot_saved==True
                              (goalie made a save; description contains
                              "Save by" in 100% of the 6-game sample)
      - "on_goal_no_save"  : event_type=='shot', shot_on_goal==True,
                              shot_saved==False. Observed in ~4% of shots
                              across the sample (15/367) with a plain
                              "Missed shot by X." description and no
                              goalie save credited — most plausibly a shot
                              that hit the pipe/frame while on target. PLL
                              gives no further disambiguation in the feed.
      - "missed"           : event_type=='shot', shot_on_goal==False,
                              shot_saved==False (wide/off-target attempt)
      - a mislabeled "goal" (is_valid_goal==False) is reclassified using the
        same shot_saved/shot_on_goal logic as a regular shot outcome, since
        the evidence shows it was actually a shot, not a score.
    """
    df = df.copy()

    def outcome(row):
        et = row["event_type"]
        if et == "goal":
            if row.get("is_valid_goal") is True:
                return "goal"
            # invalid "goal": treat like a shot using its own detail fields
        elif et != "shot":
            return None

        if row.get("shot_saved") is True:
            return "saved"
        if row.get("shot_on_goal") is True and row.get("shot_saved") is False:
            return "on_goal_no_save"
        if row.get("shot_on_goal") is False and row.get("shot_saved") is False:
            return "missed"
        return None  # no detail info available (shouldn't happen for goal/shot)

    df["shot_outcome"] = df.apply(outcome, axis=1)
    return df


def _flag_duplicate_same_type(df: pd.DataFrame, event_type: str, match_fields: list) -> pd.Series:
    """
    Flags an event as a likely duplicate ONLY when ALL hold against the
    IMMEDIATELY PRECEDING event in the raw stream (any other event type in
    between resets the check — this is strict raw adjacency, not just
    "same event type somewhere nearby"):
      - both events are event_type==`event_type`
      - identical, non-null values on every field in `match_fields`
      - identical period
      - clock (seconds_passed) within 1 second of each other

    This is deliberately conservative: exact-content-match + strict
    adjacency, so two distinct events that merely share a clock or a player
    are never flagged. The first event in a duplicate run is kept
    authoritative (flag False); subsequent ones in the run are flagged
    True. Rows are NEVER dropped — this is a flag only.
    """
    is_dup = pd.Series(False, index=df.index)
    mask = df["event_type"] == event_type

    prev_i = None
    for i in df.index:
        if not mask.loc[i]:
            prev_i = None
            continue
        if prev_i is not None:
            same_fields = all(
                pd.notna(df.at[i, f]) and df.at[i, f] == df.at[prev_i, f]
                for f in match_fields
            )
            same_period = df.at[i, "period"] == df.at[prev_i, "period"]
            clock_diff = abs(df.at[i, "seconds_passed"] - df.at[prev_i, "seconds_passed"])
            if same_fields and same_period and clock_diff <= 1:
                is_dup.at[i] = True
        prev_i = i

    return is_dup.where(mask)


def _flag_duplicate_events(df: pd.DataFrame) -> pd.DataFrame:
    """
    General-purpose duplicate-event detector (Phase 3.5), applied uniformly
    to EVERY event type — not just the 4 types where duplicates were first
    found by hand. Strong-evidence, conservative rule: an event is flagged
    only when it matches the IMMEDIATELY PRECEDING event of the same
    event_type in the raw stream (any other event in between resets the
    check) on ALL of:
      - identical team_id
      - identical top-level `description` (the fullest available content
        signature — it already encodes player name(s), team, and, for
        penalties, duration + reason; verified by hand against the
        field-specific rules previously used per event type and found to
        reproduce them exactly)
      - identical period
      - clock (seconds_passed) within 1 second

    This single rule was checked against all 51 completed 2026 games across
    EVERY event type (including shot, goal, shotclockexpired, pregame,
    gameEnd, which had never been checked directly before) and reproduces
    exactly the counts previously found by the type-specific rules — 22
    turnover pairs, 10 groundball pairs, 3 penalty pairs, 1 faceoff pair —
    with zero new occurrences in any other event type. Never flags two
    distinct events that merely share a clock (multiple legitimate plays
    can share a second); requires exact content match, not proximity alone.

    Produces the general `is_duplicate_event` flag plus, for backward
    compatibility and per-type analysis, `is_duplicate_groundball`,
    `is_duplicate_turnover`, `is_duplicate_faceoff`, `is_duplicate_penalty`
    (each simply `is_duplicate_event` filtered to that event type — kept as
    separate named columns because Phase 3 anomaly documentation and the
    validation pipeline reference them individually). Rows are NEVER
    dropped — flags only.
    """
    df = df.copy()
    is_dup = pd.Series(False, index=df.index)
    for et in df["event_type"].dropna().unique():
        is_dup |= _flag_duplicate_same_type(df, et, ["team_id", "description"]).eq(True)
    df["is_duplicate_event"] = is_dup

    df["is_duplicate_groundball"] = df["is_duplicate_event"].where(df["event_type"] == "groundball")
    df["is_duplicate_turnover"] = df["is_duplicate_event"].where(df["event_type"] == "turnover")
    df["is_duplicate_faceoff"] = df["is_duplicate_event"].where(df["event_type"] == "faceoff")
    df["is_duplicate_penalty"] = df["is_duplicate_event"].where(df["event_type"] == "penalty")
    return df


def _validate_penalties(df: pd.DataFrame) -> pd.DataFrame:
    """
    A `penalty` event is considered VALID if penalty_length_sec is not null.
    Every well-formed penalty in the 6-game sample carries a real duration
    (30 or 60 seconds); one event (2026-ev-9, marker penalty-3012200) had
    penalty_length_sec=None and a near-empty description ("Joey Spallina
    penalty for ."), and excluding it is what makes the pbp penalty count
    match the official box score (3) instead of over-counting (4). Note an
    empty *reason* tag (penalty_description == "") alone is NOT disqualifying
    — 2026-ev-24 has a legitimate penalty with a real 60s length but no
    categorized reason, and it correctly counts as valid.
    """
    df = df.copy()
    is_valid = pd.Series(None, index=df.index, dtype=object)
    pen_mask = df["event_type"] == "penalty"
    is_valid[pen_mask] = df.loc[pen_mask, "penalty_length_sec"].notna()
    df["is_valid_penalty"] = is_valid
    return df


def _flag_shot_type_attributes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derives is_two_point_attempt / is_man_up_shot directly from the raw
    shot_type tag, on every shot/goal row (NaN elsewhere). Deterministic
    mapping, verified against every shot_type value observed across the
    full 2026 season (1_PT, 2_PT, MU, MU_2_PT — no others found):

        1_PT     -> is_two_point_attempt=False, is_man_up_shot=False
        2_PT     -> is_two_point_attempt=True,  is_man_up_shot=False
        MU       -> is_two_point_attempt=False, is_man_up_shot=True
        MU_2_PT  -> is_two_point_attempt=True,  is_man_up_shot=True

    This does not collapse or reinterpret shot_type — it is preserved
    unchanged alongside these two convenience booleans.
    """
    df = df.copy()
    df["is_two_point_attempt"] = df["shot_type"].map(
        lambda s: s in ("2_PT", "MU_2_PT") if pd.notna(s) and s != "" else None
    )
    df["is_man_up_shot"] = df["shot_type"].map(
        lambda s: s in ("MU", "MU_2_PT") if pd.notna(s) and s != "" else None
    )
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = _validate_goals(df)
    df = _reconstruct_scores(df)
    df = _classify_shots(df)
    df = _flag_duplicate_events(df)
    df = _validate_penalties(df)
    df = _flag_shot_type_attributes(df)
    return df
