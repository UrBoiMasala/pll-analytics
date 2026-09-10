"""
Phase 10 part B: the 2023 possession-denominator anomaly -- investigation and
evidence-bounded repair.

WHAT PHASE 9 FOUND
    2023 carries 97.0 possessions per game against a five-season median of
    89.1, 43.2% flagged-ambiguous possessions, and a large block of goals with
    no faceoff logged after them. Phase 9 concluded that 2023's per-possession
    metrics are not cross-season comparable and stopped there.

WHAT THIS MODULE FOUND, FROM THE RAW EVENTS UP
    The faceoffs are not missing. 2023 logs 26.28 faceoffs per game against
    26.02 in 2026 -- the normal number. What is wrong is their POSITION in the
    event stream.

    `event_number` is the index of the event in the raw feed's `items` array
    (pll_pbp_extractor.normalize_play_by_play), and the possession state
    machine processes events in that order. In 12 games of 2023 (and 4 of
    2024) the feed emits the faceoff that FOLLOWS a goal BEFORE that goal, and
    stamps it with the goal's own clock. Three independent facts identify this
    as a feed ordering defect rather than real play:

      1. `markerId` -- the feed's own monotone sequence number, carried on
         every event and stored as `event_id` -- puts the faceoff AFTER the
         goal. Array order and markerId order disagree on exactly these rows.
      2. The faceoff row names its own ground-ball recoverer in `gbPlayerId`,
         and that recovery is logged as a separate `groundball` event. A
         faceoff and the recovery of that same draw are one moment: in every
         season they share `seconds_passed` exactly (973/973 in 2022,
         948/948 in 2025, 1083/1084 in 2026). On the affected rows the goal
         sits BETWEEN them, which is physically impossible.
      3. Repairing the order makes the goal-to-faceoff interval in 2023 match
         the clean seasons (median 3-5s vs 4-5s in 2025/2026) -- a
         distribution that was never targeted by the repair rule.

    The repair is therefore an ORDER-AND-TIMESTAMP correction of events the
    feed already contains. No event is created, deleted, duplicated or
    re-attributed. No team, player, outcome, shot type or score field is
    touched, so scoring reconciliation is unaffected by construction.

EVIDENCE TAXONOMY
    The repository's existing vocabulary for "how sure are we" is
    PASS / KNOWN_DATA_ISSUE / UNRESOLVED (validation) and
    OBSERVED / DERIVED / MODELED / INFERRED / UNSUPPORTED (metrics). Neither
    fits a per-sequence repair decision, so Phase 10 adds a fourth, narrower
    scale and maps it onto them:

      DIRECT             the feed's own markerId sequence contradicts the array
                         order AND the faceoff's companion ground ball lies on
                         the far side of the goal. The transposition is
                         uniquely implied by the source. -> OBSERVED
      DIRECT_TIMING      the faceoff's companion ground ball is later than the
                         faceoff with nothing of consequence between them: the
                         ORDER is already right, only the timestamp is wrong.
                         -> OBSERVED
      STRONGLY_INFERRED  markerId contradicts the array order, but the faceoff
                         logged no companion ground ball, so the true time is
                         not recoverable and only the order can be argued.
                         -> INFERRED
      WEAKLY_INFERRED    something is odd but the direction of the fix is not
                         implied by any feed field. NEVER repaired.
      DUPLICATE_FACEOFF_EVENT
                         the SAME faceoff appears twice -- once mis-stamped
                         before the goal, once correctly after it. This is a
                         real, separate defect (it dominates 2024) whose repair
                         is de-duplication, not reordering, and de-duplicating
                         touches the canonical event layer. Reported, never
                         repaired here. -> KNOWN_DATA_ISSUE
      UNRESOLVED         a goal separates a faceoff from its own ground ball
                         but markerId agrees with the array order, so the two
                         sources of sequence evidence disagree. NEVER repaired.

    The PRIMARY repair applies DIRECT + DIRECT_TIMING only. That choice is made
    on evidence, not on outcome, and it has a consequence worth stating: 2022,
    2025 and 2026 contain ZERO rows in those two classes, so the frozen 2026
    possession layer is left bit-identical by construction rather than by
    exemption. STRONGLY_INFERRED is carried through the sensitivity analysis so
    its effect is visible and separable.

WHAT THIS MODULE DOES NOT DO
    It does not overwrite `possessions.csv` in any season, and it does not
    rebuild the Phase 5-8 stat layers. The repaired possession layer is
    published ALONGSIDE the frozen one as `possessions_repaired.csv`, with
    every original value recoverable. Adoption into the canonical layer is a
    migration with a measured blast radius (docs/2023_POSSESSION_REPAIR.md
    Section 8) and is deliberately left to a later phase.

Outputs (data/processed/history/ unless noted):
    possession_repair_evidence_2022_2026.csv   every candidate sequence, all seasons
    2023_possession_repair_audit.csv           2023 only, with surrounding event context
    2023_possession_sensitivity.csv            5 repair variants x 2023 metrics
    possession_stats_original_vs_repaired.csv  every season, every requested metric
    possession_team_rank_stability.csv         team rankings, original vs repaired
    data/processed/<year>/possessions_repaired.csv
"""
import sys
import re
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"
SEASONS = [2022, 2023, 2024, 2025, 2026]

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The possession RULES are imported, never reimplemented and never modified.
# A repair that had to change the state machine would not be a data repair.
from pll_build_possessions import build_possessions_for_game  # noqa: E402

# Which evidence classes each variant applies. V2 is the primary repair.
VARIANTS = {
    "V0_original": frozenset(),
    "V1_direct_only": frozenset({"DIRECT"}),
    "V2_direct_and_timing": frozenset({"DIRECT", "DIRECT_TIMING"}),
    "V3_direct_and_strongly_inferred": frozenset({"DIRECT", "STRONGLY_INFERRED"}),
    "V4_all_repairable": frozenset({"DIRECT", "DIRECT_TIMING", "STRONGLY_INFERRED"}),
}
PRIMARY_VARIANT = "V2_direct_and_timing"

EVIDENCE_TO_REPO_LABEL = {
    "DIRECT": "OBSERVED",
    "DIRECT_TIMING": "OBSERVED",
    "STRONGLY_INFERRED": "INFERRED",
    "WEAKLY_INFERRED": "INFERRED",
    "DUPLICATE_FACEOFF_EVENT": "KNOWN_DATA_ISSUE",
    "UNRESOLVED": "UNRESOLVED",
}

# How far ahead a faceoff's own companion ground ball may be looked for. The
# companion is normally the very next event; 8 is generous and bounded so the
# search can never wander into an unrelated later recovery by the same player.
COMPANION_SEARCH_WINDOW = 8


def marker_seq(event_id) -> float:
    """The feed's own monotone sequence number, from the trailing digits of
    markerId ('shot-8900' -> 8900, '9000' -> 9000). 'pregame'/'gameEnd' carry
    no number and return NaN, which disqualifies them from every rule below."""
    m = re.search(r"(\d+)$", str(event_id))
    return float(m.group(1)) if m else np.nan


def load_season(year):
    """Phase 11 note: `events.csv` now HAS the DIRECT/DIRECT_TIMING repair
    canonicalized into `event_number`/`seconds_passed` (see
    `pll_chronology_repair.py`), with the feed's own original values
    preserved alongside as `event_number_raw`/`seconds_passed_raw`. This
    module's whole purpose is to analyze the ORIGINAL feed order, so it
    restores those raw values here -- its own V0_original/V2_direct_and_timing
    comparison keeps working exactly as designed, now sourced from the
    provenance columns instead of a pre-repair file, which is the intended
    use of that provenance (docs/PHASE11_CHRONOLOGY_REPAIR.md)."""
    ev = pd.read_csv(
        PROC / str(year) / "events.csv", low_memory=False,
        dtype={"event_id": str, "gb_player_id": str, "player_id": str,
               "team_id": str, "secondary_player_id": str, "goalie_id": str},
    )
    if "event_number_raw" in ev.columns:
        ev["event_number"] = ev["event_number_raw"]
        ev["seconds_passed"] = ev["seconds_passed_raw"]
    games = pd.read_csv(PROC / str(year) / "games.csv")
    return ev, games


def eligible_events(ev, games):
    """Exactly the event set the production possession builder consumes."""
    el = set(games[games["is_completed"] & games["include_in_league_analytics"]
                   & ~games["is_all_star"]]["game_id"])
    out = ev[(ev["is_analysis_eligible_event"] == True)  # noqa: E712
             & ev["game_id"].isin(el)]
    return out.sort_values(["game_id", "event_number"]).reset_index(drop=True)


def detect_faceoff_order_defects(e: pd.DataFrame) -> pd.DataFrame:
    """Classify every faceoff whose position or timestamp is contradicted by
    another field of the same feed. Returns one row per candidate."""
    e = e.reset_index(drop=True)
    seq = e["event_id"].map(marker_seq).to_numpy()
    et = e["event_type"].to_numpy()
    gid = e["game_id"].to_numpy()
    secs = e["seconds_passed"].to_numpy()
    valid_goal = (e["is_valid_goal"] == True).to_numpy()  # noqa: E712
    pid = e["player_id"].astype(str).to_numpy()
    gbid = e["gb_player_id"].astype(str).to_numpy()
    n = len(e)

    rows = []
    for i in range(n):
        if et[i] != "faceoff":
            continue

        # --- the faceoff's own companion ground-ball recovery --------------
        gb_j = None
        if gbid[i] not in ("nan", "None", ""):
            for k in range(i + 1, min(i + COMPANION_SEARCH_WINDOW, n)):
                if gid[k] != gid[i]:
                    break
                if et[k] == "groundball" and pid[k] == gbid[i]:
                    gb_j = k
                    break

        # --- is the very next event a same-instant valid goal? -------------
        j = i + 1
        goal_next = (j < n and gid[j] == gid[i] and et[j] == "goal"
                     and valid_goal[j] and secs[j] == secs[i])
        seq_inverted = bool(goal_next and np.isfinite(seq[i]) and np.isfinite(seq[j])
                            and seq[i] > seq[j])

        gb_gap = (secs[gb_j] - secs[i]) if gb_j is not None else np.nan
        goal_between = False
        if gb_j is not None and gb_j > i + 1:
            span = slice(i + 1, gb_j)
            goal_between = bool(((et[span] == "goal") & valid_goal[span]).any())

        # Both repairable classes require the scramble to be a SINGLE adjacent
        # displacement -- the goal alone sits between the faceoff and its own
        # ground ball (DIRECT), or nothing does (DIRECT_TIMING). This is not a
        # convenience: a two-event transposition only restores the feed's own
        # markerId order when the displacement is one event wide, and applying
        # it to a wider scramble leaves the faceoff stranded after events that
        # markerId puts before it -- which shows up immediately as a possession
        # of negative duration. Wider scrambles are real and are recorded as
        # UNRESOLVED rather than half-fixed.
        single_displacement = (gb_j is not None and gb_j == j + 1)

        # A DIFFERENT defect, found in 2024 and reported rather than repaired:
        # the feed emits the SAME faceoff twice -- once mis-stamped with the
        # goal's clock before the goal, once correctly after it. The two rows
        # agree on team, winner, loser AND declared ground-ball recoverer
        # (including both being untagged). The correct repair there is
        # de-duplication, not transposition, and de-duplicating an event that
        # Phase 3.5's cleaning admitted is a change to the canonical event
        # layer -- out of scope for Phase 10, which repairs ORDER only; taken
        # up in Phase 11 (`pll_duplicate_faceoff.py`).
        #
        # Phase 11 fix (evidence: docs/PHASE11_DUPLICATE_FACEOFF.md): the
        # original rule searched for the duplicate's companion ground ball
        # via `gb_j` and only checked for a matching-content faceoff BETWEEN
        # the goal and that ground ball. That missed 3 real duplicates (2024)
        # whose draw carries no ground-ball tag at all on EITHER copy, so
        # `gb_j` was never found and they fell through to STRONGLY_INFERRED
        # instead. The duplicate's real copy is always the event immediately
        # following the goal (an intervening event, if any, means the two
        # faceoffs are not adjacent copies of one draw); checking that single
        # position directly -- with FULL content identity including
        # gb_player_id -- catches all 36 confirmed cases with no new false
        # positive (verified: 2023's DIRECT/DIRECT_TIMING/STRONGLY_INFERRED/
        # UNRESOLVED counts, 199/57/26/9, are unchanged by this fix; a naive
        # version that dropped the gb_player_id equality check produced 34
        # false positives in 2023 alone -- two real, distinct, evidence-backed
        # DIRECT faceoffs 10 seconds apart between the same two players are
        # not a duplicate of each other).
        k = j + 1
        duplicate_copy = bool(
            seq_inverted and k < n and gid[k] == gid[i] and et[k] == "faceoff"
            and e.at[k, "team_id"] == e.at[i, "team_id"]
            and str(e.at[k, "player_id"]) == str(e.at[i, "player_id"])
            and str(e.at[k, "secondary_player_id"]) == str(e.at[i, "secondary_player_id"])
            and str(e.at[k, "gb_player_id"]) == str(e.at[i, "gb_player_id"])
            and e.at[k, "period"] == e.at[i, "period"]
        )

        if duplicate_copy:
            klass, action = "DUPLICATE_FACEOFF_EVENT", "none"
        elif seq_inverted and single_displacement and goal_between:
            klass, action = "DIRECT", "transpose_and_retime"
        elif seq_inverted and gb_j is None:
            klass, action = "STRONGLY_INFERRED", "transpose_only"
        elif (not seq_inverted) and gb_j == i + 1 and gb_gap > 0:
            klass, action = "DIRECT_TIMING", "retime_only"
        elif gb_j is not None and gb_gap > 0:
            klass, action = "UNRESOLVED", "none"
        elif seq_inverted:
            klass, action = "WEAKLY_INFERRED", "none"
        else:
            continue

        rows.append({
            "season": int(e.at[i, "season"]) if "season" in e.columns else np.nan,
            "game_slug": e.at[i, "game_slug"],
            "period": int(e.at[i, "period"]),
            "faceoff_event_id": e.at[i, "event_id"],
            "faceoff_array_index": i,
            "faceoff_marker_seq": seq[i],
            "faceoff_seconds_passed": float(secs[i]),
            "faceoff_team_id": e.at[i, "team_id"],
            "goal_event_id": e.at[j, "event_id"] if goal_next else None,
            "goal_array_index": j if goal_next else np.nan,
            "goal_marker_seq": seq[j] if goal_next else np.nan,
            "goal_team_id": e.at[j, "team_id"] if goal_next else None,
            "companion_gb_event_id": e.at[gb_j, "event_id"] if gb_j is not None else None,
            "companion_gb_array_index": gb_j if gb_j is not None else np.nan,
            "companion_gb_seconds_passed": float(secs[gb_j]) if gb_j is not None else np.nan,
            "faceoff_to_companion_gb_gap_seconds": gb_gap,
            "marker_seq_contradicts_array_order": seq_inverted,
            "valid_goal_between_faceoff_and_its_own_ground_ball": goal_between,
            "evidence_class": klass,
            "repo_label": EVIDENCE_TO_REPO_LABEL[klass],
            "repair_action": action,
            "repaired_faceoff_seconds_passed": (
                float(secs[gb_j]) if (gb_j is not None
                                      and action in ("transpose_and_retime", "retime_only"))
                else float(secs[i])),
        })
    return pd.DataFrame(rows)


def apply_repair(e: pd.DataFrame, det: pd.DataFrame, classes) -> pd.DataFrame:
    """Return a copy of `e` with the selected repairs applied.

    Two operations only, both order-preserving elsewhere:
      transpose  -- swap the faceoff and the goal in processing order
      retime     -- set the faceoff's seconds_passed to its companion ground
                    ball's, which is the same real-world instant
    Nothing else in any row changes.
    """
    e = e.reset_index(drop=True).copy()
    # A transposition swaps the two events' own event_numbers. Every other row
    # keeps the number the feed gave it, so an unrepaired season comes back
    # byte-for-byte identical and the repaired rows stay traceable to source.
    # The transposed pairs are always (faceoff, immediately-following goal) and
    # are therefore disjoint -- a goal is never itself a candidate -- so the
    # swaps cannot interact.
    numbers = e["event_number"].to_numpy(dtype=float).copy()
    secs = e["seconds_passed"].to_numpy(dtype=float).copy()
    for r in det.itertuples():
        if r.evidence_class not in classes:
            continue
        i = int(r.faceoff_array_index)
        if r.repair_action in ("transpose_and_retime", "transpose_only"):
            j = int(r.goal_array_index)
            numbers[i], numbers[j] = numbers[j], numbers[i]
        if r.repair_action in ("transpose_and_retime", "retime_only"):
            secs[i] = float(r.companion_gb_seconds_passed)
    e["seconds_passed"] = secs.astype(e["seconds_passed"].dtype)
    e["event_number"] = numbers.astype(e["event_number"].dtype)
    return e.sort_values(["game_id", "event_number"]).reset_index(drop=True)


def build_possessions(e: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Run the UNMODIFIED Phase 4 state machine over an event frame."""
    el = games[games["is_completed"] & games["include_in_league_analytics"]
               & ~games["is_all_star"]]
    out = []
    for _, gm in el.iterrows():
        gev = e[e["game_slug"] == gm["game_slug"]]
        if len(gev) == 0:
            continue
        out.extend(build_possessions_for_game(
            gm["game_id"], gm["game_slug"], gm["home_team_id"],
            gm["away_team_id"], gev))
    df = pd.DataFrame(out)
    df.insert(0, "possession_id",
              [f"{r.game_slug}__p{r.possession_number:04d}" for r in df.itertuples()])
    df["is_analysis_eligible"] = True
    col_order = [
        "possession_id", "game_id", "game_slug", "possession_number", "period",
        "offense_team_id", "defense_team_id",
        "start_event_id", "end_event_id", "start_event_number", "end_event_number",
        "start_seconds_passed", "end_seconds_passed", "duration_seconds",
        "start_reason", "end_reason", "event_count",
        "shot_attempts", "shots_on_goal", "goals", "points_scored", "turnovers",
        "ground_balls", "has_two_point_attempt", "has_man_up_shot",
        "is_truncated", "is_ambiguous", "ambiguous_reason", "is_analysis_eligible",
    ]
    return df[col_order]


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def possession_metrics(poss: pd.DataFrame, games: pd.DataFrame,
                       events: pd.DataFrame) -> dict:
    """Every metric section B of the Phase 10 brief asks to be compared.

    Team possessions per game uses the same convention as
    team_game_advanced.sql: a team's OFFENSIVE possessions in a game.
    """
    ng = poss["game_slug"].nunique()
    n_team_games = 2 * ng
    off = poss.groupby(["game_slug", "offense_team_id"]).agg(
        poss_n=("possession_id", "size"),
        points=("points_scored", "sum"),
        goals=("goals", "sum"),
        shots=("shot_attempts", "sum"),
        turnovers=("turnovers", "sum"),
    ).reset_index()
    dur = poss.loc[~poss["is_truncated"], "duration_seconds"]
    return {
        "n_games": ng,
        "possessions": len(poss),
        "possessions_per_game": len(poss) / ng,
        "team_possessions_per_game": len(poss) / n_team_games,
        "offensive_efficiency_points_per_possession": poss["points_scored"].sum() / len(poss),
        "defensive_efficiency_points_allowed_per_possession": poss["points_scored"].sum() / len(poss),
        "points_per_possession": poss["points_scored"].sum() / len(poss),
        "goals_per_possession": poss["goals"].sum() / len(poss),
        "shots_per_possession": poss["shot_attempts"].sum() / len(poss),
        "possession_ending_turnover_rate": (poss["end_reason"] == "turnover").sum() / len(poss),
        "turnovers_per_possession": poss["turnovers"].sum() / len(poss),
        "possession_ambiguity_rate": float(poss["is_ambiguous"].mean()),
        "truncated_rate": float(poss["is_truncated"].mean()),
        "mean_duration_seconds_untruncated": float(dur.mean()),
        "median_duration_seconds_untruncated": float(dur.median()),
        "total_points_scored": float(poss["points_scored"].sum()),
        "total_goals": float(poss["goals"].sum()),
        "faceoff_win_starts": int((poss["start_reason"] == "faceoff_win").sum()),
        "ambiguous_control_change_ends": int((poss["end_reason"] == "ambiguous_control_change").sum()),
        "other_confirmed_control_starts": int((poss["start_reason"] == "other_confirmed_control").sum()),
        "team_offensive_efficiency_sd": float(
            (off["points"] / off["poss_n"]).groupby(off["offense_team_id"]).mean().std(ddof=0)),
        "goals_followed_by_a_faceoff_pct": goal_faceoff_followup_rate(events),
    }


def goal_faceoff_followup_rate(e: pd.DataFrame) -> float:
    """Share of valid goals whose next state-changing event is a faceoff,
    among goals that are not the last event of their period. This is the
    diagnostic Phase 9 used to size the anomaly; it is reported, never
    optimised against."""
    no_effect = {"pregame", "gameEnd", "penalty"}
    e = e.reset_index(drop=True)
    et = e["event_type"].to_numpy()
    vg = (e["is_valid_goal"] == True).to_numpy()  # noqa: E712
    key = list(zip(e["game_id"], e["period"]))
    n = len(e)
    total = follow = 0
    for i in range(n):
        if not (et[i] == "goal" and vg[i]):
            continue
        j = i + 1
        while j < n and key[j] == key[i] and et[j] in no_effect:
            j += 1
        if j >= n or key[j] != key[i]:
            continue           # period ended: no faceoff is expected
        total += 1
        follow += (et[j] == "faceoff")
    return 100.0 * follow / total if total else np.nan


def residual_by_game(e_before: pd.DataFrame, e_after: pd.DataFrame,
                     season: int) -> pd.DataFrame:
    """What the repair did NOT fix, per game.

    A faceoff follows every goal in real lacrosse, so `expected_faceoffs`
    (goals + one draw to open each period) is a lower bound on how many the
    feed should carry. Where the feed carries fewer, the events are genuinely
    absent and no reordering can recover them: those games stay UNRESOLVED and
    their possession counts remain inflated.
    """
    no_effect = {"pregame", "gameEnd", "penalty"}

    def unfollowed(e):
        e = e.reset_index(drop=True)
        et = e["event_type"].to_numpy()
        vg = (e["is_valid_goal"] == True).to_numpy()  # noqa: E712
        key = list(zip(e["game_id"], e["period"]))
        out = {}
        n = len(e)
        for i in range(n):
            if not (et[i] == "goal" and vg[i]):
                continue
            j = i + 1
            while j < n and key[j] == key[i] and et[j] in no_effect:
                j += 1
            if j >= n or key[j] != key[i]:
                continue
            if et[j] != "faceoff":
                out[e.at[i, "game_slug"]] = out.get(e.at[i, "game_slug"], 0) + 1
        return pd.Series(out, dtype=float)

    before, after = unfollowed(e_before), unfollowed(e_after)
    ea = e_after.assign(
        _goal=((e_after["event_type"] == "goal")
               & (e_after["is_valid_goal"] == True)).astype(int),  # noqa: E712
        _fo=(e_after["event_type"] == "faceoff").astype(int))
    g = ea.groupby("game_slug")
    tab = pd.DataFrame({
        "season": season,
        "goals": g["_goal"].sum(),
        "faceoffs": g["_fo"].sum(),
        "periods": g["period"].nunique(),
    })
    tab["expected_faceoffs_lower_bound"] = tab["goals"] + tab["periods"]
    tab["faceoff_shortfall"] = (tab["expected_faceoffs_lower_bound"]
                                - tab["faceoffs"]).clip(lower=0)
    tab["goals_unfollowed_before_repair"] = before.reindex(tab.index).fillna(0)
    tab["goals_unfollowed_after_repair"] = after.reindex(tab.index).fillna(0)
    tab["resolved_by_repair"] = (tab["goals_unfollowed_before_repair"]
                                 - tab["goals_unfollowed_after_repair"])
    tab["residual_status"] = np.where(
        tab["goals_unfollowed_after_repair"] == 0, "CLEAN",
        np.where(tab["faceoff_shortfall"] > 0,
                 "UNRESOLVED_MISSING_FACEOFF_EVENTS",
                 "UNRESOLVED_OTHER"))
    return tab.reset_index()


def team_offensive_efficiency(poss: pd.DataFrame) -> pd.Series:
    g = poss.groupby("offense_team_id").agg(
        pts=("points_scored", "sum"), n=("possession_id", "size"))
    return (g["pts"] / g["n"]).sort_index()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    HIST.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 250)

    evidence_all, stats_rows, rank_rows, sens_rows = [], [], [], []
    residual_all = []
    audit_2023 = None

    for year in SEASONS:
        ev, games = load_season(year)
        e0 = eligible_events(ev, games)
        e0 = e0.assign(season=year)
        det = detect_faceoff_order_defects(e0)
        if len(det):
            det["season"] = year
            evidence_all.append(det)

        built = {}
        for name, classes in VARIANTS.items():
            src = apply_repair(e0, det, classes) if (classes and len(det)) else e0
            built[name] = (build_possessions(src, games), src)

        orig_poss, orig_ev = built["V0_original"]
        published = pd.read_csv(PROC / str(year) / "possessions.csv")

        # Phase 11 note: `possessions.csv` is now built FROM the canonical
        # DIRECT/DIRECT_TIMING-repaired event order (`pll_chronology_repair.py`,
        # applied inside `pll_build_tables.build_events_table`), so V0 (this
        # script's own from-scratch rebuild on the RAW, pre-repair order --
        # see `load_season`) matches `published` only in the 3 seasons with
        # zero repairable candidates (2022, 2025, 2026). For 2023/2024 this
        # is now the EXPECTED, by-design divergence -- PRIMARY_VARIANT
        # (V2_direct_and_timing) is the one that must match published there
        # (see `test_phase10.py::test_the_repair_is_canonical_in_2023_and_2024`).
        v0_matches = _frames_equal(orig_poss, published)

        for name, (poss, src_ev) in built.items():
            m = possession_metrics(poss, games, src_ev)
            m.update({"season": year, "variant": name,
                      "classes_applied": "+".join(sorted(VARIANTS[name])) or "none",
                      "identical_to_published_possessions": _frames_equal(poss, published),
                      "v0_rebuild_reproduces_published": v0_matches})
            stats_rows.append(m)
            if year == 2023:
                sens_rows.append(m)

        # team ranking movement, original vs the primary repair
        eff0 = team_offensive_efficiency(orig_poss)
        eff1 = team_offensive_efficiency(built[PRIMARY_VARIANT][0])
        both = pd.DataFrame({"original": eff0, "repaired": eff1}).dropna()
        r0 = both["original"].rank(ascending=False)
        r1 = both["repaired"].rank(ascending=False)
        for tm in both.index:
            rank_rows.append({
                "season": year, "team_id": tm,
                "offensive_efficiency_original": both.at[tm, "original"],
                "offensive_efficiency_repaired": both.at[tm, "repaired"],
                "rank_original": float(r0[tm]), "rank_repaired": float(r1[tm]),
                "rank_change": float(r0[tm] - r1[tm]),
                "variant": PRIMARY_VARIANT,
            })

        # A repair may never produce a possession that ends before it starts.
        # This is asserted rather than checked because it is the signature of
        # a transposition applied to a scramble wider than one event, and no
        # such output should ever reach disk.
        neg = int((built[PRIMARY_VARIANT][0]["duration_seconds"] < 0).sum())
        if neg:
            raise AssertionError(
                f"{year}: the repair produced {neg} possession(s) of negative "
                f"duration -- a transposition was applied to a multi-event "
                f"scramble")

        # publish the repaired possession layer next to the frozen one
        built[PRIMARY_VARIANT][0].to_csv(
            PROC / str(year) / "possessions_repaired.csv", index=False)

        residual_all.append(residual_by_game(orig_ev, built[PRIMARY_VARIANT][1], year))

        if year == 2023:
            audit_2023 = _audit_table(e0, det)

        print(f"{year}: candidates {det['evidence_class'].value_counts().to_dict() if len(det) else {}}"
              f"  V0 {len(orig_poss)} -> {PRIMARY_VARIANT} {len(built[PRIMARY_VARIANT][0])}"
              f"  (V0 reproduces published: {v0_matches})")

    ev_df = (pd.concat(evidence_all, ignore_index=True) if evidence_all
             else pd.DataFrame())
    ev_df.to_csv(HIST / "possession_repair_evidence_2022_2026.csv", index=False)
    audit_2023.to_csv(HIST / "2023_possession_repair_audit.csv", index=False)

    stats = pd.DataFrame(stats_rows)
    front = ["season", "variant", "classes_applied"]
    stats = stats[front + [c for c in stats.columns if c not in front]]
    stats.to_csv(HIST / "possession_stats_original_vs_repaired.csv", index=False)

    sens = pd.DataFrame(sens_rows)
    sens = sens[front + [c for c in sens.columns if c not in front]]
    sens.to_csv(HIST / "2023_possession_sensitivity.csv", index=False)

    pd.DataFrame(rank_rows).to_csv(
        HIST / "possession_team_rank_stability.csv", index=False)

    resid = pd.concat(residual_all, ignore_index=True)
    resid.to_csv(HIST / "possession_repair_residual_by_game.csv", index=False)

    _print_summary(ev_df, stats)
    print("\n=== WHAT THE REPAIR DID NOT FIX (goals with no faceoff after them) ===")
    print(resid.groupby("season")[["goals_unfollowed_before_repair",
                                   "goals_unfollowed_after_repair",
                                   "faceoff_shortfall"]].sum().to_string())
    return ev_df, audit_2023, stats, pd.DataFrame(rank_rows), resid


def _frames_equal(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    """Value equality on the shared columns, tolerant of int/float storage."""
    if len(a) != len(b):
        return False
    cols = [c for c in a.columns if c in b.columns]
    x = a[cols].reset_index(drop=True)
    y = b[cols].reset_index(drop=True)
    for c in cols:
        xs, ys = x[c], y[c]
        if pd.api.types.is_numeric_dtype(xs) and pd.api.types.is_numeric_dtype(ys):
            if not np.allclose(xs.to_numpy(dtype=float), ys.to_numpy(dtype=float),
                               equal_nan=True):
                return False
        else:
            # None (in-memory) and NaN (round-tripped through CSV) are the
            # same absent value; normalise before comparing.
            if not (xs.where(xs.notna(), "\x00").astype(str)
                    .equals(ys.where(ys.notna(), "\x00").astype(str))):
                return False
    return True


def _audit_table(e: pd.DataFrame, det: pd.DataFrame) -> pd.DataFrame:
    """One row per 2023 candidate with the full surrounding event context the
    brief asks for: prior possession evidence, the goal, the score change, the
    period/time, what follows, and who next holds the ball."""
    e = e.reset_index(drop=True)
    rows = []
    for r in det.itertuples():
        i = int(r.faceoff_array_index)
        lo, hi = max(0, i - 4), min(len(e), i + 6)
        ctx = e.iloc[lo:hi]
        ctx = ctx[ctx["game_slug"] == r.game_slug]
        prior = ctx[ctx.index < i]
        after = ctx[ctx.index > i]
        rows.append({
            "season": 2023,
            "game_slug": r.game_slug, "period": r.period,
            "faceoff_event_id": r.faceoff_event_id,
            "goal_event_id": r.goal_event_id,
            "companion_gb_event_id": r.companion_gb_event_id,
            "evidence_class": r.evidence_class,
            "repo_label": r.repo_label,
            "repair_action": r.repair_action,
            "marker_seq_faceoff": r.faceoff_marker_seq,
            "marker_seq_goal": r.goal_marker_seq,
            "marker_seq_contradicts_array_order": r.marker_seq_contradicts_array_order,
            "goal_between_faceoff_and_its_ground_ball":
                r.valid_goal_between_faceoff_and_its_own_ground_ball,
            "faceoff_seconds_passed_original": r.faceoff_seconds_passed,
            "faceoff_seconds_passed_repaired": r.repaired_faceoff_seconds_passed,
            "faceoff_team_id": r.faceoff_team_id,
            "goal_team_id": r.goal_team_id,
            "prior_events": "; ".join(
                f"{t}@{s}({tm})" for t, s, tm in zip(
                    prior["event_type"], prior["seconds_passed"], prior["team_id"].fillna("-"))),
            "subsequent_events": "; ".join(
                f"{t}@{s}({tm})" for t, s, tm in zip(
                    after["event_type"], after["seconds_passed"], after["team_id"].fillna("-"))),
            "next_team_control": next(
                (tm for tm, t in zip(after["team_id"], after["event_type"])
                 if pd.notna(tm) and t in ("shot", "goal", "turnover", "groundball")), None),
            "score_home_after_goal": (
                e.at[int(r.goal_array_index), "home_score_corrected"]
                if pd.notna(r.goal_array_index) else np.nan),
            "score_away_after_goal": (
                e.at[int(r.goal_array_index), "away_score_corrected"]
                if pd.notna(r.goal_array_index) else np.nan),
            "repair_applied_in_primary_variant":
                r.evidence_class in VARIANTS[PRIMARY_VARIANT],
        })
    return pd.DataFrame(rows)


def _print_summary(ev_df, stats):
    print("\n=== EVIDENCE CLASSES, 2022-2026 ===")
    if len(ev_df):
        print(pd.crosstab(ev_df["season"], ev_df["evidence_class"]).to_string())
    print("\n=== POSSESSION STATISTICS: original vs repaired ===")
    show = ["season", "variant", "possessions", "possessions_per_game",
            "possession_ambiguity_rate", "points_per_possession",
            "shots_per_possession", "goals_per_possession",
            "median_duration_seconds_untruncated",
            "goals_followed_by_a_faceoff_pct", "total_points_scored",
            "identical_to_published_possessions"]
    print(stats[show].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
