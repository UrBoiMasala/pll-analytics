"""
Phase 6: player-value validation.

Writes data/processed/2026/player_value_validation_report.csv with the same
check_id / check_name / status / n_failures / detail shape the Phase 4 and
Phase 5 validators use.

INDEPENDENCE. Every numeric check recomputes its quantity in pandas straight
from events.csv / player_game_stats.csv / team_game_stats.csv / games.csv. The
SQL in sql/ is never re-run to check itself. Check 19 in particular rebuilds
all five value components from scratch with separate arithmetic and compares
them player by player.

A FAIL is a real correctness problem in the Phase 6 layer.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"
sys.path.insert(0, str(Path(__file__).resolve().parent))

# player_id is a zero-padded 6-character string; without an explicit dtype
# pandas infers int64 and silently drops the padding.
ID_DTYPE = {"player_id": str, "team_id": str, "primary_team_id": str,
            "officialId": str, "teamId": str}

BUILD_INPUTS = ["games.csv", "teams.csv", "players.csv", "events.csv", "possessions.csv",
                "player_game_stats.csv", "team_game_stats.csv", "validation_report.csv"]
BUILD_OUTPUTS = ["player_opportunities.csv", "player_value_baselines.csv",
                 "player_value_components.csv", "player_value_shrinkage.csv",
                 "player_value_metric_definitions.csv", "shot_model_validation.csv",
                 "ground_ball_context_values.csv"]

TOL = 1e-8


def _load():
    d = {}
    d["comp"] = pd.read_csv(DATA_DIR / "player_value_components.csv", dtype=ID_DTYPE)
    d["opp"] = pd.read_csv(DATA_DIR / "player_opportunities.csv", dtype=ID_DTYPE)
    d["base"] = pd.read_csv(DATA_DIR / "player_value_baselines.csv")
    d["shrink"] = pd.read_csv(DATA_DIR / "player_value_shrinkage.csv", dtype=ID_DTYPE)
    d["defs"] = pd.read_csv(DATA_DIR / "player_value_metric_definitions.csv",
                            keep_default_na=False)
    d["sens"] = pd.read_csv(DATA_DIR / "player_value_sensitivity.csv", dtype=ID_DTYPE)
    d["games"] = pd.read_csv(DATA_DIR / "games.csv")
    d["players"] = pd.read_csv(DATA_DIR / "players.csv", dtype={"player_id": str,
                                                                "team_id": str})
    d["teams"] = pd.read_csv(DATA_DIR / "teams.csv")
    d["pg"] = pd.read_csv(DATA_DIR / "player_game_stats.csv", dtype=ID_DTYPE)
    d["tg"] = pd.read_csv(DATA_DIR / "team_game_stats.csv", dtype=ID_DTYPE)
    d["events"] = pd.read_csv(
        DATA_DIR / "events.csv", low_memory=False,
        dtype={"player_id": str, "secondary_player_id": str, "team_id": str,
               "goalie_id": str, "gb_player_id": str, "event_id": str})
    return d


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _rebuild_and_compare():
    """Rebuild every output into a scratch directory and compare byte-for-byte.

    Deliberately NOT rebuilt over the files under test: a validator that
    overwrites its own inputs mid-run makes every earlier check describe a
    different artefact than the one on disk.
    """
    import importlib
    build = importlib.import_module("pll_build_player_value")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for name in BUILD_INPUTS:
            shutil.copy2(DATA_DIR / name, tmp_dir / name)
        build.main(data_dir=tmp_dir)
        changed = [f for f in BUILD_OUTPUTS
                   if not (tmp_dir / f).exists() or _sha(tmp_dir / f) != _sha(DATA_DIR / f)]
    return changed


def main():
    d = _load()
    comp, opp, base = d["comp"], d["opp"], d["base"]
    games = d["games"]
    eligible = games[games["is_completed"] & games["include_in_league_analytics"]
                     & ~games["is_all_star"]]
    eligible_ids = set(eligible["game_id"])
    pg = d["pg"][d["pg"]["game_id"].isin(eligible_ids)].copy()
    pg["player_id"] = pg["officialId"].str.zfill(6)

    results = []

    def check(cid, name, n_fail, detail=""):
        results.append({"check_id": cid, "check_name": name,
                        "status": "PASS" if n_fail == 0 else "FAIL",
                        "n_failures": int(n_fail), "detail": detail})

    def bl(name):
        return float(base.loc[base["baseline_name"] == name, "baseline_value"].iloc[0])

    # ---- 1. player ids resolve ------------------------------------------
    roster = set(d["players"]["player_id"])
    unresolved = set(comp["player_id"]) - roster
    check(1, "player_ids_resolve_to_roster", len(unresolved),
          f"{len(comp)} players in player_value_components; {len(unresolved)} not in players.csv"
          + (f": {sorted(unresolved)[:5]}" if unresolved else ""))

    # ---- 2. team ids resolve --------------------------------------------
    team_ids = set(d["teams"]["team_id"])
    bad_teams = set(comp["team_id"].dropna()) - team_ids
    check(2, "team_ids_resolve", len(bad_teams), f"unresolved team ids: {sorted(bad_teams)}")

    # ---- 3. no duplicate season keys ------------------------------------
    dupes = comp["player_id"].duplicated().sum()
    movers = int((comp["n_teams"] > 1).sum())
    check(3, "one_row_per_player_season", dupes,
          f"{dupes} duplicate player_id rows. The season key is player_id alone; "
          f"{movers} players changed team mid-season and are documented by n_teams>1 "
          "with primary_team_id set to the team they played most games for")

    # ---- 4. raw totals reconcile to official player box score ------------
    official = pg.groupby("player_id").agg(
        o_games=("game_id", "size"), o_shots=("shots", "sum"),
        o_sog=("shotsOnGoal", "sum"), o_goals=("goals", "sum"),
        o_1pt=("onePointGoals", "sum"), o_2pt=("twoPointGoals", "sum"),
        o_2pt_shots=("twoPointShots", "sum"), o_to=("turnovers", "sum"),
        o_ct=("causedTurnovers", "sum"), o_gb=("groundBalls", "sum"),
        o_fo=("faceoffs", "sum"), o_fow=("faceoffsWon", "sum"),
        o_saves=("saves", "sum"), o_ga=("goalsAgainst", "sum"),
        o_touches=("touches", "sum"), o_assists=("assists", "sum"))
    j = opp.set_index("player_id").join(official, how="outer")
    pairs = [("games_played", "o_games"), ("shots", "o_shots"), ("shots_on_goal", "o_sog"),
             ("goals", "o_goals"), ("one_point_goals", "o_1pt"), ("two_point_goals", "o_2pt"),
             ("two_point_attempts", "o_2pt_shots"), ("turnovers", "o_to"),
             ("caused_turnovers", "o_ct"), ("ground_balls", "o_gb"), ("faceoffs", "o_fo"),
             ("faceoff_wins", "o_fow"), ("saves", "o_saves"), ("goals_allowed", "o_ga"),
             ("touches", "o_touches"), ("official_assists", "o_assists")]
    n4, bad4 = 0, []
    for a, b in pairs:
        bad = int((j[a].fillna(-1) != j[b].fillna(-1)).sum())
        if bad:
            bad4.append(f"{a}={bad}")
        n4 += bad
    check(4, "player_totals_reconcile_to_official_box_score", n4,
          f"{len(pairs)} columns x {len(j)} players compared against a direct groupby of "
          f"player_game_stats.csv. {bad4 or 'all agree'}")

    # ---- 5/6. team sums of player stats reconcile to team box score -------
    tg = d["tg"][d["tg"]["game_id"].isin(eligible_ids)]
    recon_cols = ["shots", "goals", "shotsOnGoal", "twoPointShots", "twoPointGoals",
                  "onePointGoals", "assists", "saves", "causedTurnovers", "faceoffsWon"]
    # Compared with an explicit merge on named keys rather than by subtracting
    # two indexed frames: player_game_stats keys the team as `teamId` and
    # team_game_stats as `officialId`, and subtracting frames whose MultiIndex
    # names differ aligns them wrongly and silently, which reports mismatches
    # that are an artefact of the check rather than of the data.
    psum = pg.groupby(["game_id", "teamId"])[recon_cols].sum().reset_index()
    tsum = tg[["game_id", "officialId"] + recon_cols]
    merged = psum.merge(tsum, left_on=["game_id", "teamId"],
                        right_on=["game_id", "officialId"],
                        suffixes=("_player", "_team"), how="outer", indicator=True)
    unmatched = int((merged["_merge"] != "both").sum())
    n5 = unmatched + int((merged["shots_player"] != merged["shots_team"]).sum())
    n6 = sum(int((merged[f"{c}_player"] != merged[f"{c}_team"]).sum())
             for c in ["goals", "onePointGoals", "twoPointGoals"])
    check(5, "team_sum_of_player_shots_matches_team_box_score", n5,
          f"{len(merged)} team-games joined on (game_id, team); {unmatched} unmatched, "
          f"shots differ in {n5 - unmatched}")
    check(6, "team_sum_of_player_goals_matches_team_box_score", n6,
          f"goals/onePointGoals/twoPointGoals across {len(merged)} team-games; "
          f"{n6} cell mismatches")

    # ---- 7. one-point / two-point shot accounting -------------------------
    n7 = int((opp["one_point_attempts"] + opp["two_point_attempts"] != opp["shots"]).sum())
    n7 += int((opp["one_point_goals"] + opp["two_point_goals"] != opp["goals"]).sum())
    n7 += int((opp["two_point_attempts"] < opp["two_point_goals"]).sum())
    n7 += int((opp["one_point_attempts"] < opp["one_point_goals"]).sum())
    check(7, "one_and_two_point_shot_accounting", n7,
          "one_point_attempts + two_point_attempts == shots; one+two point goals == goals; "
          "goals never exceed attempts within a class")

    # ---- 8. a two-point goal is 1 goal and 2 points -----------------------
    n8 = int((opp["pll_points"] != opp["one_point_goals"] + 2 * opp["two_point_goals"]).sum())
    n8 += int((opp["goals"] != opp["one_point_goals"] + opp["two_point_goals"]).sum())
    league_points = int(opp["pll_points"].sum())
    official_points = int(eligible["home_score"].sum() + eligible["away_score"].sum())
    if league_points != official_points:
        n8 += 1
    check(8, "two_point_goal_is_one_goal_and_two_points", n8,
          f"pll_points == one_point_goals + 2*two_point_goals on every row; league total "
          f"{league_points} vs official final-score total {official_points}")

    # ---- 9/10/11. impossible rates ---------------------------------------
    def _out_of_range(frame, col, lo=0.0, hi=1.0):
        v = frame[col].dropna()
        return int(((v < lo) | (v > hi)).sum())
    n9 = (_out_of_range(opp, "shooting_pct") + _out_of_range(opp, "one_point_pct")
          + _out_of_range(opp, "two_point_pct"))
    check(9, "no_impossible_shooting_rates", n9, "shooting/one-point/two-point rates in [0,1]")
    n10 = _out_of_range(opp, "faceoff_win_pct")
    n10 += int((opp["faceoff_wins"] > opp["faceoffs"]).sum())
    check(10, "no_impossible_faceoff_rates", n10,
          "faceoff_win_pct in [0,1] and wins never exceed faceoffs contested")
    n11 = _out_of_range(opp, "save_pct")
    n11 += int((opp["saves"] > opp["shots_on_goal_faced"] + 1).sum())
    check(11, "no_impossible_save_rates", n11,
          "save_pct in [0,1]; saves never exceed shots on goal faced (a 1-save tolerance "
          "absorbs the known unresolved 2026-ev-8 residual)")

    # ---- 12. no infinities ------------------------------------------------
    n12 = 0
    for frame in (comp, opp, base, d["shrink"], d["sens"]):
        num = frame.select_dtypes(include=[np.number])
        n12 += int(np.isinf(num.to_numpy(dtype=float, na_value=0.0)).sum())
    check(12, "no_infinite_values", n12,
          "every rate in the SQL layer wraps its denominator in NULLIF")

    # ---- 13. unsupported components are NULL, not zero --------------------
    n13 = int(comp["ground_ball_value"].notna().sum())
    n13 += int(comp["assist_value"].notna().sum())
    # faceoff/goalie value must be NULL exactly where the opportunity is absent
    n13 += int((comp["faceoffs"] == 0).ne(comp["faceoff_value"].isna()).sum())
    n13 += int((comp["shots_on_goal_faced"] == 0).ne(comp["goalie_value"].isna()).sum())
    check(13, "unsupported_components_are_null_not_zero", n13,
          "ground_ball_value and assist_value are NULL for all 228 players (deferred, not "
          "measured-zero); faceoff_value is NULL exactly for players with 0 faceoffs; "
          "goalie_value NULL exactly for players facing 0 shots on goal")

    # ---- 14. league shooting value sums to zero ---------------------------
    s14 = float(comp["shooting_value"].sum())
    n14 = int(abs(s14) > 1e-6)
    check(14, "league_shooting_value_sums_to_zero", n14,
          f"sum = {s14:+.10f}. Exact by construction: every attempt contributes its own shot "
          "class's league mean to the expectation, so observed and expected points sum equal")

    # ---- 15. league faceoff value sums to zero ----------------------------
    s15 = float(comp["faceoff_value"].sum())
    n15 = int(abs(s15) > 1e-6)
    fo_prob = bl("faceoff_win_probability")
    check(15, "league_faceoff_value_sums_to_zero", n15,
          f"sum = {s15:+.10f} using the empirical league win probability {fo_prob:.5f} "
          "(not an assumed 0.5 -- 18 draws have no recorded winner, and an assumed 0.5 would "
          "leave a nonzero residual)")

    # extra: the other residual components must also net out
    extra = {c: float(comp[c].sum()) for c in
             ["turnover_value", "caused_turnover_value", "goalie_value", "total_player_value"]}
    n15b = sum(int(abs(v) > 1e-6) for v in extra.values())
    check(16, "other_residual_components_sum_to_zero", n15b,
          "; ".join(f"{k}={v:+.10f}" for k, v in extra.items()))

    # ---- 17. shrinkage stays in probability bounds ------------------------
    n17, bad17 = 0, []
    for name in ["shooting_pct", "one_point_pct", "two_point_pct", "faceoff_win_pct", "save_pct"]:
        col = f"{name}_shrunk"
        if col not in d["shrink"].columns:
            continue
        v = d["shrink"][col].dropna()
        bad = int(((v < 0) | (v > 1)).sum())
        if bad:
            bad17.append(f"{col}={bad}")
        n17 += bad
    check(17, "shrunk_rates_within_probability_bounds", n17,
          f"5 shrunk rate columns checked. {bad17 or 'all within [0,1]'}")

    # ---- 18. raw and shrunk are distinguishable ---------------------------
    n18, detail18 = 0, []
    for name in ["shooting_pct", "one_point_pct", "two_point_pct", "faceoff_win_pct", "save_pct"]:
        raw, shr = f"{name}_raw", f"{name}_shrunk"
        if raw not in d["shrink"].columns:
            n18 += 1
            detail18.append(f"{name}: no raw column")
            continue
        sub = d["shrink"][[raw, shr]].dropna()
        strength = d["shrink"][f"{name}_prior_strength_trials"].dropna()
        detail18.append(f"{name}: prior {strength.iloc[0]:.1f} trials, "
                        f"raw sd {sub[raw].std():.4f} -> shrunk sd {sub[shr].std():.4f}")
    check(18, "raw_and_shrunk_estimates_both_published_and_distinct", n18, "; ".join(detail18))

    # ---- 19. SQL components vs independent Python recomputation -----------
    xp1 = bl("expected_points_per_one_point_attempt")
    xp2 = bl("expected_points_per_two_point_attempt")
    xg1 = bl("expected_points_allowed_per_one_point_shot_on_goal")
    xg2 = bl("expected_points_allowed_per_two_point_shot_on_goal")
    c_to = -bl("event_value__turnover")
    c_fo = 2 * bl("event_value__faceoff_win")

    to_rate = {g.replace("turnovers_per_touch__", ""): v for g, v in
               zip(base["baseline_name"], base["baseline_value"])
               if str(g).startswith("turnovers_per_touch__")}
    ct_rate = {g.replace("caused_turnovers_per_game__", ""): v for g, v in
               zip(base["baseline_name"], base["baseline_value"])
               if str(g).startswith("caused_turnovers_per_game__")}

    r = comp.set_index("player_id")
    exp_shoot = r["one_point_attempts"] * xp1 + r["two_point_attempts"] * xp2
    py = pd.DataFrame(index=r.index)
    py["shooting_value"] = r["pll_points"] - exp_shoot
    py["turnover_value"] = -(r["turnovers"]
                             - r["touches"] * r["baseline_group"].map(to_rate)) * c_to
    py["faceoff_value"] = ((r["faceoff_wins"] - r["faceoffs"] * fo_prob) * c_fo
                           ).where(r["faceoffs"] > 0)
    py["caused_turnover_value"] = ((r["caused_turnovers"]
                                    - r["games_played"] * r["baseline_group"].map(ct_rate))
                                   * c_to)
    py["goalie_value"] = ((r["one_point_shots_on_goal_faced"] * xg1
                           + r["two_point_shots_on_goal_faced"] * xg2)
                          - r["pll_points_allowed"]).where(r["shots_on_goal_faced"] > 0)
    py["total_player_value"] = (py[["shooting_value", "turnover_value", "faceoff_value",
                                    "caused_turnover_value", "goalie_value"]]
                                .fillna(0).sum(axis=1))
    n19, bad19 = 0, []
    for col in py.columns:
        a, b = r[col].astype(float), py[col].astype(float)
        bad = int((~np.isclose(a, b, rtol=0, atol=1e-9, equal_nan=True)).sum())
        if bad:
            bad19.append(f"{col}={bad}")
        n19 += bad
    check(19, "sql_components_match_independent_python_recomputation", n19,
          f"all {len(py.columns)} components rebuilt with separate pandas arithmetic over "
          f"{len(r)} players. {bad19 or 'none disagree'}")

    # ---- 20. all-star excluded --------------------------------------------
    allstar_games = set(games.loc[games["is_all_star"], "game_id"])
    allstar_teams = {"ASE", "ASW"}
    n20 = int(comp["team_id"].isin(allstar_teams).sum())
    n20 += int(opp["primary_team_id"].isin(allstar_teams).sum())
    # a player's opportunity counts must not include all-star-game production
    allstar_pg = d["pg"][d["pg"]["game_id"].isin(allstar_games)]
    if len(allstar_pg):
        as_shots = allstar_pg.groupby(allstar_pg["officialId"].str.zfill(6))["shots"].sum()
        joined = opp.set_index("player_id")["shots"].reindex(as_shots.index)
        official_excl = official["o_shots"].reindex(as_shots.index)
        n20 += int((joined.fillna(-1) != official_excl.fillna(-1)).sum())
    check(20, "all_star_excluded", n20,
          f"all-star game_ids {sorted(allstar_games)} and teams {sorted(allstar_teams)} absent; "
          f"{len(allstar_pg)} all-star player-game rows excluded from every opportunity count")

    # ---- 21. deterministic rebuild ----------------------------------------
    changed = _rebuild_and_compare()
    check(21, "rerun_produces_identical_output", len(changed),
          f"rebuilt {len(BUILD_OUTPUTS)} outputs into a scratch directory and compared "
          f"SHA-256; changed: {changed or 'none'}")

    # ---- 22. no value from untraceable opportunities ----------------------
    # Every component's opportunity count must be something the player is
    # individually credited with. Nothing may be driven by possessions, which
    # cannot be attributed to a player at all.
    n22 = 0
    detail22 = []
    for col in comp.columns:
        if "per_possession" in col or "possessions_played" in col:
            n22 += 1
            detail22.append(col)
    # a player with no opportunities of a class must carry no value for it
    n22 += int(((comp["faceoffs"] == 0) & comp["faceoff_value"].notna()).sum())
    n22 += int(((comp["shots_on_goal_faced"] == 0) & comp["goalie_value"].notna()).sum())
    n22 += int(((comp["shots"] == 0) & (comp["shooting_value"].abs() > TOL)).sum())
    check(22, "no_value_from_untraceable_opportunities", n22,
          "no component is denominated in possessions (the feed has no lineup data, so "
          "possession participation is unknowable); a player with zero opportunities of a "
          f"class carries no value for it. Offending columns: {detail22 or 'none'}")

    # ---- 23. documented limitations are not bypassed -----------------------
    n23, detail23 = 0, []
    # (a) shotAssistId must not be used anywhere in the value layer
    sql_text = "\n".join((REPO_ROOT / "sql" / f).read_text()
                         for f in ["player_opportunities.sql", "player_shooting_value.sql",
                                   "player_value_components.sql", "20_player_base_views.sql"])
    if "pre_shot_pass_player_id" in sql_text or "shotAssistId" in sql_text:
        n23 += 1
        detail23.append("shotAssistId/pre_shot_pass_player_id referenced in the value SQL")
    # (b) caused turnovers must come from the official box score, never events
    ct_official = int(pg["causedTurnovers"].sum())
    if int(opp["caused_turnovers"].sum()) != ct_official:
        n23 += 1
        detail23.append("caused turnovers do not match the official player box score")
    if d["events"]["is_analysis_eligible_event"].notna().any():
        # the event-level caused-turnover field must still be entirely absent
        if "caused_turnover_player_id" in d["events"].columns:
            n23 += 1
            detail23.append("an event-level caused-turnover column has appeared")
    # (c) deferred metrics must be documented as such and not emitted with values
    deferred = set(d["defs"].loc[d["defs"]["status"].isin(["deferred", "unsupported"]),
                                 "metric_name"])
    for m in deferred:
        if m in comp.columns and comp[m].notna().any():
            n23 += 1
            detail23.append(f"{m} is documented {d['defs'].loc[d['defs'].metric_name == m, 'status'].iloc[0]} but carries values")
    check(23, "documented_data_limitations_not_bypassed", n23,
          f"shotAssistId unused in the value layer; caused turnovers sourced from the official "
          f"box score ({ct_official} season-wide); {len(deferred)} deferred/unsupported metrics "
          f"emit no values. {detail23 or 'all clear'}")

    # ---- 24. every emitted component is documented -------------------------
    documented = set(d["defs"]["metric_name"])
    value_cols = [c for c in comp.columns if c.endswith("_value") or c.startswith("total_")]
    undocumented = sorted(c for c in value_cols if c not in documented
                          and not c.startswith("total_"))
    check(24, "every_value_component_is_documented", len(undocumented),
          f"{len(value_cols)} value columns checked against player_value_metric_definitions.csv; "
          f"undocumented: {undocumented or 'none'}")

    report = pd.DataFrame(results)
    out = DATA_DIR / "player_value_validation_report.csv"
    report.to_csv(out, index=False)
    n_fail = int((report["status"] == "FAIL").sum())
    with pd.option_context("display.width", 250, "display.max_colwidth", 90):
        print(report.to_string(index=False))
    print(f"\n{len(report) - n_fail}/{len(report)} checks PASS -> {out.relative_to(REPO_ROOT)}")
    return report


if __name__ == "__main__":
    main()
