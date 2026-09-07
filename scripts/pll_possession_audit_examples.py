"""
Phase 4: pulls one concrete real example per required manual-audit category
(A-N) and prints the underlying raw event sequence next to the possession(s)
the state machine produced, with the reasoning. Read-only / diagnostic.
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"


def load():
    poss = pd.read_csv(DATA_DIR / "possessions.csv")
    events = pd.read_csv(
        DATA_DIR / "events.csv", low_memory=False,
        dtype={"player_id": str, "secondary_player_id": str, "team_id": str,
               "goalie_id": str, "gb_player_id": str, "event_id": str},
    )
    elig = events[events["is_analysis_eligible_event"] == True]  # noqa: E712
    return poss, events, elig


def show_window(elig, slug, start_num, end_num, pad=0):
    g = elig[elig["game_slug"] == slug].sort_values("event_number")
    g = g[(g["event_number"] >= start_num - pad) & (g["event_number"] <= end_num + pad)]
    cols = ["event_number", "event_id", "period", "clock", "seconds_passed", "team_id", "event_type", "description", "shot_outcome"]
    print(g[cols].to_string(index=False))


def show_poss(poss, poss_id):
    cols = ["possession_id", "period", "offense_team_id", "defense_team_id", "start_reason", "end_reason",
            "start_event_id", "end_event_id", "duration_seconds", "goals", "points_scored", "is_ambiguous", "is_truncated"]
    row = poss[poss["possession_id"] == poss_id][cols]
    print(row.to_string(index=False))


def label(title):
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)


def main():
    poss, events, elig = load()

    # A: faceoff -> settled offense -> goal
    label("A. faceoff -> settled offense -> goal")
    row = poss[(poss["start_reason"] == "faceoff_win") & (poss["end_reason"] == "goal") & (poss["event_count"] >= 4)].iloc[0]
    show_window(elig, row["game_slug"], row["start_event_number"], row["end_event_number"])
    show_poss(poss, row["possession_id"])

    # B: missed shot -> offensive ground ball -> continued offense
    label("B. missed shot -> offensive ground ball -> continued offense (same team)")
    row = poss[(poss["shot_attempts"] >= 2) & (poss["ground_balls"] >= 1) & (poss["end_reason"] == "goal")].iloc[0]
    show_window(elig, row["game_slug"], row["start_event_number"], row["end_event_number"])
    show_poss(poss, row["possession_id"])

    # C: shot -> defensive ground ball -> possession change
    label("C. shot -> defensive ground ball -> possession change")
    row = poss[(poss["end_reason"] == "defensive_ground_ball") & (poss["shot_attempts"] >= 1)].iloc[0]
    show_window(elig, row["game_slug"], row["start_event_number"], row["end_event_number"] + 1)
    show_poss(poss, row["possession_id"])

    # D: ordinary turnover
    label("D. ordinary turnover")
    row = poss[(poss["end_reason"] == "turnover") & (poss["start_reason"] == "faceoff_win") & (poss["is_ambiguous"] == False)].iloc[0]  # noqa: E712
    show_window(elig, row["game_slug"], row["start_event_number"], row["end_event_number"])
    show_poss(poss, row["possession_id"])

    # E: shot-clock expiration
    label("E. shot-clock expiration")
    row = poss[(poss["end_reason"] == "shot_clock_expiration") & (poss["is_ambiguous"] == False)].iloc[0]
    show_window(elig, row["game_slug"], row["start_event_number"], row["end_event_number"])
    show_poss(poss, row["possession_id"])

    # F: turnover + shotclockexpired redundant sequence, collapsed
    label("F. turnover + shotclockexpired sequence (redundancy collapsed — game 2026-ev-1, shotclockexpired-2100/turnover-2110)")
    g = elig[elig["game_slug"] == "2026-ev-1"].sort_values("event_number")
    win = g[(g["event_number"] >= 5) & (g["event_number"] <= 11)]
    print(win[["event_number", "event_id", "period", "clock", "seconds_passed", "team_id", "event_type", "description"]].to_string(index=False))
    print("Possession that this closes:")
    show_poss(poss, "2026-ev-1__p0002")
    print("Next possession opened (note start_reason references the shot-clock closure, not a second boundary from the redundant turnover):")
    show_poss(poss, "2026-ev-1__p0003")

    # G: penalty during an ongoing possession
    label("G. penalty during an ongoing possession")
    row = poss[poss["possession_id"] == "2026-ev-1__p0017"].iloc[0]
    show_window(elig, row["game_slug"], row["start_event_number"], row["end_event_number"])
    show_poss(poss, row["possession_id"])
    pen = events[(events["game_slug"] == row["game_slug"]) & (events["event_type"] == "penalty")
                 & (events["event_number"] >= row["start_event_number"]) & (events["event_number"] <= row["end_event_number"])]
    print("Penalty event(s) within this possession's event window (not part of the state machine's decisions):")
    print(pen[["event_number", "event_id", "description"]].to_string(index=False))

    # H: man-up possession / man-up goal
    label("H. man-up possession / man-up goal")
    row = poss[(poss["has_man_up_shot"] == True) & (poss["end_reason"] == "goal")].iloc[0]  # noqa: E712
    show_window(elig, row["game_slug"], row["start_event_number"], row["end_event_number"])
    show_poss(poss, row["possession_id"])

    # I: two-point attempt (non-scoring)
    label("I. two-point attempt (non-scoring)")
    row = poss[(poss["has_two_point_attempt"] == True) & (poss["goals"] == 0)].iloc[0]
    show_window(elig, row["game_slug"], row["start_event_number"], row["end_event_number"])
    show_poss(poss, row["possession_id"])

    # J: successful two-point goal
    label("J. successful two-point goal")
    row = poss[(poss["has_two_point_attempt"] == True) & (poss["points_scored"] == 2)].iloc[0]
    show_window(elig, row["game_slug"], row["start_event_number"], row["end_event_number"])
    show_poss(poss, row["possession_id"])

    # K: period ending while possession is still open
    label("K. period ending while possession is still open (truncated)")
    row = poss[(poss["end_reason"] == "period_end")].iloc[0]
    show_window(elig, row["game_slug"], row["start_event_number"], row["end_event_number"] + 2)
    show_poss(poss, row["possession_id"])

    # L: overtime possession
    label("L. overtime possession (period 5)")
    row = poss[poss["period"] == 5].iloc[0]
    show_window(elig, row["game_slug"], row["start_event_number"], row["end_event_number"])
    show_poss(poss, row["possession_id"])
    ot_games = sorted(poss[poss["period"] == 5]["game_slug"].unique())
    print("All OT games in the 2026 season possession dataset:", ot_games)

    # M: unusual loose-ball / ground-ball sequence
    label("M. unusual loose-ball/ground-ball sequence (multiple recoveries within one possession)")
    row = poss[(poss["ground_balls"] >= 3)].sort_values("ground_balls", ascending=False).iloc[0]
    show_window(elig, row["game_slug"], row["start_event_number"], row["end_event_number"])
    show_poss(poss, row["possession_id"])

    # N: ambiguous example
    label("N. event sequence the state machine marks ambiguous")
    row = poss[poss["ambiguous_reason"].astype(str).str.contains("no clean evidence chain", na=False)].iloc[3]
    show_window(elig, row["game_slug"], max(0, row["start_event_number"] - 3), row["end_event_number"] + 1)
    show_poss(poss, row["possession_id"])
    print("Reason:", row["ambiguous_reason"])


if __name__ == "__main__":
    main()
