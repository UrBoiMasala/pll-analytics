"""
Phase 4: possession-reconstruction engine.

Builds data/processed/2026/possessions.csv from data/processed/2026/events.csv
via an explicit, deterministic state machine. See POSSESSION_METHODOLOGY.md
for the full rule set and evidence behind every rule below — this docstring
only summarizes.

Scope: only games where games.include_in_league_analytics == True (i.e.
regular season + playoffs, NOT the all-star game) are processed, using only
events.csv rows where is_analysis_eligible_event == True (excludes exact
duplicates and confirmed-invalid goals/penalties). This reuses the existing
Phase 3.5 eligibility definitions rather than inventing a new one. All-star
game events remain fully preserved in events.csv; they are simply not built
into possessions in this phase (see POSSESSION_METHODOLOGY.md).

Core rules (evidence-based, verified against the full 2026 season before
being encoded — see POSSESSION_METHODOLOGY.md §"Evidence base"):

- faceoff  -> starts a possession for the winning team (start_reason=faceoff_win).
- goal     -> ends the scoring team's possession (end_reason=goal); does NOT
              open a new possession for the opponent — that waits for real
              subsequent evidence (normally the next faceoff).
- turnover / shotclockexpired -> ends the committing team's possession, IF
              one is open for them. If no possession is open for that team:
                - if this event's seconds_passed exactly matches the most
                  recent possession-closing event's seconds_passed, it is
                  treated as an informational same-instant companion event
                  (no state change) — this is what correctly collapses the
                  turnover+shotclockexpired redundancy the audit predicted,
                  and also absorbs same-instant "companion turnover" entries
                  PLL logs alongside some goals.
                - otherwise, a transient possession is opened for that team
                  (using normal start-reason inference) and immediately
                  closed by this same event — modeling brief, evidenced
                  control that was never separately confirmed by a
                  faceoff/groundball.
- groundball -> continues the current possession if the recovering team
              already has it; otherwise ends the prior possession
              (end_reason=defensive_ground_ball, if one was open) and starts
              a new one for the recovering team.
- shot     -> never itself ends a possession. If it belongs to the team
              already in possession, it's just added. If it conflicts with
              the tracked state (wrong team, or no possession open), the
              engine treats this as evidence a transition was missed by the
              raw feed, closes/opens accordingly, and flags is_ambiguous.
- penalty  -> no state effect (does not open or close a possession).
- period/game end -> closes any open possession (end_reason=period_end or
              game_end, is_truncated=True). Never carries a possession
              across a period boundary.
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

# Phase 9: season is module state defaulting to 2026. The possession RULES are
# untouched -- they are deliberately not tuned per season, so that historical
# possession distributions are comparable evidence rather than a fitted result.
SEASON = 2026
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"


def set_season(year: int) -> None:
    global SEASON, DATA_DIR
    SEASON = int(year)
    DATA_DIR = REPO_ROOT / "data" / "processed" / str(SEASON)

SHOT_TYPE_POINTS = {"1_PT": 1, "MU": 1, "2_PT": 2, "MU_2_PT": 2}

# Event types that, on their own, never establish or end a possession.
NO_EFFECT_TYPES = {"pregame", "gameEnd", "penalty"}


class Possession:
    """Mutable accumulator for one in-progress or just-closed possession."""

    def __init__(self, game_id, game_slug, period, offense_team, defense_team,
                 start_event, start_reason, is_ambiguous=False, ambiguous_reason=None):
        self.game_id = game_id
        self.game_slug = game_slug
        self.period = period
        self.offense_team = offense_team
        self.defense_team = defense_team
        self.start_event = start_event  # the row (Series) that opened this
        self.start_reason = start_reason
        self.is_ambiguous = is_ambiguous
        self.ambiguous_reasons = [ambiguous_reason] if ambiguous_reason else []
        self.event_numbers = [start_event["event_number"]]
        self.shot_attempts = 0
        self.shots_on_goal = 0
        self.goals = 0
        self.points_scored = 0
        self.turnovers = 0
        self.ground_balls = 0
        self.has_two_point_attempt = False
        self.has_man_up_shot = False
        self.last_event = start_event

    def add(self, row):
        self.event_numbers.append(row["event_number"])
        self.last_event = row

    def add_shot_or_goal(self, row):
        self.add(row)
        if pd.notna(row["shot_outcome"]):
            self.shot_attempts += 1
            if row["shot_outcome"] in ("goal", "saved", "on_goal_no_save"):
                self.shots_on_goal += 1
        if row["event_type"] == "goal" and row["is_valid_goal"] == True:  # noqa: E712
            self.goals += 1
            self.points_scored += SHOT_TYPE_POINTS.get(row["shot_type"], 0)
        if row.get("is_two_point_attempt") == True:  # noqa: E712
            self.has_two_point_attempt = True
        if row.get("is_man_up_shot") == True:  # noqa: E712
            self.has_man_up_shot = True

    def add_groundball_continuation(self, row):
        self.add(row)
        self.ground_balls += 1

    def flag_ambiguous(self, reason):
        self.is_ambiguous = True
        self.ambiguous_reasons.append(reason)

    def finalize(self, end_event, end_reason, is_truncated=False):
        start_ev = self.start_event
        duration = end_event["seconds_passed"] - start_ev["seconds_passed"]
        return {
            "game_id": self.game_id,
            "game_slug": self.game_slug,
            "period": self.period,
            "offense_team_id": self.offense_team,
            "defense_team_id": self.defense_team,
            "start_event_id": start_ev["event_id"],
            "end_event_id": end_event["event_id"],
            "start_event_number": start_ev["event_number"],
            "end_event_number": end_event["event_number"],
            "start_seconds_passed": start_ev["seconds_passed"],
            "end_seconds_passed": end_event["seconds_passed"],
            "duration_seconds": duration,
            "start_reason": self.start_reason,
            "end_reason": end_reason,
            "event_count": len(self.event_numbers),
            "shot_attempts": self.shot_attempts,
            "shots_on_goal": self.shots_on_goal,
            "goals": self.goals,
            "points_scored": self.points_scored,
            "turnovers": self.turnovers,
            "ground_balls": self.ground_balls,
            "has_two_point_attempt": self.has_two_point_attempt,
            "has_man_up_shot": self.has_man_up_shot,
            "is_truncated": is_truncated,
            "is_ambiguous": self.is_ambiguous,
            "ambiguous_reason": "; ".join(self.ambiguous_reasons) if self.ambiguous_reasons else None,
        }


def other_team(row_team, home_id, away_id):
    if row_team == home_id:
        return away_id
    if row_team == away_id:
        return home_id
    return None


def infer_start_reason(pending, opening_team, triggering_type):
    """
    Determine why a NEW possession is starting for `opening_team`, given
    `pending` = {'reason': <end_reason of the most recent close>, 'team':
    <team that possession belonged to>} or None if there's no recent close
    to reason from (e.g., very start of a period).

    Returns (start_reason, is_ambiguous, ambiguous_note).
    """
    if triggering_type == "faceoff":
        return "faceoff_win", False, None

    if pending is None:
        return "other_confirmed_control", True, "no prior closing event in this period to infer start reason from"

    if pending["reason"] == "turnover" and pending["team"] != opening_team:
        return "opponent_turnover", False, None
    if pending["reason"] == "shot_clock_expiration" and pending["team"] != opening_team:
        return "opponent_shot_clock_expiration", False, None
    if pending["reason"] == "goal":
        # Real lacrosse always re-faceoffs after a goal; the raw feed
        # sometimes omits that faceoff event (~3% of goals — see
        # POSSESSION_METHODOLOGY.md). Team attribution is still solid
        # (comes straight from the triggering event's own team_id), but the
        # *expected* establishing evidence is missing, so this is flagged.
        return "other_confirmed_control", True, "expected a faceoff after the prior goal but none was logged (missing-faceoff data gap)"
    if pending["reason"] in ("period_end", "game_end"):
        return "other_confirmed_control", True, "possession opened without a faceoff following a period/game boundary close"
    if pending["reason"] == "defensive_ground_ball" and pending["team"] != opening_team:
        # shouldn't normally reach here (groundball continuations/steals are
        # handled directly), but cover it defensively
        return "other_confirmed_control", True, "opened following a defensive-ground-ball close without direct groundball evidence"

    return "other_confirmed_control", True, f"no clean evidence chain (prior close: {pending['reason']} by {pending['team']})"


def build_possessions_for_game(game_id, game_slug, home_id, away_id, events: pd.DataFrame) -> list:
    possessions = []
    possession_number = 0

    for period, pdf in events.groupby("period", sort=True):
        pdf = pdf.sort_values("event_number").reset_index(drop=True)
        current = None  # type: Possession | None
        pending = None  # {'reason': str, 'team': str, 'seconds_passed': int}

        def close(end_event, end_reason, truncated=False):
            nonlocal current, possession_number, pending
            possession_number += 1
            rec = current.finalize(end_event, end_reason, is_truncated=truncated)
            rec["possession_number"] = possession_number
            possessions.append(rec)
            pending = {"reason": end_reason, "team": current.offense_team, "seconds_passed": end_event["seconds_passed"]}
            current = None

        def open_new(row, offense, defense, start_reason, is_amb, amb_note):
            return Possession(game_id, game_slug, period, offense, defense, row, start_reason,
                               is_ambiguous=is_amb, ambiguous_reason=amb_note)

        for _, row in pdf.iterrows():
            et = row["event_type"]

            if et in NO_EFFECT_TYPES:
                continue

            if et == "faceoff":
                if current is not None:
                    # Faceoff-violation/redraw special case (Phase 4.25 —
                    # see POSSESSION_METHODOLOGY.md "Faceoff redraw
                    # handling"): if the possession about to be closed is
                    # ITSELF nothing but its own opening faceoff (no shot,
                    # turnover, or groundball was ever added — start_reason
                    # is faceoff_win and exactly 1 event total) and this new
                    # faceoff arrives with zero other events in between,
                    # there is no real possession content that went
                    # unlogged — the two faceoffs are back-to-back with
                    # nothing between them. This is a well-evidenced
                    # violation/redraw (e.g. an offsides or too-many-men
                    # call voiding the draw), not an unconfirmed possession
                    # change, so it is closed cleanly rather than flagged
                    # ambiguous. Deliberately narrow: this does NOT cover a
                    # groundball-started possession immediately followed by
                    # a faceoff (weaker evidence — the ball WAS demonstrably
                    # recovered first; see POSSESSION_METHODOLOGY.md for why
                    # that case is left ambiguous).
                    if current.start_reason == "faceoff_win" and len(current.event_numbers) == 1:
                        close(row, "faceoff_violation_redraw", truncated=False)
                    else:
                        current.flag_ambiguous(
                            "faceoff occurred while a previous possession had not been closed by "
                            "goal/turnover/shot-clock (likely an unlogged transition)"
                        )
                        close(row, "ambiguous_control_change", truncated=False)
                offense = row["team_id"]
                defense = other_team(offense, home_id, away_id)
                current = open_new(row, offense, defense, "faceoff_win", False, None)
                continue

            if et == "groundball":
                team = row["team_id"]
                if current is not None and current.offense_team == team:
                    current.add_groundball_continuation(row)
                elif current is not None and current.offense_team != team:
                    close(row, "defensive_ground_ball")
                    defense = other_team(team, home_id, away_id)
                    current = open_new(row, team, defense, "defensive_ground_ball", False, None)
                else:
                    defense = other_team(team, home_id, away_id)
                    sr, amb, note = infer_start_reason(pending, team, "groundball_gap")
                    current = open_new(row, team, defense, sr, amb, note)
                continue

            if et in ("shot", "goal"):
                team = row["team_id"]
                if current is None:
                    defense = other_team(team, home_id, away_id)
                    sr, amb, note = infer_start_reason(pending, team, "shot_gap")
                    current = open_new(row, team, defense, sr, amb, note)
                elif current.offense_team != team:
                    prior_offense = current.offense_team
                    current.flag_ambiguous(f"a {et} arrived for {team} while {prior_offense} was tracked as in possession")
                    close(row, "ambiguous_control_change")
                    defense = other_team(team, home_id, away_id)
                    sr, amb, note = infer_start_reason(pending, team, "shot_gap")
                    current = open_new(row, team, defense, sr, True, note or "possession opened after an unexplained team conflict")

                current.add_shot_or_goal(row)

                if et == "goal" and row["is_valid_goal"] == True:  # noqa: E712
                    close(row, "goal")
                continue

            if et in ("turnover", "shotclockexpired"):
                team = row["team_id"]
                end_reason = "turnover" if et == "turnover" else "shot_clock_expiration"

                if current is not None and current.offense_team == team:
                    if et == "turnover":
                        current.turnovers += 1
                    close(row, end_reason)
                    continue

                # No open possession belongs to this team.
                same_instant_as_last_close = (
                    pending is not None and pending["seconds_passed"] == row["seconds_passed"]
                )
                if current is None and same_instant_as_last_close:
                    # informational companion event (e.g. the turnover
                    # PLL logs alongside the opponent's goal, or the
                    # trailing turnover of a shotclockexpired+turnover
                    # redundant pair) — no state change.
                    continue

                if current is not None and current.offense_team != team:
                    # conflicting state — close what's open (ambiguous),
                    # then this team's transient possession below.
                    prior_offense = current.offense_team
                    current.flag_ambiguous(f"a {et} arrived for {team} while {prior_offense} was tracked as in possession")
                    close(row, "ambiguous_control_change")

                # transient possession: opened and immediately closed by
                # this same event (evidenced control with no separately
                # logged establishing event).
                defense = other_team(team, home_id, away_id)
                sr, amb, note = infer_start_reason(pending, team, "turnover_gap")
                current = open_new(row, team, defense, sr, amb, note)
                if et == "turnover":
                    current.turnovers += 1
                close(row, end_reason)
                continue

        if current is not None:
            last_row = pdf.iloc[-1]
            end_reason = "game_end" if last_row["event_type"] == "gameEnd" else "period_end"
            close(last_row, end_reason, truncated=True)

    return possessions


def main():
    events = pd.read_csv(
        DATA_DIR / "events.csv", low_memory=False,
        dtype={"player_id": str, "secondary_player_id": str, "team_id": str,
               "goalie_id": str, "gb_player_id": str, "event_id": str},
    )
    games = pd.read_csv(DATA_DIR / "games.csv")
    eligible_games = games[games["is_completed"] & games["include_in_league_analytics"]]

    elig_events = events[events["is_analysis_eligible_event"] == True]  # noqa: E712

    all_possessions = []
    for _, game in eligible_games.iterrows():
        slug = game["game_slug"]
        gev = elig_events[elig_events["game_slug"] == slug]
        if len(gev) == 0:
            continue
        possessions = build_possessions_for_game(
            game["game_id"], slug, game["home_team_id"], game["away_team_id"], gev
        )
        all_possessions.extend(possessions)

    df = pd.DataFrame(all_possessions)
    df.insert(0, "possession_id", [f"{r.game_slug}__p{r.possession_number:04d}" for r in df.itertuples()])
    df["is_analysis_eligible"] = True  # by construction — see module docstring

    col_order = [
        "possession_id", "game_id", "game_slug", "possession_number", "period",
        "offense_team_id", "defense_team_id",
        "start_event_id", "end_event_id", "start_event_number", "end_event_number",
        "start_seconds_passed", "end_seconds_passed", "duration_seconds",
        "start_reason", "end_reason", "event_count",
        "shot_attempts", "shots_on_goal", "goals", "points_scored", "turnovers", "ground_balls",
        "has_two_point_attempt", "has_man_up_shot",
        "is_truncated", "is_ambiguous", "ambiguous_reason", "is_analysis_eligible",
    ]
    df = df[col_order]

    out_path = DATA_DIR / "possessions.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} possessions to {out_path.relative_to(REPO_ROOT)}")
    print(f"  games: {df['game_slug'].nunique()}")
    print(f"  ambiguous: {int(df['is_ambiguous'].sum())} ({100*df['is_ambiguous'].mean():.1f}%)")
    print(f"  truncated: {int(df['is_truncated'].sum())}")
    return df


if __name__ == "__main__":
    main()
