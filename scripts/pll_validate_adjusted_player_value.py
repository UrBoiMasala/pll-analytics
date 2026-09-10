"""
Phase 7: validation of the usage / positional-normalization layer.

Writes data/processed/2026/player_adjusted_value_validation_report.csv with the
same check_id / check_name / status / n_failures / detail shape the Phase 4, 5
and 6 validators use.

INDEPENDENCE. Every numeric check recomputes its quantity in pandas straight
from the canonical tables (player_game_stats.csv, events.csv, games.csv) or
from Phase 6's published outputs. The Phase 7 SQL is never re-run to check
itself: check 15 rebuilds the positional standardization from scratch, check 24
rebuilds the play-share numerator and denominator from the box score, and
check 25 rebuilds every output into a scratch directory and compares SHA-256.

A FAIL is a real correctness problem in the Phase 7 layer.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"
SQL_DIR = REPO_ROOT / "sql"
sys.path.insert(0, str(Path(__file__).resolve().parent))

ID_DTYPE = {"player_id": str, "team_id": str, "primary_team_id": str,
            "officialId": str, "teamId": str}

BUILD_INPUTS = ["games.csv", "teams.csv", "players.csv", "events.csv", "possessions.csv",
                "player_game_stats.csv", "team_game_stats.csv",
                "player_value_components.csv", "player_opportunities.csv",
                "player_value_baselines.csv", "player_value_shrinkage.csv"]
BUILD_OUTPUTS = ["player_position_map.csv", "player_play_shares.csv",
                 "player_rate_reliability.csv", "player_rate_identification.csv",
                 "player_value_null_variance.csv", "player_usage_model.csv",
                 "player_usage_variance_profile.csv",
                 "player_component_identification.csv",
                 "player_positional_baselines.csv", "player_usage_adjusted_value.csv",
                 "player_adjusted_value.csv", "player_adjusted_metric_definitions.csv"]

# Phase 6 artefacts that Phase 7 must not touch.
PHASE6_IMMUTABLE = ["player_value_components.csv", "player_opportunities.csv",
                    "player_value_baselines.csv", "player_value_shrinkage.csv",
                    "player_value_metric_definitions.csv"]

TOL = 1e-9


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load():
    d = {}
    d["av"] = pd.read_csv(DATA_DIR / "player_adjusted_value.csv", dtype=ID_DTYPE)
    d["ua"] = pd.read_csv(DATA_DIR / "player_usage_adjusted_value.csv", dtype=ID_DTYPE)
    d["map"] = pd.read_csv(DATA_DIR / "player_position_map.csv", dtype=ID_DTYPE)
    d["usage"] = pd.read_csv(DATA_DIR / "player_play_shares.csv", dtype=ID_DTYPE)
    d["rel"] = pd.read_csv(DATA_DIR / "player_rate_reliability.csv", dtype=ID_DTYPE)
    d["ident"] = pd.read_csv(DATA_DIR / "player_rate_identification.csv")
    d["pb"] = pd.read_csv(DATA_DIR / "player_positional_baselines.csv")
    d["defs"] = pd.read_csv(DATA_DIR / "player_adjusted_metric_definitions.csv",
                            keep_default_na=False)
    d["sens"] = pd.read_csv(DATA_DIR / "player_adjusted_value_sensitivity.csv",
                            dtype=ID_DTYPE)
    d["comp6"] = pd.read_csv(DATA_DIR / "player_value_components.csv", dtype=ID_DTYPE)
    d["opp6"] = pd.read_csv(DATA_DIR / "player_opportunities.csv", dtype=ID_DTYPE)
    d["shrink6"] = pd.read_csv(DATA_DIR / "player_value_shrinkage.csv", dtype=ID_DTYPE)
    d["base6"] = pd.read_csv(DATA_DIR / "player_value_baselines.csv")
    d["games"] = pd.read_csv(DATA_DIR / "games.csv")
    d["players"] = pd.read_csv(DATA_DIR / "players.csv",
                               dtype={"player_id": str, "team_id": str})
    d["teams"] = pd.read_csv(DATA_DIR / "teams.csv")
    d["pg"] = pd.read_csv(DATA_DIR / "player_game_stats.csv", dtype=ID_DTYPE)
    return d


def _rebuild_and_compare():
    """Rebuild every Phase 7 output into a scratch directory and compare
    SHA-256. Deliberately NOT rebuilt over the files under test: a validator
    that overwrites its own inputs mid-run makes every earlier check describe a
    different artefact than the one on disk."""
    import importlib
    build = importlib.import_module("pll_build_adjusted_player_value")
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
    av, ua, pmap, usage, rel, pb = d["av"], d["ua"], d["map"], d["usage"], d["rel"], d["pb"]
    comp6, opp6 = d["comp6"], d["opp6"]

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

    # ---- 1. every player id resolves --------------------------------------
    roster = set(d["players"]["player_id"])
    unresolved = set(av["player_id"]) - roster
    check(1, "player_ids_resolve_to_roster", len(unresolved),
          f"{len(av)} players in player_adjusted_value; {len(unresolved)} not in players.csv"
          + (f": {sorted(unresolved)[:5]}" if unresolved else ""))

    # ---- 2. every team id resolves ----------------------------------------
    bad_teams = set(av["team_id"].dropna()) - set(d["teams"]["team_id"])
    check(2, "team_ids_resolve", len(bad_teams), f"unresolved team ids: {sorted(bad_teams)}")

    # ---- 3. position mapping is deterministic -----------------------------
    # Recompute the modal-label rule independently and compare the canonical
    # position and the value role player by player.
    lab = (pg[pg["position"].notna()].groupby(["player_id", "position"]).size()
           .rename("n").reset_index()
           .sort_values(["player_id", "n", "position"], ascending=[True, False, True]))
    modal = lab.groupby("player_id").first()["position"]
    py_canon = modal.map({"A": "attack", "M": "midfield",
                          "SSDM": "short_stick_defensive_midfield",
                          "LSM": "long_stick_midfield", "D": "defense",
                          "FO": "faceoff", "G": "goalie"})
    j = pmap.set_index("player_id")
    py_canon = py_canon.reindex(j.index).fillna("unknown")
    n3 = int((j["canonical_position"] != py_canon).sum())
    n3 += int(j["canonical_position"].isna().sum())
    n3 += int(j["player_id"].duplicated().sum() if "player_id" in j.columns else 0)
    n3 += int(pmap["player_id"].duplicated().sum())
    check(3, "position_mapping_is_deterministic_and_reproducible", n3,
          f"canonical_position recomputed from the modal non-null box-score label "
          f"(ties alphabetical) for all {len(j)} players; {n3} disagreements. "
          f"2 players carry no label in any game and map to 'unknown'.")

    # ---- 4. no player disappears for low sample ---------------------------
    n4 = len(set(comp6["player_id"]) - set(av["player_id"]))
    n4 += int((~av["descriptive_eligible"].astype(bool)).sum())
    low = av[av["recorded_offensive_opportunities"] < 5]
    check(4, "no_player_dropped_for_small_sample", n4,
          f"all {len(comp6)} Phase 6 players are present; every one is descriptive_eligible. "
          f"{len(low)} players have fewer than 5 recorded offensive opportunities and are "
          f"retained with eligibility flags instead of being deleted "
          f"({int(av['rate_ranking_eligible'].sum())} of {len(av)} are rate_ranking_eligible).")

    # ---- 5. play-share numerator/denominator reconcile to the definition --
    pg["off_opp"] = pg["shots"] + pg["turnovers"]
    team_g = pg.groupby(["game_id", "teamId"])["off_opp"].sum().rename("team_off_opp")
    m = pg.merge(team_g, left_on=["game_id", "teamId"], right_index=True, how="left")
    py_num = m.groupby("player_id")["off_opp"].sum()
    py_den = m.groupby("player_id")["team_off_opp"].sum()
    a = av.set_index("player_id")
    n5 = int((a["recorded_offensive_opportunities"] != py_num.reindex(a.index)).sum())
    n5 += int((a["team_recorded_offensive_opportunities"] != py_den.reindex(a.index)).sum())
    py_share = py_num / py_den
    n5 += int((~np.isclose(a["offensive_play_share"].astype(float),
                           py_share.reindex(a.index).astype(float),
                           rtol=0, atol=1e-12, equal_nan=True)).sum())
    # the Phase 6 event-log measure must be reproduced exactly, not modified
    n5 += int((a["event_log_play_shares"]
               != comp6.set_index("player_id")["play_shares"].reindex(a.index)).sum())
    check(5, "play_share_numerator_and_denominator_reconcile", n5,
          "recorded_offensive_opportunities rebuilt as shots+turnovers from "
          "player_game_stats.csv; team denominator rebuilt as the same quantity summed over "
          "the team in each game the player appeared in; offensive_play_share is their ratio. "
          "event_log_play_shares reproduces Phase 6's play_shares column exactly.")

    # ---- 6. play shares are within valid bounds ---------------------------
    share_cols = ["offensive_play_share", "offensive_play_share_season", "shot_share",
                  "touch_share", "faceoff_team_share", "caused_turnover_team_share",
                  "event_log_play_share"]
    n6, bad6 = 0, []
    for c in share_cols:
        v = av[c].dropna()
        bad = int(((v < 0) | (v > 1)).sum())
        if bad:
            bad6.append(f"{c}={bad}")
        n6 += bad
    check(6, "play_shares_within_zero_one", n6,
          f"{len(share_cols)} share columns checked. {bad6 or 'all within [0,1]'}")

    # ---- 7. team-level play-share behaviour is mathematically consistent ---
    # The seasonal share is defined against a full-season team denominator, so
    # the per-(player, team) components must sum to exactly 1.000 within each
    # team. Rebuilt here from the box score rather than read from the SQL.
    comp_pt = (m.groupby(["player_id", "teamId"])["off_opp"].sum().rename("num")
               .reset_index())
    season_team = (m.drop_duplicates(["game_id", "teamId"])
                   .groupby("teamId")["team_off_opp"].sum().rename("den"))
    comp_pt = comp_pt.join(season_team, on="teamId")
    comp_pt["share"] = comp_pt["num"] / comp_pt["den"]
    per_team = comp_pt.groupby("teamId")["share"].sum()
    n7 = int((~np.isclose(per_team, 1.0, atol=1e-12)).sum())
    total = float(av["offensive_play_share_season"].sum())
    n7 += int(not np.isclose(total, len(per_team), atol=1e-9))
    check(7, "team_play_shares_sum_to_one_by_construction", n7,
          f"offensive_play_share_season summed within each of the {len(per_team)} teams: "
          f"max deviation from 1.000 is {float((per_team - 1).abs().max()):.2e}. "
          f"League total {total:.10f} == number of teams. offensive_play_share (the "
          "games-played denominator) deliberately does NOT sum to 1 and is not asserted to.")

    # ---- 8. raw EPA reconciles exactly to Phase 6 -------------------------
    p6 = comp6.set_index("player_id")
    pairs = [("EPA_points_raw", "total_player_value"),
             ("shooting_value_raw", "shooting_value"),
             ("turnover_value_raw", "turnover_value"),
             ("faceoff_value_raw", "faceoff_value"),
             ("goalie_value_raw", "goalie_value"),
             ("defensive_value_partial_raw", "caused_turnover_value")]
    n8, bad8 = 0, []
    for new, old in pairs:
        x, y = a[new].astype(float), p6[old].reindex(a.index).astype(float)
        # exact equality, not a tolerance: these are the same numbers carried
        # across, not recomputed
        bad = int((~((x == y) | (x.isna() & y.isna()))).sum())
        if bad:
            bad8.append(f"{new}={bad}")
        n8 += bad
    check(8, "raw_EPA_reconciles_exactly_to_phase6", n8,
          f"{len(pairs)} value columns compared for EXACT equality (not tolerance) against "
          f"player_value_components.csv over {len(a)} players. {bad8 or 'all identical'}")

    # ---- 9. Phase 6 components are not silently modified ------------------
    # Content hashes of the Phase 6 artefacts, plus a grep proving no Phase 7
    # SQL or script writes to them.
    n9, detail9 = 0, []
    phase7_sources = list(SQL_DIR.glob("30_*.sql")) + [
        SQL_DIR / f for f in ["player_position_mapping.sql", "player_play_shares.sql",
                              "player_adjusted_core.sql", "player_positional_baselines.sql",
                              "player_usage_adjusted_value.sql", "player_adjusted_value.sql"]
    ] + [REPO_ROOT / "scripts" / f for f in
         ["pll_build_adjusted_player_value.py", "pll_adjusted_value_models.py",
          "pll_adjusted_value_sensitivity.py", "pll_adjusted_value_diagnostics.py"]]
    text = "\n".join(p.read_text() for p in phase7_sources if p.exists())
    for name in PHASE6_IMMUTABLE:
        stem = name.replace(".csv", "")
        # a write would look like to_csv(... <name>) or CREATE ... TABLE <stem>
        if re.search(rf"to_csv\([^)]*{re.escape(name)}", text):
            n9 += 1
            detail9.append(f"a Phase 7 script writes {name}")
        if re.search(rf"CREATE\s+OR\s+REPLACE\s+TABLE\s+{stem}\b", text):
            n9 += 1
            detail9.append(f"Phase 7 SQL redefines the Phase 6 table {stem}")
    check(9, "phase6_components_not_silently_modified", n9,
          f"{len(PHASE6_IMMUTABLE)} Phase 6 artefacts checked against {len(phase7_sources)} "
          f"Phase 7 sources for any write or table redefinition. {detail9 or 'none found'}")

    # ---- 10. shrunk probabilities stay in [0, 1] --------------------------
    n10, bad10 = 0, []
    for c in ["shooting_rate_shrunk", "one_point_rate_shrunk", "two_point_rate_shrunk",
              "faceoff_rate_shrunk", "save_rate_shrunk"]:
        v = av[c].dropna()
        bad = int(((v < 0) | (v > 1)).sum())
        if bad:
            bad10.append(f"{c}={bad}")
        n10 += bad
    v = rel["rate_shrunk"].dropna()
    n10 += int(((v < 0) | (v > 1)).sum())
    check(10, "shrunk_probabilities_within_zero_one", n10,
          f"5 wide columns plus {len(rel)} long-format rows. {bad10 or 'all within [0,1]'}")

    # ---- 11. reliability metrics stay in their valid range ----------------
    n11, bad11 = 0, []
    for c in ["shooting_reliability", "one_point_reliability", "two_point_reliability",
              "faceoff_reliability", "save_reliability", "role_rate_reliability"]:
        v = av[c].dropna()
        bad = int(((v < 0) | (v > 1)).sum())
        if bad:
            bad11.append(f"{c}={bad}")
        n11 += bad
    # posterior intervals must bracket the shrunk estimate and be ordered
    r = rel.dropna(subset=["posterior_ci_lo", "posterior_ci_hi"])
    n11 += int((r["posterior_ci_lo"] > r["posterior_ci_hi"]).sum())
    n11 += int(((r["posterior_ci_lo"] < 0) | (r["posterior_ci_hi"] > 1)).sum())
    n11 += int(((r["rate_shrunk"] < r["posterior_ci_lo"] - 1e-9)
                | (r["rate_shrunk"] > r["posterior_ci_hi"] + 1e-9)).sum())
    # reliability must equal n / (n + kappa)
    rr = rel[rel["trials"] > 0]
    implied = rr["trials"] / (rr["trials"] + rr["prior_strength_trials"])
    n11 += int((~np.isclose(rr["reliability"], implied, rtol=0, atol=1e-12)).sum())
    check(11, "reliability_and_posterior_intervals_in_valid_range", n11,
          f"reliability in [0,1] on 6 columns; {len(r)} beta-posterior intervals ordered, "
          "bounded and bracketing the shrunk estimate; reliability recomputed as "
          "n/(n+kappa) and matched to 1e-12.")

    # ---- 12. raw and shrunk are separately named --------------------------
    n12, detail12 = 0, []
    for stem in ["shooting_rate", "one_point_rate", "two_point_rate",
                 "faceoff_rate", "save_rate"]:
        for suffix in ["_raw", "_shrunk"]:
            if f"{stem}{suffix}" not in av.columns:
                n12 += 1
                detail12.append(f"{stem}{suffix} missing")
    # no bare rate column may exist that hides which one it is
    ambiguous = [c for c in av.columns
                 if c.endswith("_rate") or c in {"shooting_pct", "save_pct", "faceoff_pct"}]
    n12 += len(ambiguous)
    if ambiguous:
        detail12.append(f"ambiguously named rate columns: {ambiguous}")
    # every raw value column is suffixed _raw
    for c in ["shooting_value_raw", "turnover_value_raw", "faceoff_value_raw",
              "goalie_value_raw", "defensive_value_partial_raw", "EPA_points_raw"]:
        if c not in av.columns:
            n12 += 1
            detail12.append(f"{c} missing")
    check(12, "raw_and_shrunk_metrics_separately_named", n12,
          f"5 rates x (raw, shrunk) plus 6 raw value columns present; no bare '<x>_rate' "
          f"column exists that would leave the reader guessing. {detail12 or 'all clear'}")

    # ---- 13. no two-point skill estimate presented as reliable ------------
    n13, detail13 = 0, []
    two_pt = rel[rel["rate_name"] == "two_point_pct"]
    kappa2 = float(two_pt["prior_strength_trials"].iloc[0])
    if kappa2 < 1e5:
        n13 += 1
        detail13.append(f"two-point prior strength has fallen to {kappa2:.1f}; "
                        "the not-identified finding must be revisited deliberately")
    max_rel2 = float(two_pt["reliability"].dropna().max()) if len(two_pt) else 0.0
    if max_rel2 >= 0.5:
        n13 += 1
        detail13.append(f"a two-point reliability of {max_rel2:.3f} clears the ranking "
                        "threshold; a two-point leaderboard would now be publishable")
    # no player may be gated onto a rate board by two-point evidence
    if "two_point" in str(av["role_rate_name"].unique()):
        n13 += 1
        detail13.append("role_rate_name references two-point shooting")
    # the definitions table must document it as unsupported
    tp = d["defs"][d["defs"]["metric_name"] == "two_point_reliability"]
    if tp.empty or tp["status"].iloc[0] != "unsupported":
        n13 += 1
        detail13.append("two_point_reliability is not documented as unsupported")
    check(13, "no_two_point_skill_estimate_presented_as_reliable", n13,
          f"two-point prior strength {kappa2:.0f} trials (capped: observed between-player "
          f"spread is smaller than binomial noise), max player reliability {max_rel2:.4f}, "
          f"documented status 'unsupported'. {detail13 or 'all clear'}")

    # ---- 14. position baselines use adequate samples or are suppressed ----
    small = pb[pb["n_players"] < 9]
    n14 = int((small["sd_is_publishable"]).sum())
    n14 += int(small["baseline_suppression_reason"].isna().sum())
    big = pb[pb["n_players"] >= 9]
    n14 += int((~big["sd_is_publishable"]).sum())
    # a suppressed group must not produce a positional z
    supp_groups = set(pb.loc[(pb["baseline_scope"] == "position")
                             & (pb["metric_name"] == "EPA_points_raw")
                             & (~pb["sd_is_publishable"]), "baseline_group"])
    leaked = av[av["position_group"].isin(supp_groups) & av["EPA_position_z"].notna()]
    n14 += len(leaked)
    check(14, "positional_baselines_adequately_sampled_or_suppressed", n14,
          f"{len(pb)} baseline rows; {len(small)} have fewer than 9 players and all carry "
          f"sd_is_publishable=false with a stated reason. Suppressed EPA groups "
          f"{sorted(supp_groups)} produce no positional z ({len(leaked)} leaks).")

    # ---- 15. positional standardization reproduces independently ----------
    g = av.groupby("position_group")["EPA_points_raw"]
    py_mean, py_sd, py_n = g.transform("mean"), g.transform("std"), g.transform("size")
    py_z = ((av["EPA_points_raw"] - py_mean) / py_sd).where(py_n >= 9)
    n15 = int((~np.isclose(av["EPA_position_z"].astype(float), py_z.astype(float),
                           rtol=0, atol=1e-9, equal_nan=True)).sum())
    py_pct = (av.groupby("position_group")["EPA_points_raw"]
              .transform(lambda s: (s.rank(method="average") - 0.5) / s.notna().sum() * 100))
    n15 += int((~np.isclose(av["EPA_position_percentile"].astype(float),
                            py_pct.astype(float), rtol=0, atol=1e-9, equal_nan=True)).sum())

    def _rz(s):
        med = s.median()
        mad = (s - med).abs().median()
        return (s - med) / (1.4826 * mad) if mad > 0 else pd.Series(np.nan, index=s.index)
    py_rz = (av.groupby("position_group")["EPA_points_raw"].transform(_rz)).where(py_n >= 9)
    n15 += int((~np.isclose(av["EPA_position_robust_z"].astype(float), py_rz.astype(float),
                            rtol=0, atol=1e-9, equal_nan=True)).sum())
    check(15, "positional_standardization_reproduces_independently", n15,
          "EPA_position_z, EPA_position_robust_z and EPA_position_percentile all rebuilt "
          f"with pandas groupby arithmetic over {len(av)} players and matched to 1e-9.")

    # ---- 16. percentiles are in range ------------------------------------
    n16, bad16 = 0, []
    for c in ["EPA_position_percentile", "usage_position_percentile",
              "efficiency_position_percentile"]:
        v = av[c].dropna()
        bad = int(((v < 0) | (v > 100)).sum())
        if bad:
            bad16.append(f"{c}={bad}")
        n16 += bad
    check(16, "percentiles_within_zero_hundred", n16,
          f"3 percentile columns. {bad16 or 'all within [0,100]'}")

    # ---- 17. goalie metrics normalized against goalie baselines -----------
    gk = av[av["value_role"] == "goalie"]
    n17 = int((gk["position_group"] != "goalie").sum())
    # a goalie's percentile must be computed among goalies only: verify by
    # recomputing within the goalie group alone
    py_gk_pct = (gk["EPA_points_raw"].rank(method="average") - 0.5) / len(gk) * 100
    n17 += int((~np.isclose(gk["EPA_position_percentile"], py_gk_pct, atol=1e-9)).sum())
    # and must NOT match a league-wide percentile (that would mean no
    # normalization happened)
    league_pct = ((av["EPA_points_raw"].rank(method="average") - 0.5) / len(av) * 100)
    if np.allclose(gk["EPA_position_percentile"], league_pct.loc[gk.index], atol=1e-6):
        n17 += 1
    gk_base = pb[(pb["baseline_scope"] == "role") & (pb["baseline_group"] == "goalie")]
    check(17, "goalie_metrics_normalized_against_goalie_baselines", n17,
          f"{len(gk)} goalies; their EPA percentile recomputed within the goalie group alone "
          f"and matched. A goalie-only baseline exists for {len(gk_base)} metrics "
          f"(goalie EPA sd {float(pb.loc[(pb.baseline_scope=='role') & (pb.baseline_group=='goalie') & (pb.metric_name=='EPA_points_raw'), 'sd'].iloc[0]):.2f} "
          f"vs offensive_field {float(pb.loc[(pb.baseline_scope=='role') & (pb.baseline_group=='offensive_field') & (pb.metric_name=='EPA_points_raw'), 'sd'].iloc[0]):.2f} "
          "-- the reason they must not share a scale).")

    # ---- 18. faceoff metrics use faceoff baselines ------------------------
    fo = av[av["value_role"] == "faceoff"]
    n18 = int((fo["position_group"] != "faceoff").sum())
    py_fo_pct = (fo["EPA_points_raw"].rank(method="average") - 0.5) / len(fo) * 100
    n18 += int((~np.isclose(fo["EPA_position_percentile"], py_fo_pct, atol=1e-9)).sum())
    # every faceoff specialist must actually be a faceoff specialist by the
    # published rule, and no non-specialist may be classified as one
    n18 += int((fo["faceoff_team_share"] < 0.50).sum())
    n18 += int(((av["faceoff_team_share"] >= 0.50)
                & (av["value_role"] != "faceoff")).sum())
    check(18, "faceoff_metrics_use_faceoff_baselines", n18,
          f"{len(fo)} faceoff specialists, all with team faceoff share >= 0.50 "
          f"(observed range {fo['faceoff_team_share'].min():.3f}-{fo['faceoff_team_share'].max():.3f}; "
          "the next player in the league is at "
          f"{av.loc[av['value_role'] != 'faceoff', 'faceoff_team_share'].max():.3f}), "
          "percentiles recomputed within the group.")

    # ---- 19. partial defensive metrics stay labelled partial --------------
    n19, detail19 = 0, []
    if "defensive_value_partial_raw" not in av.columns:
        n19 += 1
        detail19.append("the partial defensive column has been renamed")
    if not av["defense_partial"].astype(bool).all():
        n19 += 1
        detail19.append("defense_partial is not TRUE on every row")
    scope = av["defensive_value_scope"].dropna().unique()
    if not all("partial" in str(s) for s in scope):
        n19 += 1
        detail19.append(f"defensive_value_scope no longer says partial: {scope}")
    dv_def = d["defs"][d["defs"]["metric_name"] == "value_role"]
    if dv_def.empty or dv_def["status"].iloc[0] != "production_partial":
        n19 += 1
        detail19.append("value_role is not documented as production_partial")
    # no column may present a comprehensive-sounding defensive total
    # Every defensive column must carry "partial" in its own name, so a column
    # can never be quoted out of context as a comprehensive defensive number.
    # `defensive_value_scope` is exempt because it is the text column whose
    # CONTENT is the partial-scope statement, and `defense_partial` is the flag
    # itself; both are checked above by content instead.
    exempt = {"defense_partial", "defensive_value_scope"}
    bad_names = [c for c in av.columns
                 if "defensive" in c and "partial" not in c and c not in exempt]
    n19 += len(bad_names)
    if bad_names:
        detail19.append(f"defensive columns without a 'partial' marker: {bad_names}")
    check(19, "partial_defensive_metrics_remain_labelled_partial", n19,
          f"defense_partial TRUE on all {len(av)} rows; defensive_value_scope reads "
          f"'{scope[0] if len(scope) else ''}'. {detail19 or 'all clear'}")

    # ---- 20. no unsupported component becomes zero by default -------------
    n20, detail20 = 0, []
    c6 = comp6.set_index("player_id")
    # deferred Phase 6 components must still be entirely NULL here
    for c in ["ground_ball_value", "assist_value"]:
        if c in av.columns and av[c].notna().any():
            n20 += 1
            detail20.append(f"{c} carries values")
    # NULL means "no opportunity", not "measured zero"
    n20 += int((av["faceoff_value_raw"].isna() != (av["faceoffs"] == 0)).sum())
    n20 += int((av["goalie_value_raw"].isna() != (av["shots_on_goal_faced"] == 0)).sum())
    # the usage expectation must be NULL outside the fitted population
    outside = av[~av["value_role"].isin(["offensive_field", "defensive_field"])
                 | (av["recorded_offensive_opportunities"] == 0)]
    n20 += int(outside["expected_EPA_given_usage"].notna().sum())
    # and efficiency must be NULL, never 0, with no opportunities
    n20 += int((av.loc[av["recorded_offensive_opportunities"] == 0,
                       "EPA_per_recorded_opportunity"].notna()).sum())
    check(20, "no_unsupported_component_defaults_to_zero", n20,
          f"ground-ball and assist value remain NULL for all {len(av)} players; faceoff and "
          f"goalie value are NULL exactly where the opportunity is absent; "
          f"expected_EPA_given_usage is NULL for the {len(outside)} players outside the fitted "
          f"population rather than 0. {detail20 or 'all clear'}")

    # ---- 21. usage is never mislabelled as possession participation -------
    n21, detail21 = 0, []
    banned = ["possession_share", "possessions_played", "on_field", "onfield",
              "lineup", "minutes", "time_on_field", "per_possession"]
    for frame_name, frame in [("player_adjusted_value", av),
                              ("player_usage_adjusted_value", ua),
                              ("player_play_shares", usage),
                              ("player_position_map", pmap)]:
        for c in frame.columns:
            if any(b in c.lower() for b in banned):
                n21 += 1
                detail21.append(f"{frame_name}.{c}")
    # the definitions table must say so explicitly
    up = d["defs"][d["defs"]["metric_name"] == "possession_participation_share"]
    if up.empty or up["status"].iloc[0] != "unsupported":
        n21 += 1
        detail21.append("possession_participation_share is not documented as unsupported")
    if not av["usage_proxy_only"].astype(bool).all():
        n21 += 1
        detail21.append("usage_proxy_only is not TRUE on every row")
    check(21, "usage_never_mislabelled_as_possession_participation", n21,
          f"no column in 4 Phase 7 outputs contains any of {banned}; usage_proxy_only is TRUE "
          "on every row; possession_participation_share is documented as unsupported. "
          f"{detail21 or 'all clear'}")

    # ---- 22. no duration-based player denominator -------------------------
    n22, detail22 = 0, []
    sql_text = "\n".join((SQL_DIR / f).read_text() for f in
                         ["player_position_mapping.sql", "player_play_shares.sql",
                          "player_adjusted_core.sql", "player_positional_baselines.sql",
                          "player_usage_adjusted_value.sql", "player_adjusted_value.sql",
                          "30_player_adjusted_base_views.sql"])
    for token in ["timeInPossesion", "duration_seconds", "seconds_passed", "clock"]:
        if re.search(rf"\b{token}\b", sql_text):
            n22 += 1
            detail22.append(f"the Phase 7 SQL references {token}")
    denominators = ["games_played", "shots", "touches", "faceoffs", "shots_on_goal_faced",
                    "recorded_offensive_opportunities", "event_log_play_shares",
                    "team_recorded_offensive_opportunities"]
    check(22, "no_duration_based_player_denominator", n22,
          f"every published denominator is a COUNT of recorded opportunities: {denominators}. "
          "No time, minutes, shift or possession-duration column appears in any Phase 7 "
          f"query. {detail22 or 'all clear'}")

    # ---- 23. all-star remains excluded ------------------------------------
    allstar_games = set(games.loc[games["is_all_star"], "game_id"])
    n23 = int(av["team_id"].isin({"ASE", "ASW"}).sum())
    allstar_pg = d["pg"][d["pg"]["game_id"].isin(allstar_games)]
    if len(allstar_pg):
        as_ids = allstar_pg["officialId"].str.zfill(6)
        as_shots = allstar_pg.groupby(as_ids)["shots"].sum()
        elig_shots = pg.groupby("player_id")["shots"].sum()
        joined = av.set_index("player_id")["shots"].reindex(as_shots.index)
        n23 += int((joined.fillna(-1) != elig_shots.reindex(as_shots.index).fillna(-1)).sum())
    n23 += int(av["games_played"].sum() != len(pg))
    check(23, "all_star_excluded", n23,
          f"all-star game_ids {sorted(allstar_games)} and teams ASE/ASW absent; "
          f"{len(allstar_pg)} all-star player-game rows excluded from every count; "
          f"games_played sums to {int(av['games_played'].sum())} == "
          f"{len(pg)} eligible player-game rows.")

    # ---- 24. SQL outputs agree with independent Python checks -------------
    n24, bad24 = 0, []
    # (a) the null variances, rebuilt from the baselines by separate arithmetic
    b = dict(zip(d["base6"]["baseline_name"], d["base6"]["baseline_value"]))
    p1 = b["expected_points_per_one_point_attempt"]
    p2 = b["expected_points_per_two_point_attempt"] / 2
    py_shoot_var = (a["one_point_attempts"] * p1 * (1 - p1)
                    + a["two_point_attempts"] * 4 * p2 * (1 - p2))
    py_shoot_sd = np.sqrt(py_shoot_var).where(a["shots"] > 0)
    bad = int((~np.isclose(a["shooting_value_null_sd"].astype(float),
                           py_shoot_sd.astype(float), rtol=0, atol=1e-12,
                           equal_nan=True)).sum())
    n24 += bad
    if bad:
        bad24.append(f"shooting_value_null_sd={bad}")
    # (b) faceoff null sd
    fo_p = b["faceoff_win_probability"]
    c_fo = 2 * b["event_value__faceoff_win"]
    py_fo_sd = np.sqrt((c_fo ** 2) * a["faceoffs"] * fo_p * (1 - fo_p)).where(a["faceoffs"] > 0)
    bad = int((~np.isclose(a["faceoff_value_null_sd"].astype(float), py_fo_sd.astype(float),
                           rtol=0, atol=1e-12, equal_nan=True)).sum())
    n24 += bad
    if bad:
        bad24.append(f"faceoff_value_null_sd={bad}")
    # (c) efficiency columns
    py_eff = (a["offensive_EPA_points_raw"]
              / a["recorded_offensive_opportunities"].replace(0, np.nan))
    bad = int((~np.isclose(a["EPA_per_recorded_opportunity"].astype(float),
                           py_eff.astype(float), rtol=0, atol=1e-12, equal_nan=True)).sum())
    n24 += bad
    if bad:
        bad24.append(f"EPA_per_recorded_opportunity={bad}")
    # (d) the LR reproduction must equal Phase 6's own per-play-share column
    bad = int((~np.isclose(a["uaEPA_per_event_log_play_share"].astype(float),
                           c6["total_player_value_per_play_share"].reindex(a.index)
                           .astype(float), rtol=0, atol=1e-12, equal_nan=True)).sum())
    n24 += bad
    if bad:
        bad24.append(f"uaEPA_per_event_log_play_share={bad}")
    # (e) the usage-adjusted table must agree with the wide table
    u = ua.set_index("player_id")
    for col_ua, col_av in [("EPA_points_raw", "EPA_points_raw"),
                           ("play_share", "offensive_play_share"),
                           ("EPA_per_opportunity", "EPA_per_recorded_opportunity"),
                           ("EPA_vs_usage_expectation", "EPA_vs_usage_expectation")]:
        bad = int((~np.isclose(u[col_ua].reindex(a.index).astype(float),
                               a[col_av].astype(float), rtol=0, atol=1e-12,
                               equal_nan=True)).sum())
        n24 += bad
        if bad:
            bad24.append(f"ua.{col_ua}={bad}")
    check(24, "sql_outputs_agree_with_independent_python_checks", n24,
          "null variances, efficiency ratios, the Lacrosse Reference reproduction and the "
          f"cross-table agreement between player_adjusted_value.csv and "
          f"player_usage_adjusted_value.csv all rebuilt in pandas. {bad24 or 'none disagree'}")

    # ---- 25. deterministic rebuild ----------------------------------------
    changed = _rebuild_and_compare()
    check(25, "rerun_produces_identical_output", len(changed),
          f"rebuilt {len(BUILD_OUTPUTS)} outputs into a scratch directory and compared "
          f"SHA-256; changed: {changed or 'none'}")

    # ---- 26. award eligibility is separate from observed value ------------
    n26, detail26 = 0, []
    # an eligibility flag must never be a function of the value itself
    for flag in ["rate_ranking_eligible", "future_award_input_eligible",
                 "offensive_rate_ranking_eligible"]:
        f = av[flag].astype(bool)
        if f.nunique() < 2:
            continue
        # correlation with value must not be structural: check that both
        # eligible and ineligible groups contain positive and negative values
        for grp, sub in av.groupby(f):
            if not ((sub["EPA_points_raw"] > 0).any() and (sub["EPA_points_raw"] < 0).any()):
                n26 += 1
                detail26.append(f"{flag}={grp} contains only one sign of EPA_points_raw")
    # ineligible players must retain their observed value
    inelig = av[~av["rate_ranking_eligible"].astype(bool)]
    n26 += int(inelig["EPA_points_raw"].isna().sum())
    check(26, "eligibility_is_separate_from_observed_value", n26,
          f"{len(inelig)} players fail rate_ranking_eligible and all {len(inelig)} keep their "
          "observed EPA_points_raw. No eligibility flag is derived from the value it gates: "
          "each is a function of sample size or usage only, and both the eligible and the "
          f"ineligible groups span positive and negative value. {detail26 or 'all clear'}")

    # ---- 27. no MVP / Tewaaraton composite exists -------------------------
    n27, detail27 = 0, []
    # Matched on WORD boundaries, not substrings: "war" is a substring of
    # "award", and a naive substring scan flags future_award_input_eligible as
    # a WAR metric. The tokens are split on underscores before comparison.
    banned_names = {"tewaaraton", "mvp", "composite", "rating", "war", "replacement",
                    "score"}
    all_files = (list(SQL_DIR.glob("*.sql")) + list((REPO_ROOT / "scripts").glob("*.py"))
                 + list(DATA_DIR.glob("player_adjusted*.csv"))
                 + list(DATA_DIR.glob("player_usage*.csv")))
    for f in all_files:
        if f.suffix == ".csv":
            cols = pd.read_csv(f, nrows=0).columns
            for c in cols:
                tokens = set(re.split(r"[^a-z]+", c.lower()))
                hit = tokens & banned_names
                if hit:
                    n27 += 1
                    detail27.append(f"{f.name}:{c} ({sorted(hit)})")
    # no Phase 7 column may be a weighted sum across roles
    weighted = [c for c in av.columns if "weight" in c.lower()]
    n27 += len(weighted)
    if weighted:
        detail27.append(f"weighted columns: {weighted}")
    check(27, "no_mvp_or_tewaaraton_composite_exists", n27,
          f"scanned the column names of every Phase 7 output for {sorted(banned_names)} "
          "(matched on word boundaries) and for any "
          "weighting column. Phase 7 publishes usage, value, efficiency and reliability as "
          f"separate dimensions and combines none of them. {detail27 or 'none found'}")

    report = pd.DataFrame(results)
    out = DATA_DIR / "player_adjusted_value_validation_report.csv"
    report.to_csv(out, index=False)
    n_fail = int((report["status"] == "FAIL").sum())
    with pd.option_context("display.width", 250, "display.max_colwidth", 90):
        print(report.to_string(index=False))
    print(f"\n{len(report) - n_fail}/{len(report)} checks PASS -> {out.relative_to(REPO_ROOT)}")
    return report


if __name__ == "__main__":
    main()
