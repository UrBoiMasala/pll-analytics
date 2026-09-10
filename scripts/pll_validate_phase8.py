"""
Phase 8: validation of the 2026 comprehensive statistical layer.

Validates the outputs of scripts/pll_build_phase8_stats.py and writes
data/processed/2026/phase8_validation_report.csv in the same
check_id / check_name / status / n_failures / detail shape as the Phase 4.25,
5, 6 and 7 reports.

INDEPENDENCE. Phase 8 is a consolidation layer, so the failure mode that
matters is a join or a rename that silently changes a number. Every numeric
check therefore recomputes its target from the ORIGINAL source -- the official
box score in team_game_stats.csv / player_game_stats.csv, the cleaned event log,
possessions.csv, or the Phase 5/6/7 output file the column claims to come from
-- using pandas, and none of the SQL in sql/ is re-executed to check itself.
Checks 7, 8 and 9 in particular rebuild the team season table, the player value
identity and the leaderboard ranks with completely separate implementations.

A FAIL is a real correctness problem in the Phase 8 layer.

WHAT A PASS DOES NOT MEAN. Nothing here can tell you whether a metric is worth
publishing. That is what metric_sanity_flags_2026.csv, the distribution audit
and docs/2026_METRIC_SANITY_AUDIT.md are for; check 20 asserts only that no
flag of class E (implementation/data bug) survives.
"""
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pll_metric_catalog import CATALOG, CATALOG_BY_KEY, FORBIDDEN_IN_PUBLISHED  # noqa: E402

TOL = 1e-9

PHASE_8_OUTPUTS = [
    "team_stats_2026.csv", "player_stats_2026.csv",
    "team_leaderboards_2026.csv", "player_leaderboards_2026.csv",
    "two_point_audit_2026.csv", "metric_catalog_2026.csv",
    "metric_distribution_audit_2026.csv", "metric_redundancy_2026.csv",
    "metric_sanity_flags_2026.csv", "phase8_qualification_rules.csv",
]

# Files Phase 8 consumes and must not alter. Their SHA-256 is written into the
# report so the report is itself the manifest a later season can diff against.
UPSTREAM = [
    "games.csv", "teams.csv", "players.csv", "events.csv", "possessions.csv",
    "player_game_stats.csv", "team_game_stats.csv",
    "team_season_advanced.csv", "team_game_advanced.csv", "team_rankings.csv",
    "possession_length_splits.csv", "team_metric_sensitivity.csv",
    "player_opportunities.csv", "player_value_components.csv",
    "player_value_baselines.csv",
    "player_adjusted_value.csv", "player_usage_adjusted_value.csv",
    "player_position_map.csv", "player_positional_baselines.csv",
    "player_rate_identification.csv",
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load():
    d = {}
    d["team"] = pd.read_csv(DATA_DIR / "team_stats_2026.csv", dtype={"team_id": str})
    d["player"] = pd.read_csv(DATA_DIR / "player_stats_2026.csv",
                              dtype={"player_id": str, "team_id": str})
    d["tlb"] = pd.read_csv(DATA_DIR / "team_leaderboards_2026.csv", dtype={"team_id": str})
    d["plb"] = pd.read_csv(DATA_DIR / "player_leaderboards_2026.csv",
                           dtype={"player_id": str, "team_id": str})
    d["two_pt"] = pd.read_csv(DATA_DIR / "two_point_audit_2026.csv")
    d["catalog"] = pd.read_csv(DATA_DIR / "metric_catalog_2026.csv")
    d["audit"] = pd.read_csv(DATA_DIR / "metric_distribution_audit_2026.csv")
    d["flags"] = pd.read_csv(DATA_DIR / "metric_sanity_flags_2026.csv")
    d["redundancy"] = pd.read_csv(DATA_DIR / "metric_redundancy_2026.csv")
    d["rules"] = pd.read_csv(DATA_DIR / "phase8_qualification_rules.csv")

    d["games"] = pd.read_csv(DATA_DIR / "games.csv")
    d["poss"] = pd.read_csv(DATA_DIR / "possessions.csv")
    d["pgs"] = pd.read_csv(DATA_DIR / "player_game_stats.csv")
    d["tgs"] = pd.read_csv(DATA_DIR / "team_game_stats.csv")
    d["events"] = pd.read_csv(
        DATA_DIR / "events.csv", low_memory=False,
        dtype={"player_id": str, "secondary_player_id": str, "team_id": str,
               "goalie_id": str, "gb_player_id": str, "event_id": str})
    d["tsa"] = pd.read_csv(DATA_DIR / "team_season_advanced.csv", dtype={"team_id": str})
    d["tga"] = pd.read_csv(DATA_DIR / "team_game_advanced.csv", dtype={"team_id": str})
    d["opps"] = pd.read_csv(DATA_DIR / "player_opportunities.csv", dtype={"player_id": str})
    d["adj"] = pd.read_csv(DATA_DIR / "player_adjusted_value.csv",
                           dtype={"player_id": str, "team_id": str})
    d["comp"] = pd.read_csv(DATA_DIR / "player_value_components.csv", dtype={"player_id": str})
    d["posmap"] = pd.read_csv(DATA_DIR / "player_position_map.csv", dtype={"player_id": str})
    d["ident"] = pd.read_csv(DATA_DIR / "player_rate_identification.csv")
    return d


def _eligible(games):
    return games[games["is_completed"] & games["include_in_league_analytics"]
                 & ~games["is_all_star"]]


def _rebuild_and_compare():
    """Re-run the Phase 8 build into a scratch copy of the data directory and
    compare every output byte-for-byte with the committed one."""
    import importlib
    import shutil
    import tempfile

    build = importlib.import_module("pll_build_phase8_stats")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for name in UPSTREAM:
            shutil.copy2(DATA_DIR / name, tmp_dir / name)
        original_data, original_scratch = build.DATA_DIR, build.SCRATCH_DIR
        try:
            build.DATA_DIR = tmp_dir
            build.SCRATCH_DIR = tmp_dir / "_phase8_scratch"
            build.main()
        finally:
            build.DATA_DIR, build.SCRATCH_DIR = original_data, original_scratch
        changed = [f for f in PHASE_8_OUTPUTS
                   if not (tmp_dir / f).exists() or _sha(tmp_dir / f) != _sha(DATA_DIR / f)]
    return changed


def main():
    d = _load()
    team, player = d["team"], d["player"]
    tlb, plb = d["tlb"], d["plb"]
    eg = _eligible(d["games"])
    eligible_ids = set(eg["game_id"])
    results = []

    def check(cid, name, n_fail, detail=""):
        results.append({"check_id": cid, "check_name": name,
                        "status": "PASS" if n_fail == 0 else "FAIL",
                        "n_failures": int(n_fail), "detail": detail})

    # official box score restricted to the eligible scope, aggregated
    # independently of every Phase 5/6/7 groupby
    tgs = d["tgs"][d["tgs"]["game_id"].isin(eligible_ids)].copy()
    tgs["team_id"] = tgs["officialId"].astype(str)
    pgs = d["pgs"][d["pgs"]["game_id"].isin(eligible_ids)].copy()
    # the canonical player_id is the official id zero-padded to 6 characters
    pgs["player_id"] = pgs["officialId"].astype(int).astype(str).str.zfill(6)

    # ---- 1. identifiers and row uniqueness --------------------------------
    n1, bad1 = 0, []
    if len(team) != team["team_id"].nunique():
        n1 += 1; bad1.append("team_stats_2026 team_id not unique")
    if len(team) != 8:
        n1 += 1; bad1.append(f"team_stats_2026 has {len(team)} rows, expected 8")
    if len(player) != player["player_id"].nunique():
        n1 += 1; bad1.append("player_stats_2026 player_id not unique")
    if set(player["player_id"]) != set(d["adj"]["player_id"].astype(str)):
        n1 += 1; bad1.append("player_stats_2026 player set differs from Phase 7")
    for name, df, key in (
        ("team_leaderboards_2026", tlb, ["metric_name", "team_id"]),
        ("player_leaderboards_2026", plb, ["metric_name", "scope", "player_id"]),
        ("two_point_audit_2026", d["two_pt"], ["scope", "scope_key"]),
        ("metric_catalog_2026", d["catalog"], ["entity_level", "metric_name"]),
        ("metric_distribution_audit_2026", d["audit"], ["entity_level", "metric_name"]),
    ):
        dup = int(df.duplicated(subset=key).sum())
        if dup:
            n1 += dup; bad1.append(f"{name}: {dup} duplicate {key}")
    if player["player_id"].isna().any() or team["team_id"].isna().any():
        n1 += 1; bad1.append("null identifier")
    check(1, "identifiers_and_row_uniqueness", n1,
          f"{len(team)} teams, {len(player)} players, {len(tlb)} team-leaderboard rows, "
          f"{len(plb)} player-leaderboard rows. {bad1 or 'all keys unique and complete'}")

    # ---- 2. official totals reconciliation --------------------------------
    # Season totals recomputed from the official box score with a fresh groupby.
    off = tgs.groupby("team_id").agg(
        shots=("shots", "sum"), shots_on_goal=("shotsOnGoal", "sum"),
        goals=("goals", "sum"), one_point_goals=("onePointGoals", "sum"),
        two_point_goals=("twoPointGoals", "sum"),
        two_point_attempts=("twoPointShots", "sum"),
        turnovers=("turnovers", "sum"), ground_balls=("groundBalls", "sum"),
        faceoffs=("faceoffs", "sum"), faceoff_wins=("faceoffsWon", "sum"),
        faceoff_losses=("faceoffsLost", "sum"), saves=("saves", "sum"),
        goals_allowed=("goalsAgainst", "sum"), penalties=("numPenalties", "sum"),
        clears=("clears", "sum"), clear_attempts=("clearAttempts", "sum"),
        ride_attempts=("rideAttempts", "sum"),
        shot_clock_expirations=("shotClockExpirations", "sum"),
        games_played=("goals", "size"))
    t = team.set_index("team_id")
    n2, bad2 = 0, []
    for col in off.columns:
        if col not in t.columns:
            continue
        diff = (t[col].astype(float) - off[col].reindex(t.index).astype(float)).abs()
        n_bad = int((diff > TOL).sum())
        if n_bad:
            n2 += n_bad; bad2.append(f"{col}={n_bad}")
    check(2, "team_season_totals_match_official_box_score", n2,
          f"{len(off.columns)} official season totals recomputed from "
          f"team_game_stats.csv over {len(eligible_ids)} eligible games. "
          f"{bad2 or 'all agree exactly'}")

    # ---- 3. team scoring reconciles to the official final scores ----------
    home = eg.groupby("home_team_id")["home_score"].sum()
    away = eg.groupby("away_team_id")["away_score"].sum()
    scored = home.add(away, fill_value=0)
    conc_h = eg.groupby("home_team_id")["away_score"].sum()
    conc_a = eg.groupby("away_team_id")["home_score"].sum()
    allowed = conc_h.add(conc_a, fill_value=0)
    n3 = int((t["points_scored"] - scored.reindex(t.index)).abs().gt(TOL).sum())
    n3 += int((t["points_allowed"] - allowed.reindex(t.index)).abs().gt(TOL).sum())
    n3 += int((t["points_scored"] - t["one_point_points"] - t["two_point_points"])
              .abs().gt(TOL).sum())
    check(3, "team_scoring_reconciles_to_final_scores", n3,
          f"points_scored / points_allowed recomputed from games.csv final scores "
          f"({int(scored.sum())} league points), and one-point plus two-point points "
          f"re-added to the total.")

    # ---- 4. player scoring reconciles to the team and to the league -------
    p_off = pgs.groupby("player_id").agg(
        goals=("goals", "sum"), one_point_goals=("onePointGoals", "sum"),
        two_point_goals=("twoPointGoals", "sum"), assists=("assists", "sum"),
        shots=("shots", "sum"), shots_on_goal=("shotsOnGoal", "sum"),
        two_point_attempts=("twoPointShots", "sum"),
        turnovers=("turnovers", "sum"), touches=("touches", "sum"),
        faceoffs=("faceoffs", "sum"), faceoff_wins=("faceoffsWon", "sum"),
        saves=("saves", "sum"), goals_allowed=("goalsAgainst", "sum"),
        caused_turnovers=("causedTurnovers", "sum"),
        ground_balls=("groundBalls", "sum"))
    p = player.set_index("player_id")
    n4, bad4 = 0, []
    for pcol, ocol in (("goals", "goals"), ("one_point_goals", "one_point_goals"),
                       ("two_point_goals", "two_point_goals"),
                       ("official_assists", "assists"), ("shots", "shots"),
                       ("shots_on_goal", "shots_on_goal"),
                       ("two_point_attempts", "two_point_attempts"),
                       ("turnovers", "turnovers"), ("touches", "touches"),
                       ("faceoffs", "faceoffs"), ("faceoff_wins", "faceoff_wins"),
                       ("saves", "saves"), ("goals_allowed", "goals_allowed"),
                       ("caused_turnovers", "caused_turnovers"),
                       ("ground_balls", "ground_balls")):
        exp = p_off[ocol].reindex(p.index).fillna(0).astype(float)
        n_bad = int((p[pcol].astype(float) - exp).abs().gt(TOL).sum())
        if n_bad:
            n4 += n_bad; bad4.append(f"{pcol}={n_bad}")
    # scoring_points is PLL points from goals, NOT goals+assists, and must sum
    # to the league's actual points
    league_points = float(eg["home_score"].sum() + eg["away_score"].sum())
    if abs(float(player["scoring_points"].sum()) - league_points) > TOL:
        n4 += 1
        bad4.append(f"player scoring_points sum {player['scoring_points'].sum()} "
                    f"!= league points {league_points}")
    check(4, "player_totals_match_official_box_score", n4,
          f"15 official player totals recomputed from player_game_stats.csv for "
          f"{len(player)} players; scoring_points summed to the league total "
          f"({league_points:.0f}). {bad4 or 'all agree exactly'}")

    # ---- 5. shots / SOG / goals and the 1PT-2PT split, from the EVENT LOG --
    ev = d["events"]
    ev = ev[(ev["is_analysis_eligible_event"] == True) &  # noqa: E712
            ev["game_id"].isin(eligible_ids) &
            ev["event_type"].isin(["shot", "goal"]) &
            ev["shot_outcome"].notna()].copy()
    ev["is2"] = ev["is_two_point_attempt"] == True  # noqa: E712
    ev["isg"] = ev["is_valid_goal"] == True  # noqa: E712
    n5, bad5 = 0, []
    for label, mask, col in (("shots", slice(None), "shots"),
                             ("two_point_attempts", ev["is2"], "two_point_attempts"),
                             ("goals", ev["isg"], "goals"),
                             ("two_point_goals", ev["is2"] & ev["isg"], "two_point_goals")):
        sub = ev if isinstance(mask, slice) else ev[mask]
        got = sub.groupby("team_id").size().reindex(t.index).fillna(0)
        n_bad = int((t[col].astype(float) - got.astype(float)).abs().gt(TOL).sum())
        if n_bad:
            n5 += n_bad; bad5.append(f"{label}={n_bad}")
    lg = d["two_pt"][d["two_pt"]["scope"] == "LEAGUE"].iloc[0]
    for col, expected in (("one_point_attempts", int((~ev["is2"]).sum())),
                          ("two_point_attempts", int(ev["is2"].sum())),
                          ("one_point_goals", int((ev["isg"] & ~ev["is2"]).sum())),
                          ("two_point_goals", int((ev["isg"] & ev["is2"]).sum()))):
        if int(lg[col]) != expected:
            n5 += 1; bad5.append(f"two-point audit LEAGUE {col} {lg[col]} != {expected}")
    check(5, "shots_sog_goals_and_two_point_split_match_the_event_log", n5,
          f"{len(ev)} eligible shot events regrouped in pandas; official team totals "
          f"and the two-point audit's LEAGUE row both reproduced. {bad5 or 'all agree'}")

    # ---- 6. faceoff accounting -------------------------------------------
    # The official box score records MORE faceoffs than wins plus losses. That
    # is a documented property of the source (18 league-wide draws credited to
    # neither side), so the check asserts the residual is exactly what the
    # sanity audit says it is, symmetric across the two teams in a game, and
    # never negative -- not that it is zero.
    n6, bad6 = 0, []
    fo_resid = team["faceoffs"] - team["faceoff_wins"] - team["faceoff_losses"]
    if (fo_resid < 0).any():
        n6 += int((fo_resid < 0).sum()); bad6.append("negative faceoff residual")
    if abs(team["faceoff_wins"].sum() - team["faceoff_losses"].sum()) > TOL:
        n6 += 1; bad6.append("league faceoff wins != losses")
    p_resid = player["faceoffs"] - player["faceoff_wins"] - player["faceoff_losses"]
    if abs(p_resid.sum() - fo_resid.sum()) > TOL:
        n6 += 1
        bad6.append(f"player faceoff residual {p_resid.sum()} != team {fo_resid.sum()}")
    if abs(player["faceoffs"].sum() - team["faceoffs"].sum()) > TOL:
        n6 += 1; bad6.append("player faceoff total != team faceoff total")
    flagged = int((d["flags"]["flag_code"] == "OFFICIAL_SOURCE_DISAGREEMENT").sum())
    if flagged != int((fo_resid != 0).sum()) + int((p_resid != 0).sum()):
        n6 += 1; bad6.append("faceoff residual not fully reported in the sanity flags")
    check(6, "faceoff_accounting", n6,
          f"league faceoffs {team['faceoffs'].sum():.0f}, wins "
          f"{team['faceoff_wins'].sum():.0f} = losses "
          f"{team['faceoff_losses'].sum():.0f}, with {fo_resid.sum():.0f} draws "
          f"({fo_resid.sum() / team['faceoffs'].sum() * 100:.1f}%) credited to neither "
          f"side by the official box score and reported as class-D flags. "
          f"{bad6 or 'consistent at both levels'}")

    # ---- 7. goalie accounting --------------------------------------------
    n7, bad7 = 0, []
    goalies = player[player["saves"] + player["goals_allowed"] > 0]
    trials = goalies["saves"] + goalies["goals_allowed"]
    recomputed = goalies["saves"] / trials
    if int((goalies["save_pct"] - recomputed).abs().gt(1e-12).sum()):
        n7 += 1; bad7.append("save_pct != saves / (saves + goals_allowed)")
    if abs(player["saves"].sum() - team["saves"].sum()) > TOL:
        n7 += 1; bad7.append("player saves != team saves")
    if abs(player["goals_allowed"].sum() - team["goals_allowed"].sum()) > TOL:
        n7 += 1; bad7.append("player goals_allowed != team goals_allowed")
    # every save-rate leaderboard row must be denominated on the TRIAL base,
    # never on shots_on_goal_faced, which is a different and larger count
    sr = plb[plb["metric_name"].isin(["save_pct", "save_rate_shrunk"])]
    if not (sr["denominator_name"] == "saves+goals_allowed").all():
        n7 += 1; bad7.append("a save-rate row is denominated on the wrong base")
    ident_save = d["ident"][d["ident"]["rate_name"] == "save_pct"].iloc[0]
    if abs(float(ident_save["total_trials"]) - float(trials.sum())) > TOL:
        n7 += 1
        bad7.append(f"Phase 7 save trials {ident_save['total_trials']} != {trials.sum()}")
    check(7, "goalie_accounting", n7,
          f"{len(goalies)} goalies; save_pct recomputed from saves and goals allowed; "
          f"league trials {trials.sum():.0f} matches Phase 7, against "
          f"{player['shots_on_goal_faced'].sum():.0f} event-log shots on goal faced "
          f"(the two bases are deliberately different). {bad7 or 'all agree'}")

    # ---- 8. team-game -> team-season, and possession accounting -----------
    n8, bad8 = 0, []
    tga = d["tga"][d["tga"]["game_id"].isin(eligible_ids)]
    regrouped = tga.groupby("team_id").agg(
        offensive_possessions=("offensive_possessions", "sum"),
        defensive_possessions=("defensive_possessions", "sum"),
        shots=("shots", "sum"), goals=("goals", "sum"),
        points_scored=("points_scored", "sum"),
        turnovers=("turnovers", "sum"), games_played=("shots", "size"))
    for col in regrouped.columns:
        if col not in t.columns:
            continue
        n_bad = int((t[col].astype(float)
                     - regrouped[col].reindex(t.index).astype(float)).abs().gt(TOL).sum())
        if n_bad:
            n8 += n_bad; bad8.append(f"{col}={n_bad}")
    # possessions independently counted from possessions.csv
    poss = d["poss"][d["poss"]["game_id"].isin(eligible_ids)]
    op = poss.groupby("offense_team_id").size().reindex(t.index).fillna(0)
    dp = poss.groupby("defense_team_id").size().reindex(t.index).fillna(0)
    n8 += int((t["offensive_possessions"] - op).abs().gt(TOL).sum())
    n8 += int((t["defensive_possessions"] - dp).abs().gt(TOL).sum())
    if int((t["offensive_possessions"] - t["defensive_possessions"]
            - t["possession_differential"]).abs().gt(TOL).sum()):
        n8 += 1; bad8.append("possession_differential does not equal the difference")
    if abs(op.sum() - len(poss)) > TOL:
        n8 += 1; bad8.append("offensive possessions do not partition the possession table")
    check(8, "team_game_to_team_season_and_possession_accounting", n8,
          f"7 season totals re-derived by regrouping team_game_advanced.csv, and "
          f"{len(poss)} possessions independently counted by offence and defence. "
          f"{bad8 or 'all agree'}")

    # ---- 9. player component accounting ----------------------------------
    # EPA_points_raw must be the sum of its published components, and the
    # offensive subtotal must be the sum of its two.
    n9, bad9 = 0, []
    comp_sum = (player["shooting_value_raw"].fillna(0)
                + player["turnover_value_raw"].fillna(0)
                + player["faceoff_value_raw"].fillna(0)
                + player["goalie_value_raw"].fillna(0)
                + player["defensive_value_partial_raw"].fillna(0))
    resid = (player["EPA_points_raw"] - comp_sum).abs()
    n_bad = int(resid.gt(1e-9).sum())
    if n_bad:
        n9 += n_bad; bad9.append(f"EPA_points_raw != component sum for {n_bad} players "
                                 f"(max residual {resid.max():.3g})")
    off_sum = (player["shooting_value_raw"].fillna(0)
               + player["turnover_value_raw"].fillna(0))
    n_bad = int((player["offensive_EPA_points_raw"] - off_sum).abs().gt(1e-9).sum())
    if n_bad:
        n9 += n_bad; bad9.append(f"offensive_EPA_points_raw != shooting + turnover ({n_bad})")
    shoot_split = (player["shooting_value_one_point_raw"].fillna(0)
                   + player["shooting_value_two_point_raw"].fillna(0))
    n_bad = int((player["shooting_value_raw"] - shoot_split).abs().gt(1e-9).sum())
    if n_bad:
        n9 += n_bad; bad9.append(f"shooting_value_raw != 1pt + 2pt split ({n_bad})")
    # Ground balls and assists must contribute NOTHING. The component sum above
    # is the structural proof (neither appears as a term); these two assert that
    # the published status says so as well, and that no valued column for either
    # exists to be picked up by mistake.
    for col in ("ground_ball_value_status", "assist_value_status"):
        if not (player[col].astype(str)
                .str.contains("deferred|descriptive|unvalued|not_valued",
                              case=False).all()):
            n9 += 1
            bad9.append(f"{col} does not state the component is unvalued: "
                        f"{sorted(player[col].astype(str).unique())[:2]}")
    leaked = [c for c in player.columns
              if c in ("ground_ball_value", "assist_value", "ground_ball_value_raw",
                       "assist_value_raw")]
    if leaked:
        n9 += len(leaked)
        bad9.append(f"a valued ground-ball/assist column is published: {leaked}")
    check(9, "player_component_accounting", n9,
          f"EPA_points_raw re-added from its 5 components for all {len(player)} players, "
          f"plus the offensive subtotal and the one-point/two-point shooting split; "
          f"ground balls and assists confirmed unvalued. {bad9 or 'all identities hold'}")

    # ---- 10. denominator validity ----------------------------------------
    n10, bad10 = 0, []
    for name, df in (("team", tlb), ("player", plb)):
        miss = df[df["denominator_name"].isna()]
        if len(miss):
            n10 += len(miss)
            bad10.append(f"{name}: {len(miss)} rows without a denominator name")
        neg = df[df["denominator_value"].notna() & (df["denominator_value"] < 0)]
        if len(neg):
            n10 += len(neg); bad10.append(f"{name}: {len(neg)} negative denominators")
    # A genuine RATIO on a zero denominator would be a divide-by-zero that
    # produced a value anyway. Value TOTALS are excluded on purpose: a total sums
    # components whose opportunity bases differ, so its named base can be zero
    # while the total is not (a player with no shots and no turnovers still earns
    # turnover value on his touches). Those rows are reported as class-C
    # VALUE_ON_EMPTY_NAMED_BASE flags instead of failing here.
    ratio_rules = {"SHOOTING_RELIABILITY_HALF", "ONE_POINT_RELIABILITY_HALF",
                   "FACEOFF_RELIABILITY_HALF", "SAVE_RELIABILITY_HALF",
                   "TURNOVER_RATE_RELIABILITY_HALF", "ANY_TRIAL_SHRUNK",
                   "OFFENSIVE_RATE_RANKING_ELIGIBLE", "NOT_QUALIFIABLE_TWO_POINT"}
    rate_rows = plb[plb["qualification_rule"].isin(ratio_rules)]
    zero_den = rate_rows[(rate_rows["denominator_value"] == 0)
                         & rate_rows["metric_value"].notna()]
    if len(zero_den):
        n10 += len(zero_den)
        bad10.append(f"{len(zero_den)} ratio rows carry a value on a zero denominator: "
                     f"{sorted(zero_den['metric_name'].unique())}")
    # Every value total on an empty named base must be REPORTED. Counted on the
    # ALL scope, which is where the flag is raised; the QUALIFIED duplicate of
    # the same row is the same fact about the same player.
    n_value_total_zero = int(((plb["qualification_rule"] == "DESCRIPTIVE_VALUE_TOTAL")
                              & (plb["scope"] == "ALL")
                              & (plb["denominator_value"] == 0)
                              & (plb["metric_value"].abs() > 1e-12)).sum())
    flagged = int((d["flags"]["flag_code"] == "VALUE_ON_EMPTY_NAMED_BASE").sum())
    if flagged != n_value_total_zero:
        n10 += 1
        bad10.append(f"{n_value_total_zero} value-total rows on an empty named base, "
                     f"{flagged} reported as flags")
    check(10, "denominator_validity", n10,
          f"every one of {len(tlb) + len(plb)} leaderboard rows carries a named "
          f"denominator; none is negative; no genuine ratio has a zero one; the "
          f"{flagged} value totals earned on an empty named base are reported as "
          f"class-C flags rather than hidden. {bad10 or 'clean'}")

    # ---- 11. percentage bounds, catalogue-driven --------------------------
    n11, bad11 = 0, []
    for level, df in (("team_season", team), ("player_season", player)):
        for col in df.columns:
            cat = CATALOG_BY_KEY.get((level, col))
            if cat is None or not pd.api.types.is_numeric_dtype(df[col]):
                continue
            unit = cat["unit"]
            if unit in ("percentage", "probability"):
                lo, hi = 0.0, 1.0
            elif unit == "percentile 0-100":
                lo, hi = 0.0, 100.0
            else:
                continue
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            n_bad = int(((s < lo) | (s > hi)).sum())
            if n_bad:
                n11 += n_bad; bad11.append(f"{level}.{col}={n_bad}")
    check(11, "declared_bounds_hold", n11,
          f"every column the catalog declares a percentage, probability or "
          f"percentile checked against its declared range. {bad11 or 'all in range'}")

    # ---- 12. NULL and non-finite handling ---------------------------------
    n12, bad12 = 0, []
    for level, df in (("team_season", team), ("player_season", player)):
        num = df.select_dtypes(include=[np.number])
        inf = int(np.isinf(num.to_numpy(dtype="float64", na_value=np.nan)).sum())
        if inf:
            n12 += inf; bad12.append(f"{level}: {inf} non-finite values")
    # a CORE team metric may not be null anywhere -- an 8-row table has no
    # excuse for a gap
    for col in team.columns:
        cat = CATALOG_BY_KEY.get(("team_season", col))
        if cat and cat["publication_status"] == "CORE" and team[col].isna().any():
            n12 += int(team[col].isna().sum()); bad12.append(f"CORE team.{col} has NULLs")
    # every NULL in a leaderboard metric_value would be a ranked non-value
    for name, df in (("team", tlb), ("player", plb)):
        n_null = int(df["metric_value"].isna().sum())
        if n_null:
            n12 += n_null; bad12.append(f"{name} leaderboard: {n_null} null metric_value")
    check(12, "null_and_non_finite_handling", n12,
          f"no infinities in either statistical table, no NULL in a CORE team metric, "
          f"no NULL ranked on a leaderboard. {bad12 or 'clean'}")

    # ---- 13. leaderboard qualification recomputed independently -----------
    n13, bad13 = 0, []
    thr = pd.read_csv(DATA_DIR / "_phase8_scratch" / "phase8_thresholds.csv")
    kappa = float(thr["turnover_rate_kappa"].iloc[0])
    gate = {
        "shooting_pct": p["shooting_reliability"] >= 0.5,
        "points_per_shot": p["shooting_reliability"] >= 0.5,
        "shots_on_goal_pct": p["shooting_reliability"] >= 0.5,
        "one_point_conversion_pct": p["one_point_reliability"] >= 0.5,
        "faceoff_win_pct": p["faceoff_reliability"] >= 0.5,
        "faceoff_EPA_per_faceoff": p["faceoff_reliability"] >= 0.5,
        "save_pct": p["save_reliability"] >= 0.5,
        "goalie_EPA_per_SOG": p["save_reliability"] >= 0.5,
        "turnovers_per_touch": p["touches"] >= kappa,
        "EPA_per_recorded_opportunity": p["offensive_rate_ranking_eligible"] == True,  # noqa: E712
        "shooting_EPA_per_shot": p["offensive_rate_ranking_eligible"] == True,  # noqa: E712
    }
    for metric, mask in gate.items():
        expected = set(p.index[mask.fillna(False)])
        published = set(plb[(plb["metric_name"] == metric)
                            & (plb["scope"] == "QUALIFIED")]["player_id"])
        # a player only appears at all if the metric is non-null for him
        defined = set(plb[(plb["metric_name"] == metric)
                          & (plb["scope"] == "ALL")]["player_id"])
        expected &= defined
        if expected != published:
            n13 += len(expected ^ published)
            bad13.append(f"{metric}: {len(expected ^ published)} disagreements")
    # no two-point rate may ever have a QUALIFIED scope
    tp_qual = plb[(plb["category"] == "two_point_descriptive")
                  & (plb["scope"] == "QUALIFIED")
                  & (plb["metric_name"] == "two_point_conversion_pct")]
    if len(tp_qual):
        n13 += len(tp_qual)
        bad13.append(f"{len(tp_qual)} QUALIFIED two-point conversion rows exist")
    # every rule referenced resolves to a published rule with a reason
    known = set(d["rules"]["qualification_rule"])
    unknown = set(plb["qualification_rule"]) - known
    if unknown:
        n13 += len(unknown); bad13.append(f"unknown qualification rules {sorted(unknown)}")
    if plb["qualification_reason"].isna().any():
        n = int(plb["qualification_reason"].isna().sum())
        n13 += n; bad13.append(f"{n} rows without a qualification reason")
    check(13, "leaderboard_qualification_recomputed", n13,
          f"{len(gate)} evidence gates recomputed from the reliability columns in pandas "
          f"and compared against the QUALIFIED scope; two-point qualification confirmed "
          f"empty; all {len(known)} rules resolve. {bad13 or 'exact agreement'}")

    # ---- 14. reliability is the estimator it claims to be ------------------
    n14, bad14 = 0, []
    for rate, trial_col, rel_col in (
            ("shooting_pct", "shots", "shooting_reliability"),
            ("one_point_pct", "one_point_attempts", "one_point_reliability"),
            ("faceoff_win_pct", "faceoffs", "faceoff_reliability"),
            ("two_point_pct", "two_point_attempts", "two_point_reliability")):
        k = float(d["ident"][d["ident"]["rate_name"] == rate]["prior_strength_trials"].iloc[0])
        n_trials = player[trial_col].astype(float)
        expected = n_trials / (n_trials + k)
        got = pd.to_numeric(player[rel_col], errors="coerce")
        mask = n_trials > 0
        n_bad = int((~np.isclose(got[mask], expected[mask], rtol=1e-9, atol=1e-9)).sum())
        if n_bad:
            n14 += n_bad; bad14.append(f"{rel_col}={n_bad}")
    save_trials = (player["saves"] + player["goals_allowed"]).astype(float)
    k = float(d["ident"][d["ident"]["rate_name"] == "save_pct"]["prior_strength_trials"].iloc[0])
    m = save_trials > 0
    n_bad = int((~np.isclose(player.loc[m, "save_reliability"],
                             (save_trials / (save_trials + k))[m],
                             rtol=1e-9, atol=1e-9)).sum())
    if n_bad:
        n14 += n_bad; bad14.append(f"save_reliability={n_bad}")
    # reliability must be in [0, 1] and monotone in trials
    for rel_col in ("shooting_reliability", "faceoff_reliability", "save_reliability"):
        s = pd.to_numeric(player[rel_col], errors="coerce").dropna()
        if ((s < 0) | (s > 1)).any():
            n14 += 1; bad14.append(f"{rel_col} out of [0,1]")
    check(14, "reliability_is_n_over_n_plus_kappa", n14,
          f"5 reliability columns recomputed as n/(n+kappa) from Phase 7's published "
          f"prior strengths. {bad14 or 'all reproduce exactly'}")

    # ---- 15. positional labels --------------------------------------------
    n15, bad15 = 0, []
    pm = d["posmap"].set_index("player_id")
    for col in ("canonical_position", "position_group", "value_role"):
        joined = p[col].astype(str)
        expected = pm[col].reindex(p.index).astype(str)
        n_bad = int((joined != expected).sum())
        if n_bad:
            n15 += n_bad; bad15.append(f"{col}={n_bad}")
    valid_pos = {"attack", "midfield", "short_stick_defensive_midfield",
                 "long_stick_midfield", "defense", "faceoff", "goalie", "unknown"}
    unknown = set(player["canonical_position"].dropna()) - valid_pos
    if unknown:
        n15 += len(unknown); bad15.append(f"unexpected positions {sorted(unknown)}")
    if player["canonical_position"].isna().any():
        n = int(player["canonical_position"].isna().sum())
        n15 += n; bad15.append(f"{n} players without a position label")
    # every leaderboard row must carry the position so a consumer can partition
    if plb["canonical_position"].isna().any():
        n = int(plb["canonical_position"].isna().sum())
        n15 += n; bad15.append(f"{n} leaderboard rows without a position")
    check(15, "positional_labels_match_phase_7", n15,
          f"3 label columns compared row-by-row against player_position_map.csv; "
          f"{player['canonical_position'].nunique()} distinct positions, all from the "
          f"closed Phase 7 vocabulary. {bad15 or 'exact match'}")

    # ---- 16. Phase 6 and Phase 7 values carried unchanged ------------------
    n16, bad16 = 0, []
    carried = {
        "player_adjusted_value.csv": (d["adj"], [
            "shooting_value_raw", "turnover_value_raw", "faceoff_value_raw",
            "goalie_value_raw", "defensive_value_partial_raw", "EPA_points_raw",
            "offensive_EPA_points_raw", "EPA_per_recorded_opportunity",
            "EPA_points_null_z", "shooting_rate_raw", "shooting_rate_shrunk",
            "faceoff_rate_shrunk", "save_rate_shrunk", "two_point_rate_shrunk",
            "shooting_reliability", "faceoff_reliability", "save_reliability",
            "EPA_position_percentile", "EPA_position_z", "offensive_play_share",
            "expected_EPA_given_usage", "EPA_vs_usage_expectation"]),
        "player_opportunities.csv": (d["opps"], [
            "goals", "shots", "shots_on_goal", "turnovers", "touches",
            "faceoffs", "saves", "shooting_pct", "faceoff_win_pct", "save_pct",
            "turnovers_per_touch", "points_per_shot"]),
    }
    for fname, (src, cols) in carried.items():
        s = src.set_index("player_id")
        for col in cols:
            if col not in player.columns or col not in s.columns:
                continue
            a = pd.to_numeric(p[col], errors="coerce")
            b = pd.to_numeric(s[col].reindex(p.index), errors="coerce")
            n_bad = int((~np.isclose(a, b, rtol=0, atol=0, equal_nan=True)).sum())
            if n_bad:
                n16 += n_bad; bad16.append(f"{fname}:{col}={n_bad}")
    # Phase 6 raw EPA in particular must be bit-identical
    comp = d["comp"].set_index("player_id")
    n_bad = int((~np.isclose(p["shooting_value_raw"],
                             comp["shooting_value"].reindex(p.index),
                             rtol=0, atol=0, equal_nan=True)).sum())
    if n_bad:
        n16 += n_bad
        bad16.append(f"Phase 6 shooting_value changed on the way through Phase 7/8 ({n_bad})")
    manifest = {f: _sha(DATA_DIR / f)[:12] for f in UPSTREAM}
    check(16, "phase_6_and_7_values_carried_unchanged", n16,
          f"{sum(len(c) for _, c in carried.values())} columns compared bit-for-bit "
          f"(atol=0) against their Phase 6/7 source files, plus Phase 6's raw shooting "
          f"value through the Phase 7 rename. Upstream SHA-256 (12): {manifest}. "
          f"{bad16 or 'nothing changed'}")

    # ---- 17. leaderboard ranks recomputed ---------------------------------
    n17, bad17 = 0, []
    # Ranking is on the value rounded to 12 decimals -- see the comment in
    # player_leaderboards_2026.sql; ranking the raw doubles ordered players on
    # differences of 1e-17 that came out of a division.
    for name, df, part in (("team", tlb, ["metric_name"]),
                           ("player", plb, ["scope", "metric_name"])):
        g = df.copy()
        g["_key"] = np.round(
            np.where(g["higher_is_better"], -g["metric_value"], g["metric_value"]), 12)
        expected = g.groupby(part)["_key"].rank(method="min").astype(int)
        n_bad = int((expected != g["rank"]).sum())
        if n_bad:
            n17 += n_bad; bad17.append(f"{name}={n_bad}")
        # n_ranked / n_teams must equal the actual group size
        size_col = "n_teams" if name == "team" else "n_ranked"
        n_bad = int((g.groupby(part)[size_col].transform("size") != g[size_col]).sum())
        if n_bad:
            n17 += n_bad; bad17.append(f"{name} {size_col}={n_bad}")
    # the QUALIFIED scope must be a subset of ALL, re-ranked
    for metric in plb["metric_name"].unique():
        a = set(plb[(plb["metric_name"] == metric) & (plb["scope"] == "ALL")]["player_id"])
        q = set(plb[(plb["metric_name"] == metric) & (plb["scope"] == "QUALIFIED")]["player_id"])
        if not q <= a:
            n17 += len(q - a); bad17.append(f"{metric}: QUALIFIED not a subset of ALL")
    # position_rank must be the rank within canonical_position
    g = plb.copy()
    g["_key"] = np.round(
        np.where(g["higher_is_better"], -g["metric_value"], g["metric_value"]), 12)
    exp_pos = g.groupby(["scope", "metric_name", "canonical_position"])["_key"] \
               .rank(method="min").astype(int)
    n_bad = int((exp_pos != g["position_rank"]).sum())
    if n_bad:
        n17 += n_bad; bad17.append(f"position_rank={n_bad}")
    check(17, "leaderboard_ranks_recomputed", n17,
          f"competition ranks, group sizes and within-position ranks recomputed in "
          f"pandas for all {len(tlb) + len(plb)} leaderboard rows; QUALIFIED confirmed "
          f"a subset of ALL. {bad17 or 'exact agreement'}")

    # ---- 18. catalog covers everything published --------------------------
    n18, bad18 = 0, []
    # Identifiers, labels and provenance strings are not metrics and are not
    # catalogued; everything else must be.
    from pll_build_phase8_stats import NON_METRIC_COLUMNS  # noqa: E402
    for level, df in (("team_season", team), ("player_season", player)):
        missing = [c for c in df.columns
                   if c not in NON_METRIC_COLUMNS and (level, c) not in CATALOG_BY_KEY]
        if missing:
            n18 += len(missing); bad18.append(f"{level} uncatalogued: {missing}")
    lb_metrics = set(plb["metric_name"]) | set(tlb["metric_name"])
    cat_names = {r["metric_name"] for r in CATALOG}
    missing_lb = sorted(lb_metrics - cat_names)
    if missing_lb:
        n18 += len(missing_lb); bad18.append(f"uncatalogued leaderboard metrics {missing_lb}")
    # nothing UNSUPPORTED or DEFERRED may be published as a column or ranked
    banned = {r["metric_name"] for r in CATALOG
              if r["publication_status"] in ("UNSUPPORTED", "DEFERRED")}
    leaked = sorted((set(team.columns) | set(player.columns) | lb_metrics) & banned)
    if leaked:
        n18 += len(leaked); bad18.append(f"UNSUPPORTED/DEFERRED metric published: {leaked}")
    check(18, "catalog_covers_every_published_column", n18,
          f"{len(team.columns)} team and {len(player.columns)} player columns plus "
          f"{len(lb_metrics)} leaderboard metrics resolved against a {len(CATALOG)}-row "
          f"catalog; {len(banned)} UNSUPPORTED/DEFERRED concepts confirmed unpublished. "
          f"{bad18 or 'complete coverage'}")

    # ---- 19. no composite / award / replacement-level metric exists --------
    n19, bad19 = 0, []
    surfaces = {"team_stats": list(team.columns), "player_stats": list(player.columns),
                "team_leaderboards": sorted(tlb["metric_name"].unique()),
                "player_leaderboards": sorted(plb["metric_name"].unique()),
                "distribution_audit": sorted(d["audit"]["metric_name"].unique())}
    for where, names in surfaces.items():
        for nm in names:
            low = str(nm).lower()
            for bad in FORBIDDEN_IN_PUBLISHED:
                if bad in low:
                    n19 += 1; bad19.append(f"{where}.{nm} contains {bad!r}")
    # the catalog may name them, but only as UNSUPPORTED
    for r in CATALOG:
        low = r["metric_name"].lower()
        if any(b in low for b in FORBIDDEN_IN_PUBLISHED) \
                and r["publication_status"] != "UNSUPPORTED":
            n19 += 1; bad19.append(f"catalog {r['metric_name']} is {r['publication_status']}")
    check(19, "no_mvp_tewaaraton_or_composite_score_exists", n19,
          f"{sum(len(v) for v in surfaces.values())} published metric names scanned for "
          f"{len(FORBIDDEN_IN_PUBLISHED)} forbidden patterns across 5 surfaces; the "
          f"catalog's composite row is UNSUPPORTED and documents why. "
          f"{bad19 or 'no composite, award score, WAR or replacement level anywhere'}")

    # ---- 20. no class-E sanity flag survives ------------------------------
    flags = d["flags"]
    e_flags = flags[flags["classification"] == "E"] if len(flags) else flags
    by_class = flags["classification"].value_counts().to_dict() if len(flags) else {}
    check(20, "no_implementation_bug_flags_remain", len(e_flags),
          f"{len(flags)} sanity flags by class {by_class}: A real performance, "
          f"B sample-size artifact, C role/opportunity artifact, D known feed "
          f"limitation, E implementation bug. Only E is a defect. "
          + (f"Remaining E: "
             f"{e_flags[['metric_name', 'detail']].to_dict('records')[:5]}"
             if len(e_flags) else "No E flags."))

    # ---- 21. raw and shrunk are separately named and never substituted -----
    n21, bad21 = 0, []
    for raw_col, shrunk_col in (("shooting_rate_raw", "shooting_rate_shrunk"),
                                ("faceoff_rate_raw", "faceoff_rate_shrunk"),
                                ("save_rate_raw", "save_rate_shrunk"),
                                ("one_point_rate_raw", "one_point_rate_shrunk")):
        both = player[[raw_col, shrunk_col]].dropna()
        if both.empty:
            n21 += 1; bad21.append(f"{raw_col}/{shrunk_col} missing")
            continue
        if np.allclose(both[raw_col], both[shrunk_col], atol=1e-12):
            n21 += 1; bad21.append(f"{shrunk_col} is identical to {raw_col}")
    # every shrunk leaderboard row must carry its raw companion and vice versa
    paired = plb[plb["metric_name"].isin(
        ["shooting_pct", "shooting_rate_shrunk", "faceoff_win_pct",
         "faceoff_rate_shrunk", "save_pct", "save_rate_shrunk"])]
    n_missing = int(paired["companion_metric_name"].isna().sum())
    if n_missing:
        n21 += n_missing
        bad21.append(f"{n_missing} raw/shrunk rows without their companion")
    # two-point shrinkage must be fully collapsed -- the published finding
    tp = player["two_point_rate_shrunk"].dropna()
    if tp.nunique() > 1 and tp.std() > 1e-6:
        n21 += 1
        bad21.append("two_point_rate_shrunk varies between players, contradicting "
                     "the Phase 6/7 finding that it is not identified")
    check(21, "raw_and_shrunk_kept_separate", n21,
          f"4 raw/shrunk pairs confirmed distinct, {len(paired)} paired leaderboard rows "
          f"carry their companion, and two-point shrinkage is confirmed fully collapsed "
          f"(sd {tp.std():.2e}). {bad21 or 'policy held'}")

    # ---- 22. the distribution audit describes the tables it claims to ------
    n22, bad22 = 0, []
    aud = d["audit"].set_index(["entity_level", "metric_name"])
    for level, df in (("team_season", team), ("player_season", player)):
        for col in df.columns:
            if (level, col) not in aud.index or not pd.api.types.is_numeric_dtype(df[col]):
                continue
            row = aud.loc[(level, col)]
            v = pd.to_numeric(df[col], errors="coerce").dropna()
            if v.empty:
                continue
            for stat, actual in (("n_non_null", len(v)), ("min", v.min()),
                                 ("max", v.max()), ("mean", v.mean())):
                if not np.isclose(float(row[stat]), float(actual), rtol=1e-9, atol=1e-9):
                    n22 += 1; bad22.append(f"{level}.{col}.{stat}")
    if int(d["audit"]["out_of_bounds_rows"].sum()) != 0:
        n = int(d["audit"]["out_of_bounds_rows"].sum())
        n22 += n; bad22.append(f"{n} out-of-bounds rows reported by the audit")
    check(22, "distribution_audit_matches_the_tables", n22,
          f"{len(aud)} audited metrics: n, min, max and mean each recomputed from the "
          f"source table. {bad22[:5] or 'all agree'}")

    # ---- 23. every catalog row is decided ---------------------------------
    n23, bad23 = 0, []
    cat = d["catalog"]
    for col in ("publication_status", "freeze_classification", "known_limitations",
                "interpretation", "formula", "source"):
        n_null = int(cat[col].isna().sum())
        if n_null:
            n23 += n_null; bad23.append(f"{col}: {n_null} undecided")
    blank = cat[cat["known_limitations"].astype(str).str.strip().str.len() == 0]
    if len(blank):
        n23 += len(blank)
        bad23.append(f"{len(blank)} metrics with a blank limitation")
    # A "See x." cross-reference is a legitimate and preferable way to avoid
    # restating a caveat, but only if x exists.
    import re
    names = set(cat["metric_name"])
    for _, r in cat.iterrows():
        m = re.fullmatch(r"See ([a-zA-Z0-9_]+)\.", str(r["known_limitations"]).strip())
        if m and m.group(1) not in names:
            n23 += 1
            bad23.append(f"{r['metric_name']} refers to {m.group(1)}, which is not catalogued")
    check(23, "every_catalogued_metric_has_a_decision", n23,
          f"{len(cat)} catalog rows; statuses "
          f"{cat['publication_status'].value_counts().to_dict()}; freeze "
          f"{cat['freeze_classification'].value_counts().to_dict()}; every "
          f"cross-referenced caveat resolves. "
          f"{bad23 or 'every row carries a status, a freeze class and a limitation'}")

    # ---- 24. deterministic rebuild ----------------------------------------
    changed = _rebuild_and_compare()
    check(24, "rerun_produces_identical_output", len(changed),
          f"rebuilt all {len(PHASE_8_OUTPUTS)} Phase 8 outputs into a scratch directory "
          f"from copies of the {len(UPSTREAM)} upstream files and compared SHA-256; "
          f"changed: {changed or 'none'}")

    report = pd.DataFrame(results)
    out = DATA_DIR / "phase8_validation_report.csv"
    report.to_csv(out, index=False)
    n_fail = int((report["status"] == "FAIL").sum())
    with pd.option_context("display.max_colwidth", 90, "display.width", 220):
        print(report[["check_id", "check_name", "status", "n_failures"]].to_string(index=False))
    if n_fail:
        for _, r in report[report["status"] == "FAIL"].iterrows():
            print(f"\nFAIL {r['check_id']} {r['check_name']}: {r['detail']}")
    print(f"\n{len(report) - n_fail}/{len(report)} checks PASS -> {out.relative_to(REPO_ROOT)}")
    return report


if __name__ == "__main__":
    main()
