"""
Phase 5: team advanced-metrics validation.

Validates the outputs of scripts/pll_build_team_metrics.py against the Phase
1-4.25 canonical tables. Writes
data/processed/2026/team_metrics_validation_report.csv with the same
check_id/check_name/status/n_failures/detail shape as
possession_validation_report.csv.

INDEPENDENCE: every numeric check here recomputes the value in pandas straight
from events.csv / possessions.csv / games.csv / team_game_stats.csv. None of
the SQL in sql/ is re-executed to check itself -- check 17 in particular
rebuilds 14 metrics with a completely separate groupby implementation and
compares. A check that passed only because the same expression was evaluated
twice would prove nothing.

A FAIL means a real correctness problem in the Phase 5 layer.
"""
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"

SHOT_EVENTS = ("shot", "goal")
TOL = 1e-9


def _load():
    d = {}
    d["tga"] = pd.read_csv(DATA_DIR / "team_game_advanced.csv")
    d["tsa"] = pd.read_csv(DATA_DIR / "team_season_advanced.csv")
    d["rank"] = pd.read_csv(DATA_DIR / "team_rankings.csv")
    d["sens"] = pd.read_csv(DATA_DIR / "team_metric_sensitivity.csv")
    d["splits"] = pd.read_csv(DATA_DIR / "possession_length_splits.csv")
    d["defs"] = pd.read_csv(DATA_DIR / "metric_definitions.csv")
    d["games"] = pd.read_csv(DATA_DIR / "games.csv")
    d["poss"] = pd.read_csv(DATA_DIR / "possessions.csv")
    d["events"] = pd.read_csv(
        DATA_DIR / "events.csv", low_memory=False,
        dtype={"player_id": str, "secondary_player_id": str, "team_id": str,
               "goalie_id": str, "gb_player_id": str, "event_id": str},
    )
    d["official"] = pd.read_csv(DATA_DIR / "team_game_stats.csv")
    d["valrep"] = pd.read_csv(DATA_DIR / "validation_report.csv")
    return d


def _eligible_games(games):
    return games[games["is_completed"] & games["include_in_league_analytics"] & ~games["is_all_star"]]


def _shot_frame(events, eligible_ids):
    """Independent reconstruction of the shot-level frame: shot/goal events in
    eligible games, with PLL points attached per goal."""
    ev = events[events["is_analysis_eligible_event"] == True]  # noqa: E712
    ev = ev[ev["game_id"].isin(eligible_ids) & ev["event_type"].isin(SHOT_EVENTS)]
    ev = ev.copy()
    ev["is_2pt"] = ev["is_two_point_attempt"] == True  # noqa: E712
    ev["is_goal"] = ev["is_valid_goal"] == True  # noqa: E712
    ev["pll_points"] = np.where(ev["is_goal"], np.where(ev["is_2pt"], 2, 1), 0)
    ev["on_goal"] = ev["shot_outcome"].isin(["goal", "saved", "on_goal_no_save"])
    return ev


BUILD_INPUTS = ["games.csv", "teams.csv", "events.csv", "possessions.csv",
                "team_game_stats.csv", "validation_report.csv"]
BUILD_OUTPUTS = ["team_game_advanced.csv", "team_season_advanced.csv", "team_rankings.csv",
                 "possession_length_splits.csv", "team_metric_sensitivity.csv",
                 "metric_definitions.csv"]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rebuild_and_compare():
    """Re-run the whole build against a scratch copy of the inputs and compare
    the outputs byte-for-byte with the committed ones."""
    import importlib
    import shutil
    import sys
    import tempfile

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    build = importlib.import_module("pll_build_team_metrics")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for name in BUILD_INPUTS:
            shutil.copy2(DATA_DIR / name, tmp_dir / name)
        original = build.DATA_DIR
        try:
            build.DATA_DIR = tmp_dir
            build.main()
        finally:
            build.DATA_DIR = original
        changed = [f for f in BUILD_OUTPUTS
                   if not (tmp_dir / f).exists() or _sha(tmp_dir / f) != _sha(DATA_DIR / f)]
    return changed, (f"rebuilt all {len(BUILD_OUTPUTS)} outputs into a scratch directory and "
                     f"compared SHA-256 against the committed files; changed: {changed or 'none'}")


def main():
    d = _load()
    tga, tsa = d["tga"], d["tsa"]
    eg = _eligible_games(d["games"])
    eligible_ids = set(eg["game_id"])
    poss = d["poss"]
    shots = _shot_frame(d["events"], eligible_ids)

    results = []

    def check(cid, name, n_fail, detail=""):
        results.append({
            "check_id": cid, "check_name": name,
            "status": "PASS" if n_fail == 0 else "FAIL",
            "n_failures": int(n_fail), "detail": detail,
        })

    # ---- 1. exactly 2 team-game rows per eligible game ---------------------
    counts = tga.groupby("game_id").size()
    missing = eligible_ids - set(counts.index)
    bad = counts[counts != 2]
    check(1, "two_team_rows_per_eligible_game", len(bad) + len(missing),
          f"{len(eligible_ids)} eligible games; {len(bad)} with a row count != 2, "
          f"{len(missing)} with no rows at all")

    # ---- 2. every row is a real participant of that game -------------------
    part = eg.set_index("game_id")[["home_team_id", "away_team_id"]]
    m = tga.merge(part, left_on="game_id", right_index=True, how="left")
    not_part = ~((m["team_id"] == m["home_team_id"]) | (m["team_id"] == m["away_team_id"]))
    bad_opp = ~((m["opponent_team_id"] == m["home_team_id"]) | (m["opponent_team_id"] == m["away_team_id"]))
    same = m["team_id"] == m["opponent_team_id"]
    check(2, "team_and_opponent_are_game_participants",
          int((not_part | bad_opp | same).sum()),
          f"{int(not_part.sum())} non-participant teams, {int(bad_opp.sum())} bad opponents, "
          f"{int(same.sum())} rows where team == opponent")

    # ---- 3. off possessions (A) == def possessions (B) ---------------------
    pairs = tga[["game_id", "team_id", "opponent_team_id", "offensive_possessions",
                 "defensive_possessions"]]
    opp = pairs.rename(columns={
        "team_id": "opponent_team_id", "opponent_team_id": "team_id",
        "offensive_possessions": "opp_off", "defensive_possessions": "opp_def"})
    j = pairs.merge(opp, on=["game_id", "team_id", "opponent_team_id"], how="inner")
    mism = (j["offensive_possessions"] != j["opp_def"]) | (j["defensive_possessions"] != j["opp_off"])
    check(3, "offensive_possessions_mirror_opponent_defensive", int(mism.sum()),
          f"{int(mism.sum())} of {len(j)} team-game rows where this team's offensive possession "
          "count does not equal the opponent's defensive possession count")

    # ---- 4. advanced-table points == official final score ------------------
    sc = eg.melt(id_vars="game_id", value_vars=["home_team_id", "away_team_id"],
                 value_name="team_id").drop(columns="variable")
    home = eg[["game_id", "home_team_id", "home_score"]].rename(
        columns={"home_team_id": "team_id", "home_score": "official_score"})
    away = eg[["game_id", "away_team_id", "away_score"]].rename(
        columns={"away_team_id": "team_id", "away_score": "official_score"})
    official_scores = pd.concat([home, away])
    j4 = tga.merge(official_scores, on=["game_id", "team_id"], how="left")
    bad4 = (j4["points_scored"] != j4["official_score"]) | (j4["points"] != j4["official_score"])
    check(4, "team_points_equal_official_final_score", int(bad4.sum()),
          f"{int(bad4.sum())} of {len(j4)} rows where possession-derived points_scored or "
          "event-derived points differs from games.csv final score")

    # ---- 5. offensive points reconcile to possession-level points ----------
    pp = poss.groupby(["game_id", "offense_team_id"])["points_scored"].sum().rename("recomputed")
    j5 = tga.merge(pp, left_on=["game_id", "team_id"], right_index=True, how="left")
    bad5 = j5["points_scored"] != j5["recomputed"]
    pa = poss.groupby(["game_id", "defense_team_id"])["points_scored"].sum().rename("recomputed_allowed")
    j5b = tga.merge(pa, left_on=["game_id", "team_id"], right_index=True, how="left")
    bad5b = j5b["points_allowed"] != j5b["recomputed_allowed"]
    check(5, "points_reconcile_to_possession_table", int(bad5.sum() + bad5b.sum()),
          f"{int(bad5.sum())} points_scored and {int(bad5b.sum())} points_allowed rows disagree "
          "with a direct groupby over possessions.csv")

    # ---- 6. season totals == sum of team-game totals ----------------------
    count_cols = [c for c in [
        "offensive_possessions", "defensive_possessions", "points_scored", "points_allowed",
        "shots", "shots_on_goal", "goals", "points", "two_point_attempts", "two_point_goals",
        "two_point_points", "one_point_goals", "turnovers", "turnovers_pbp",
        "possession_ending_turnovers", "faceoffs", "faceoff_wins", "faceoff_start_possessions",
        "ground_balls", "saves", "goals_allowed", "shots_allowed", "shots_on_goal_allowed",
        "man_up_opportunities", "man_up_shots", "man_up_goals", "man_up_points",
        "truncated_possessions", "complete_possessions", "measurable_span_possessions",
        "observed_possession_seconds", "complete_possession_seconds",
        "ambiguous_offensive_possessions", "ambiguous_defensive_possessions",
    ] if c in tga.columns and c in tsa.columns]
    summed = tga.groupby("team_id")[count_cols].sum()
    j6 = tsa.set_index("team_id")[count_cols]
    diff6 = (summed - j6).abs()
    n6 = int((diff6 > TOL).sum().sum())
    check(6, "season_totals_equal_sum_of_team_games", n6,
          f"{len(count_cols)} count columns x {len(j6)} teams compared; "
          f"{n6} cells differ. Mismatched columns: "
          f"{sorted(diff6.columns[(diff6 > TOL).any()].tolist())}")

    # ---- 7. no impossible percentages -------------------------------------
    pct_cols = [c for c in tga.columns
                if c.endswith("_pct") or c.endswith("_rate") or c.endswith("_share")
                or c.endswith("_ratio")]
    n7 = 0
    offenders = []
    for frame_name, frame in (("team_game", tga), ("team_season", tsa)):
        for c in pct_cols:
            if c not in frame.columns:
                continue
            v = frame[c].dropna()
            # possession_span_coverage_ratio is a diagnostic ratio, not a
            # proportion, and is legitimately allowed to exceed 1.
            hi = np.inf if c == "possession_span_coverage_ratio" else 1.0
            bad = ((v < 0) | (v > hi)).sum()
            if bad:
                offenders.append(f"{frame_name}.{c}={bad}")
            n7 += int(bad)
    check(7, "no_impossible_percentages", n7,
          f"{len(pct_cols)} proportion-typed columns checked for <0 or >1. "
          f"Offenders: {offenders or 'none'}")

    # ---- 8. no negative counts --------------------------------------------
    # Residual columns (*_minus_official) are signed differences by design.
    n8 = 0
    offenders8 = []
    for frame_name, frame in (("team_game", tga), ("team_season", tsa)):
        for c in frame.select_dtypes(include=[np.number]).columns:
            if c.endswith("_minus_official") or "net_efficiency" in c or c in (
                    "game_id", "week", "rank_change", "diff_from_league_mean", "z_score"):
                continue
            bad = int((frame[c].dropna() < 0).sum())
            if bad:
                offenders8.append(f"{frame_name}.{c}={bad}")
            n8 += bad
    check(8, "no_negative_counts_or_rates", n8,
          f"Signed residual (*_minus_official) and net-efficiency columns excluded by design. "
          f"Offenders: {offenders8 or 'none'}")

    # ---- 9. no infinities / divide-by-zero artefacts ----------------------
    n9 = 0
    for frame in (tga, tsa, d["rank"], d["sens"], d["splits"]):
        num = frame.select_dtypes(include=[np.number])
        n9 += int(np.isinf(num.to_numpy(dtype=float, na_value=0.0)).sum())
    check(9, "no_infinite_values", n9,
          "every rate in the SQL layer wraps its denominator in NULLIF, so a zero denominator "
          "yields NULL rather than inf")

    # ---- 10. every emitted metric has a documented denominator ------------
    documented = set(d["defs"]["metric_name"])
    exempt = {  # keys, context and provenance columns, not metrics
        "game_id", "game_slug", "start_date_utc", "week", "game_type", "is_playoff",
        "team_id", "team_name", "opponent_team_id", "is_home", "team_score_official",
        "opponent_score_official", "result", "games_played", "wins", "losses", "ties",
        "playoff_games", "points_scored_official", "points_allowed_official",
    }
    undocumented = sorted(
        c for c in set(tga.columns) | set(tsa.columns)
        if c not in documented and c not in exempt
        and not c.endswith("_validation_status")
        and not c.startswith("has_") and not c.startswith("games_with_")
        and not c.endswith("_minus_official")
    )
    missing_den = sorted(
        d["defs"].loc[d["defs"]["denominator"].isna() |
                      (d["defs"]["denominator"].astype(str).str.strip() == ""), "metric_name"])
    check(10, "every_metric_has_a_documented_denominator",
          len(undocumented) + len(missing_den),
          f"{len(undocumented)} emitted columns absent from metric_definitions.csv "
          f"({undocumented[:8]}); {len(missing_den)} definition rows with an empty denominator "
          f"({missing_den[:8]})")

    # ---- 11. two-point goals contribute 1 goal and 2 points ---------------
    g_by = shots[shots["is_goal"]].groupby(["game_id", "team_id"])
    recomputed = pd.DataFrame({
        "goals_r": g_by.size(),
        "two_point_goals_r": g_by["is_2pt"].sum(),
        "points_r": g_by["pll_points"].sum(),
    })
    j11 = tga.merge(recomputed, left_on=["game_id", "team_id"], right_index=True, how="left")
    bad_goals = j11["goals"] != j11["goals_r"]
    bad_tp = j11["two_point_goals"] != j11["two_point_goals_r"]
    # the actual identity: points == goals + two_point_goals
    bad_identity = j11["points"] != (j11["goals"] + j11["two_point_goals"])
    bad_pts = j11["points"] != j11["points_r"]
    check(11, "two_point_goal_counts_one_goal_and_two_points",
          int((bad_goals | bad_tp | bad_identity | bad_pts).sum()),
          f"{int(bad_identity.sum())} rows violate points == goals + two_point_goals; "
          f"{int(bad_goals.sum())} goal-count and {int(bad_pts.sum())} point-total "
          "disagreements vs an independent event-level recount")

    # ---- 12. net efficiency arithmetic ------------------------------------
    n12 = 0
    for frame in (tga, tsa):
        lhs = frame["net_efficiency"]
        rhs = frame["offensive_efficiency"] - frame["defensive_efficiency"]
        n12 += int((~np.isclose(lhs, rhs, rtol=0, atol=1e-12, equal_nan=True)).sum())
        lhs100 = frame["net_efficiency_per_100"]
        n12 += int((~np.isclose(lhs100, 100 * rhs, rtol=0, atol=1e-10, equal_nan=True)).sum())
        # the aliases must genuinely be aliases
        n12 += int((~np.isclose(frame["offensive_efficiency"], frame["points_per_possession"],
                                atol=1e-12, equal_nan=True)).sum())
    check(12, "net_efficiency_arithmetic_and_aliases", n12,
          "net_efficiency == offensive_efficiency - defensive_efficiency, the per-100 columns are "
          "exactly 100x, and offensive_efficiency is identical to points_per_possession")

    # ---- 13. rankings reproducible ----------------------------------------
    rk = d["rank"]
    n13 = 0
    detail13 = []
    for metric, grp in rk.groupby("metric_name"):
        hib = bool(grp["higher_is_better"].iloc[0])
        vals = grp.set_index("team_id")["metric_value"]
        # independent competition ranking: 1 + how many teams strictly beat you
        expected = {}
        for team, v in vals.items():
            better = (vals > v).sum() if hib else (vals < v).sum()
            expected[team] = int(better) + 1
        got = grp.set_index("team_id")["rank_value"].to_dict()
        bad = [t for t in expected if expected[t] != got[t]]
        if bad:
            detail13.append(f"{metric}:{bad}")
        n13 += len(bad)
        # ranks must cover 1..n with competition-rank semantics
        if grp["rank_value"].min() != 1:
            n13 += 1
            detail13.append(f"{metric}: min rank {grp['rank_value'].min()} != 1")
    check(13, "rankings_reproducible_and_correctly_directed", n13,
          f"{rk['metric_name'].nunique()} ranked metrics recomputed with an independent "
          f"competition-rank implementation. {detail13 or 'all agree'}")

    # ---- 14. all-star excluded --------------------------------------------
    allstar_games = set(d["games"].loc[d["games"]["is_all_star"], "game_id"])
    allstar_teams = {"ASE", "ASW"}
    n14 = int(tga["game_id"].isin(allstar_games).sum())
    n14 += int(tga["team_id"].isin(allstar_teams).sum())
    n14 += int(tsa["team_id"].isin(allstar_teams).sum())
    n14 += int(rk["team_id"].isin(allstar_teams).sum())
    check(14, "all_star_excluded_from_league_tables", n14,
          f"all-star game_ids {sorted(allstar_games)} and teams {sorted(allstar_teams)} must not "
          "appear in any Phase 5 table")

    # ---- 15. truncated possessions not treated as exact -------------------
    # (a) complete_* excludes truncated; (b) the length splits contain no
    # truncated possession at all; (c) span totals differ wherever any
    # possession was truncated.
    n15 = 0
    bad15 = tga[(tga["truncated_possessions"] > 0) &
                (tga["observed_possession_seconds"] == tga["complete_possession_seconds"]) &
                (tga["observed_possession_seconds"] > 0)]
    # a truncated possession may genuinely have 0 duration, so only flag rows
    # where the truncated possessions carried nonzero time
    trunc_time = (poss[poss["is_truncated"]]
                  .groupby(["game_id", "offense_team_id"])["duration_seconds"].sum())
    j15 = bad15.merge(trunc_time.rename("trunc_secs"), left_on=["game_id", "team_id"],
                      right_index=True, how="left")
    n15 += int((j15["trunc_secs"].fillna(0) > 0).sum())
    if (tga["complete_possessions"] + tga["truncated_possessions"] != tga["offensive_possessions"]).any():
        n15 += int((tga["complete_possessions"] + tga["truncated_possessions"]
                    != tga["offensive_possessions"]).sum())
    split_total = d["splits"].loc[d["splits"]["scope"] == "LEAGUE", "possessions"].sum()
    expected_split = int((~poss["is_ambiguous"] & ~poss["is_truncated"] & (poss["event_count"] > 1)).sum())
    if split_total != expected_split:
        n15 += 1
    check(15, "truncated_possessions_never_treated_as_exact", n15,
          f"complete + truncated == offensive possessions on every row; possession_length_splits "
          f"covers {split_total} possessions and an independent recount of "
          f"(unambiguous AND not truncated AND event_count>1) gives {expected_split}")

    # ---- 16. unresolved-validation games flagged --------------------------
    vr = d["valrep"]
    metric_map = {
        "turnovers": "has_turnover_validation_issue",
        "ground_balls": "has_ground_ball_validation_issue",
        "shot_clock_expirations": "has_shot_clock_validation_issue",
        "saves": "has_save_validation_issue",
        "penalties": "has_penalty_validation_issue",
    }
    slug_to_id = d["games"].set_index("game_slug")["game_id"].to_dict()
    n16 = 0
    detail16 = []
    for metric, col in metric_map.items():
        affected = {slug_to_id[s] for s in
                    vr.loc[(vr["metric"] == metric) & (vr["final_status"] != "PASS"), "game_slug"]
                    if s in slug_to_id}
        affected &= eligible_ids
        flagged = set(tga.loc[tga[col], "game_id"])
        miss, extra = affected - flagged, flagged - affected
        n16 += len(miss) + len(extra)
        detail16.append(f"{metric}: {len(affected)} affected games, {len(miss)} unflagged, "
                        f"{len(extra)} over-flagged")
    check(16, "validation_issues_propagated_to_team_game_rows", n16, "; ".join(detail16))

    # ---- 17. SQL vs independent pandas recomputation -----------------------
    # 14 metrics, rebuilt from scratch with pandas groupbys that share no code
    # path with sql/team_game_advanced.sql.
    off = poss.groupby(["game_id", "offense_team_id"]).agg(
        off_poss=("possession_id", "size"),
        pts=("points_scored", "sum"),
        p_shots=("shot_attempts", "sum"),
        p_sog=("shots_on_goal", "sum"),
        tp_poss=("has_two_point_attempt", "sum"),
        fo_start=("start_reason", lambda s: (s == "faceoff_win").sum()),
        to_end=("end_reason", lambda s: (s == "turnover").sum()),
        amb=("is_ambiguous", "sum"),
        trunc=("is_truncated", "sum"),
        span=("duration_seconds", "sum"),
    )
    off.index.names = ["game_id", "team_id"]
    dfn = poss.groupby(["game_id", "defense_team_id"]).agg(
        def_poss=("possession_id", "size"), pts_allowed=("points_scored", "sum"))
    dfn.index.names = ["game_id", "team_id"]
    sh = shots.groupby(["game_id", "team_id"]).agg(
        e_shots=("event_id", "size"),
        e_sog=("on_goal", "sum"),
        e_goals=("is_goal", "sum"),
        e_points=("pll_points", "sum"),
        e_tp_att=("is_2pt", "sum"),
    )
    rec = off.join(dfn).join(sh)
    rec["off_eff"] = rec["pts"] / rec["off_poss"]
    rec["def_eff"] = rec["pts_allowed"] / rec["def_poss"]
    rec["net_eff"] = rec["off_eff"] - rec["def_eff"]
    rec["shooting"] = rec["e_goals"] / rec["e_shots"]
    rec["pps"] = rec["e_points"] / rec["e_shots"]
    rec["spp"] = rec["e_shots"] / rec["off_poss"]
    rec["tp_rate"] = rec["tp_poss"] / rec["off_poss"]
    rec["tp_att_rate"] = rec["e_tp_att"] / rec["e_shots"]
    rec["fo_share"] = rec["fo_start"] / rec["off_poss"]
    rec["pe_to_rate"] = rec["to_end"] / rec["off_poss"]

    j17 = tga.set_index(["game_id", "team_id"]).join(rec, how="outer")
    comparisons = [
        ("offensive_possessions", "off_poss"), ("defensive_possessions", "def_poss"),
        ("points_scored", "pts"), ("points_allowed", "pts_allowed"),
        ("shots", "e_shots"), ("shots_on_goal", "e_sog"), ("goals", "e_goals"),
        ("points", "e_points"), ("two_point_attempts", "e_tp_att"),
        ("offensive_efficiency", "off_eff"), ("defensive_efficiency", "def_eff"),
        ("net_efficiency", "net_eff"), ("shooting_pct", "shooting"),
        ("points_per_shot", "pps"), ("shots_per_possession", "spp"),
        ("two_point_possession_rate", "tp_rate"), ("two_point_attempt_rate", "tp_att_rate"),
        ("faceoff_start_possession_share", "fo_share"),
        ("possession_ending_turnover_rate", "pe_to_rate"),
        ("observed_possession_seconds", "span"),
        ("ambiguous_offensive_possessions", "amb"),
        ("truncated_possessions", "trunc"),
        ("shots_per_possession", "spp"),
    ]
    n17 = 0
    bad17 = []
    for sql_col, py_col in comparisons:
        a = j17[sql_col].astype(float)
        b = j17[py_col].astype(float)
        bad = int((~np.isclose(a, b, rtol=0, atol=1e-9, equal_nan=True)).sum())
        if bad:
            bad17.append(f"{sql_col}={bad}")
        n17 += bad
    check(17, "sql_metrics_match_independent_python_recomputation", n17,
          f"{len(comparisons)} SQL-produced columns recomputed with independent pandas groupbys "
          f"over events.csv/possessions.csv. Disagreements: {bad17 or 'none'}")

    # ---- 18. season rates recomputed from season totals -------------------
    n18 = 0
    bad18 = []
    season_checks = [
        ("offensive_efficiency", "points_scored", "offensive_possessions"),
        ("defensive_efficiency", "points_allowed", "defensive_possessions"),
        ("shooting_pct", "goals", "shots"),
        ("points_per_shot", "points", "shots"),
        ("turnover_rate", "turnovers", "offensive_possessions"),
        ("faceoff_win_pct", "faceoff_wins", "faceoffs"),
        ("two_point_conversion_pct", "two_point_goals", "two_point_attempts"),
        ("two_point_attempt_rate", "two_point_attempts", "shots"),
        ("two_point_possession_rate", "possessions_with_two_point_attempt", "offensive_possessions"),
        ("man_up_goals_per_opportunity", "man_up_goals", "man_up_opportunities"),
        ("save_pct_vs_shots_on_goal", "saves", "shots_on_goal_allowed"),
        ("goals_per_possession", "goals", "offensive_possessions"),
    ]
    for rate, num, den in season_checks:
        expected = tsa[num] / tsa[den]
        bad = int((~np.isclose(tsa[rate], expected, rtol=0, atol=1e-12, equal_nan=True)).sum())
        if bad:
            bad18.append(f"{rate}={bad}")
        n18 += bad
    # season rates must be totals-based, NOT the mean of per-game rates
    mean_of_games = tga.groupby("team_id")["offensive_efficiency"].mean()
    if np.isclose(tsa.set_index("team_id")["offensive_efficiency"], mean_of_games,
                  atol=1e-12).all():
        n18 += 1
        bad18.append("season offensive_efficiency equals the mean of per-game rates, which "
                     "suggests it was not recomputed from season totals")
    check(18, "season_rates_recomputed_from_season_totals", n18,
          f"{len(season_checks)} season rates verified as sum(numerator)/sum(denominator). "
          f"{bad18 or 'all agree'}")

    # ---- 19. sensitivity table internally consistent ----------------------
    sens = d["sens"]
    n19 = 0
    bad19 = []
    absdiff = sens["high_confidence_value"] - sens["full_value"]
    n19 += int((~np.isclose(sens["absolute_difference"], absdiff, atol=1e-12, equal_nan=True)).sum())
    reldiff = absdiff / sens["full_value"].abs().replace(0, np.nan)
    n19 += int((~np.isclose(sens["relative_difference"], reldiff, atol=1e-12, equal_nan=True)).sum())
    n19 += int((~np.isclose(sens["rank_change"],
                            sens["rank_high_confidence"] - sens["rank_full"],
                            atol=0, equal_nan=True)).sum())
    # the high-confidence subsets must be strictly smaller than the full set
    if (sens["n_possessions_high_confidence"] > sens["n_possessions_full"]).any():
        n19 += int((sens["n_possessions_high_confidence"] > sens["n_possessions_full"]).sum())
        bad19.append("a high-confidence subset is larger than the full set")
    expected_rows = 8 * 6 * 2
    if len(sens) != expected_rows:
        n19 += 1
        bad19.append(f"{len(sens)} rows, expected {expected_rows} (8 teams x 6 metrics x 2 subsets)")
    check(19, "sensitivity_table_internally_consistent", n19,
          f"absolute/relative differences and rank_change recomputed from the value and rank "
          f"columns. {bad19 or 'all agree'}")

    # ---- 20. rerunning the build reproduces identical output --------------
    # Rebuilt into a temporary directory rather than over the top of the files
    # under test: a validator that overwrites its own inputs mid-run would make
    # every check above describe a different artefact than the one on disk.
    changed, detail20 = _rebuild_and_compare()
    check(20, "rerun_produces_identical_output", len(changed), detail20)

    report = pd.DataFrame(results)
    out = DATA_DIR / "team_metrics_validation_report.csv"
    report.to_csv(out, index=False)

    n_fail = int((report["status"] == "FAIL").sum())
    print(report.to_string(index=False))
    print(f"\n{len(report) - n_fail}/{len(report)} checks PASS -> {out.relative_to(REPO_ROOT)}")
    return report


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
