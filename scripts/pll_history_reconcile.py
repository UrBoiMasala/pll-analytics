"""
Phase 9: score and official-statistic reconciliation, 2022-2026.

For every completed competitive game, reconstructs PLL points from canonical
goal events and compares them against the official final score, then compares
eight official box-score totals against their play-by-play equivalents.

PLL scoring, applied identically in every season:
    1_PT, MU        -> 1 point
    2_PT, MU_2_PT   -> 2 points

Nothing here forces an event total to match an official total. Residuals are
MEASURED and classified; a residual is a fact about the feed, not something to
be tuned away. The one thing that is required to be exact is the final score,
because a game whose goal events do not reproduce its own scoreline cannot
support any possession or value analysis built on top of it.

Writes:
    data/processed/history/historical_reconciliation_report.csv   (per game)
    data/processed/history/historical_reconciliation_season.csv   (per season)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "processed" / "history"
SEASONS = [2022, 2023, 2024, 2025, 2026]

SHOT_TYPE_POINTS = {"1_PT": 1, "MU": 1, "2_PT": 2, "MU_2_PT": 2}

# Official box-score column -> the same quantity counted from the event log.
# `scope` is per-TEAM where the event carries the acting team, and per-GAME
# where the official column counts a shared quantity: PLL's `faceoffs` is the
# number of draws the team CONTESTED, which is the same number for both teams
# in a game, whereas a faceoff EVENT carries a single winning team. Comparing
# those per team is a category error, not a data problem -- it produced a
# spurious "0% exact" in every season including 2026 before this was fixed.
OFFICIAL_VS_PBP = [
    ("goals",        "goals",        "team"),
    ("shots",        "shots",        "team"),
    ("saves",        "saves",        "team"),
    ("faceoffs",     "faceoffs",     "game"),
    ("turnovers",    "turnovers",    "team"),
    ("groundBalls",  "ground_balls", "team"),
    ("numPenalties", "penalties",    "team"),
]

# `assists` is deliberately NOT compared. The feed's shotAssistId is a pre-shot
# pass indicator, not a confirmed assist, and an unpopulated value is not a
# negative assertion; Phases 6-8 use it nowhere. Official assists are reliable
# and are carried straight through. There is no event-log quantity to compare
# them against, so reporting a residual would invent a disagreement.


def load_season(year):
    D = REPO_ROOT / "data" / "processed" / str(year)
    g = pd.read_csv(D / "games.csv")
    e = pd.read_csv(D / "events.csv", low_memory=False,
                    dtype={"player_id": str, "team_id": str, "event_id": str,
                           "goalie_id": str, "gb_player_id": str,
                           "secondary_player_id": str})
    t = pd.read_csv(D / "team_game_stats.csv")
    el = g[g["is_completed"] & g["include_in_league_analytics"] & ~g["is_all_star"]]
    return el, e, t


def pbp_team_counts(ev):
    """Count each quantity from the cleaned event log, per (game, team)."""
    ev = ev.copy()
    ev["is2"] = ev["shot_type"].map(SHOT_TYPE_POINTS).fillna(0).astype(int)
    out = []
    for (gid, tid), sub in ev.groupby(["game_id", "team_id"], dropna=True):
        shots = sub[sub["event_type"].isin(["shot", "goal"])
                    & sub["shot_outcome"].notna()]
        goals = shots[shots["is_valid_goal"] == True]  # noqa: E712
        out.append({
            "game_id": gid, "team_id": tid,
            # a save is credited to the DEFENDING team, so it is counted from
            # the shooting team's saved shots and re-attributed below
            "pbp_shots_saved_against_opponent": int((shots["shot_outcome"] == "saved").sum()),
            "pbp_points": int(goals["shot_type"].map(SHOT_TYPE_POINTS)
                              .fillna(1).sum()),
            "pbp_goals": len(goals),
            "pbp_shots": len(shots),
            "pbp_faceoffs": int((sub["event_type"] == "faceoff").sum()),
            "pbp_turnovers": int((sub["event_type"] == "turnover").sum()),
            "pbp_ground_balls": int((sub["event_type"] == "groundball").sum()),
            "pbp_penalties": int((sub["event_type"] == "penalty").sum()),
        })
    return pd.DataFrame(out)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    game_rows, season_rows = [], []

    for year in SEASONS:
        el, ev, tgs = load_season(year)
        ids = set(el["game_id"])
        ev = ev[ev["game_id"].isin(ids) & (ev["is_analysis_eligible_event"] == True)]  # noqa: E712
        counts = pbp_team_counts(ev)
        cmap = {(r.game_id, r.team_id): r for r in counts.itertuples()}

        for g in el.itertuples():
            for side, tid, official in (("home", g.home_team_id, g.home_score),
                                        ("away", g.away_team_id, g.away_score)):
                c = cmap.get((g.game_id, tid))
                rec = int(c.pbp_points) if c is not None else 0
                game_rows.append({
                    "season": year, "game_id": g.game_id, "game_slug": g.game_slug,
                    "game_type": g.game_type, "side": side, "team_id": tid,
                    "official_score": int(official),
                    "reconstructed_points": rec,
                    "score_residual": rec - int(official),
                    "score_reconciles": rec == int(official),
                    "pbp_goals": int(c.pbp_goals) if c is not None else 0,
                    "pbp_shots": int(c.pbp_shots) if c is not None else 0,
                })

        gr = pd.DataFrame([r for r in game_rows if r["season"] == year])

        # official box score vs play-by-play, per team-game
        tg = tgs[tgs["game_id"].isin(ids)].copy()
        tg["team_id"] = tg["officialId"].astype(str)
        # saves: the opponent's saved shots in the same game
        opp = counts.rename(columns={"team_id": "opp_id"})[
            ["game_id", "opp_id", "pbp_shots_saved_against_opponent"]]
        pair = counts[["game_id", "team_id"]].merge(opp, on="game_id")
        pair = pair[pair["team_id"] != pair["opp_id"]]
        saves = (pair.groupby(["game_id", "team_id"])
                     ["pbp_shots_saved_against_opponent"].sum()
                     .rename("pbp_saves").reset_index())
        counts2 = counts.merge(saves, on=["game_id", "team_id"], how="left")
        # faceoffs are a per-GAME quantity (see OFFICIAL_VS_PBP)
        fo_game = counts.groupby("game_id")["pbp_faceoffs"].sum().rename(
            "pbp_faceoffs_game").reset_index()
        counts2 = counts2.merge(fo_game, on="game_id", how="left")
        m = tg.merge(counts2, on=["game_id", "team_id"], how="left")
        stat_resid = {}
        for off_col, pbp_name, scope in OFFICIAL_VS_PBP:
            pbp_col = ("pbp_faceoffs_game" if scope == "game"
                       else f"pbp_{pbp_name}")
            if off_col not in m.columns or pbp_col not in m.columns:
                stat_resid[off_col] = None
                continue
            d = (m[pbp_col].fillna(0) - m[off_col].fillna(0))
            stat_resid[off_col] = {
                "n_rows": int(d.notna().sum()),
                "n_exact": int((d == 0).sum()),
                "total_official": float(m[off_col].sum()),
                "total_pbp": float(m[pbp_col].sum()),
                "net_residual": float(d.sum()),
                "mean_abs_residual": float(d.abs().mean()),
            }

        season_rows.append({
            "season": year,
            "games": len(el),
            "team_games": len(gr),
            "score_rows_exact": int(gr["score_reconciles"].sum()),
            "score_rows_total": len(gr),
            "score_exact_pct": round(100 * gr["score_reconciles"].mean(), 2),
            "league_points_official": int(gr["official_score"].sum()),
            "league_points_reconstructed": int(gr["reconstructed_points"].sum()),
            "league_points_residual": int(gr["reconstructed_points"].sum()
                                          - gr["official_score"].sum()),
            **{f"{k}_net_residual": (v["net_residual"] if v else None)
               for k, v in stat_resid.items()},
            **{f"{k}_pct_exact": (round(100 * v["n_exact"] / max(v["n_rows"], 1), 1)
                                  if v else None)
               for k, v in stat_resid.items()},
            **{f"{k}_official_total": (v["total_official"] if v else None)
               for k, v in stat_resid.items()},
        })

    gdf = pd.DataFrame(game_rows)
    sdf = pd.DataFrame(season_rows)
    gdf.to_csv(OUT_DIR / "historical_reconciliation_report.csv", index=False)
    sdf.to_csv(OUT_DIR / "historical_reconciliation_season.csv", index=False)

    print("SCORE RECONCILIATION (reconstructed PLL points vs official final score)")
    print(sdf[["season", "games", "team_games", "score_rows_exact",
               "score_exact_pct", "league_points_official",
               "league_points_reconstructed", "league_points_residual"]]
          .to_string(index=False))
    bad = gdf[~gdf["score_reconciles"]]
    print(f"\nTeam-game scorelines that do NOT reconcile exactly: {len(bad)}")
    if len(bad):
        print(bad[["season", "game_slug", "team_id", "official_score",
                   "reconstructed_points", "score_residual"]].to_string(index=False))

    print("\nOFFICIAL BOX SCORE vs PLAY-BY-PLAY (% of team-games agreeing exactly)")
    cols = [f"{c}_pct_exact" for c, _, _ in OFFICIAL_VS_PBP if f"{c}_pct_exact" in sdf]
    print(sdf[["season"] + cols].to_string(index=False))

    # ---- analytics admission ------------------------------------------------
    # A game whose own goal events cannot reproduce its own final score cannot
    # support possession reconstruction or any efficiency metric built on
    # points. That is a MEASURED criterion, not a hand-maintained blocklist: it
    # excludes nothing in 2023-2026 and exactly one game in 2022.
    fail = gdf[~gdf["score_reconciles"]][["season", "game_slug"]].drop_duplicates()
    excl = fail.assign(
        exclusion_rule="score_does_not_reconcile",
        reason=("the game's goal events do not reproduce its official final "
                "score; the feed's score columns move on missed-shot events and "
                "decrease, so every points-denominated quantity in the game is "
                "unreliable"))
    excl.to_csv(OUT_DIR / "historical_analytics_exclusions.csv", index=False)
    print(f"\nAnalytics exclusions written: {len(excl)} game(s)")
    if len(excl):
        print(excl.to_string(index=False))
    return gdf, sdf


if __name__ == "__main__":
    main()
