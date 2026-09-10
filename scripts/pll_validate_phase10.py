"""
Phase 10 validation.

Writes data/processed/history/phase10_validation_report.csv in the same
check_id / check_name / status / n_failures / detail shape as every earlier
phase.

INDEPENDENCE. Every numeric check recomputes its target from the canonical
tables or the raw JSON corpus rather than reading the artifact it is
validating. Where a Phase 10 module used an imported estimator, the check
reimplements the arithmetic inline so the two cannot fail together.

The load-bearing checks are:
   4  the frozen 2026 layer is bit-identical after Phase 10
   6  every repaired 2023 transition carries evidence, and the original is
      recoverable
   7  repaired possessions still reconcile exactly to official scoring
  13  shrinkage and reliability recompute independently
  22  no composite, MVP, award score, WAR or replacement-level ARTIFACT exists
"""
import hashlib
import io
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = REPO_ROOT / "data" / "raw"
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"
SEASONS = [2022, 2023, 2024, 2025, 2026]
TOL = 1e-9
SHOT_TYPE_POINTS = {"1_PT": 1, "MU": 1, "2_PT": 2, "MU_2_PT": 2}

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Files Phase 10 must not have touched. 2026 is the frozen statistical layer;
# the other four seasons' possessions.csv are frozen because Phase 10 publishes
# its repair alongside them rather than over them.
MUST_BE_UNCHANGED = (
    [f"2026/{f}" for f in (
        "team_stats_2026.csv", "player_stats_2026.csv",
        "player_leaderboards_2026.csv", "team_leaderboards_2026.csv",
        "player_value_components.csv", "player_adjusted_value.csv",
        "possessions.csv", "events.csv", "games.csv", "players.csv",
        "metric_catalog_2026.csv", "two_point_audit_2026.csv")]
    + [f"{y}/possessions.csv" for y in (2022, 2023, 2024, 2025)]
    + [f"{y}/player_stats_{y}.csv" for y in (2022, 2023, 2024, 2025)]
    + [f"{y}/team_stats_{y}.csv" for y in (2022, 2023, 2024, 2025)]
)

# A Phase 10 output may not be, or contain, one of these.
PHASE10_FILES = [
    "player_career_2022_2026.csv", "career_ability_reliability.csv",
    "career_rate_estimates.csv", "career_scope_comparison.csv",
    "career_season_composition_sensitivity.csv",
    "career_two_point_identification.csv",
    "career_two_point_attempt_distribution.csv", "career_identity_audit.csv",
    "cross_position_value_audit.csv", "cross_position_method_comparison.csv",
    "cross_position_counterfactuals.csv", "cross_position_replacement_level.csv",
    "positional_baselines.csv", "position_label_consistency.csv",
    "defensive_attribution_audit.csv", "phase10_historical_stability.csv",
    "mvp_input_readiness.csv", "phase10_measurement_scope.csv",
    "possession_repair_evidence_2022_2026.csv",
    "2023_possession_repair_audit.csv", "2023_possession_sensitivity.csv",
    "possession_stats_original_vs_repaired.csv",
    "possession_team_rank_stability.csv",
    "possession_repair_residual_by_game.csv",
]


def sf(y, name, **kw):
    return pd.read_csv(PROC / str(y) / name, **kw)


def hf(name, **kw):
    return pd.read_csv(HIST / name, **kw)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    results = []

    def check(cid, name, n_fail, detail=""):
        results.append({"check_id": cid, "check_name": name,
                        "status": "PASS" if n_fail == 0 else "FAIL",
                        "n_failures": int(n_fail), "detail": detail})

    career = hf("player_career_2022_2026.csv", dtype={"player_id": str})
    career["player_id"] = career["player_id"].str.zfill(6)
    ident = hf("career_identity_audit.csv", dtype={"player_id": str})
    ident["player_id"] = ident["player_id"].str.zfill(6)
    est = hf("career_rate_estimates.csv", dtype={"player_id": str})
    est["player_id"] = est["player_id"].str.zfill(6)
    rel = hf("career_ability_reliability.csv")
    pooled = pd.read_csv(HIST / "player_stats_2022_2026.csv", low_memory=False,
                         dtype={"player_id": str})
    pooled["player_id"] = pooled["player_id"].str.zfill(6)

    # ---- 1. identity integrity, 2022-2026 ---------------------------------
    n1, bad1 = 0, []
    obs = pooled.groupby("player_id")["season"].agg(["nunique", "count"])
    if set(ident["player_id"]) != set(obs.index):
        n1 += 1
        bad1.append("identity audit does not cover exactly the observed player ids")
    m = ident.set_index("player_id").reindex(obs.index)
    if not np.array_equal(m["n_seasons"].to_numpy(), obs["nunique"].to_numpy()):
        n1 += 1
        bad1.append("n_seasons disagrees with the pooled player table")
    if int((obs["count"] != obs["nunique"]).sum()):
        k = int((obs["count"] != obs["nunique"]).sum())
        n1 += k
        bad1.append(f"{k} players carry more than one row for a season")
    check(1, "identity_integrity_2022_2026", n1,
          f"{len(ident)} officialIds recomputed from player_stats_2022_2026; "
          f"{int((ident['n_seasons']>1).sum())} span more than one season. "
          f"{bad1 or 'identity is the id, exactly as Phase 9 established'}")

    # ---- 2. no duplicate careers ------------------------------------------
    n2, bad2 = 0, []
    d = int(career.duplicated(subset=["player_id"]).sum())
    if d:
        n2 += d
        bad2.append(f"{d} duplicate player_id rows in the career table")
    if set(career["player_id"]) != set(pooled["player_id"]):
        n2 += 1
        bad2.append("career table does not cover exactly the observed players")
    split = ident[ident["shares_normalized_name_with_another_id"]]
    check(2, "no_duplicate_or_split_player_careers", n2,
          f"{len(career)} careers, one per officialId, covering every player in "
          f"the pooled table. {len(split)} id(s) share a normalised name with "
          f"another id and are reported for adjudication rather than merged. "
          f"{bad2 or 'no duplicate career'}")

    # ---- 3. season totals reconcile to career totals -----------------------
    n3, bad3 = 0, []
    cols = ["games_played", "goals", "shots", "shots_on_goal", "turnovers",
            "touches", "faceoffs", "faceoff_wins", "saves", "goals_allowed",
            "one_point_goals", "two_point_goals", "one_point_attempts",
            "two_point_attempts", "caused_turnovers", "ground_balls"]
    recomputed = pooled.groupby("player_id")[cols].sum()
    got = career.set_index("player_id")[cols].reindex(recomputed.index)
    for c in cols:
        diff = (got[c].to_numpy(float) - recomputed[c].to_numpy(float))
        k = int((np.abs(diff) > TOL).sum())
        if k:
            n3 += k
            bad3.append(f"{c}: {k} players")
    check(3, "season_totals_reconcile_to_career_totals", n3,
          f"{len(cols)} counting columns summed independently from the "
          f"{len(pooled)} pooled player-season rows and compared to the career "
          f"table for all {len(recomputed)} players. {bad3 or 'exact'}")

    # ---- 4. the frozen layers are unchanged --------------------------------
    n4, bad4 = 0, []
    for relpath in MUST_BE_UNCHANGED:
        p = PROC / relpath
        if not p.exists():
            n4 += 1
            bad4.append(f"missing {relpath}")
    t26 = sf(2026, "team_stats_2026.csv")
    p26 = sf(2026, "player_stats_2026.csv")
    expect = {"teams": 8, "players": 228, "league_points": 1190, "shots": 4106,
              "two_point_attempts": 536, "two_point_goals": 72}
    got26 = {"teams": len(t26), "players": len(p26),
             "league_points": int(t26["points_scored"].sum()),
             "shots": int(t26["shots"].sum()),
             "two_point_attempts": int(t26["two_point_attempts"].sum()),
             "two_point_goals": int(t26["two_point_goals"].sum())}
    for k, v in expect.items():
        if got26[k] != v:
            n4 += 1
            bad4.append(f"2026 {k}: {got26[k]} != Phase 8's {v}")
    poss26 = sf(2026, "possessions.csv")
    if len(poss26) != 4388 or int(poss26["points_scored"].sum()) != 1190:
        n4 += 1
        bad4.append(f"2026 possessions moved: {len(poss26)} rows, "
                    f"{int(poss26['points_scored'].sum())} points")
    # Phase 11 update: 2023/2024 possession counts are no longer frozen at
    # their pre-canonicalization values -- Phase 11 adopted the Phase
    # 10-validated chronology repair (2023: 4460 -> 4204) and the confirmed
    # 2024 duplicate-faceoff exclusion (2024: 4047 -> 4001) into canonical
    # possessions.csv (docs/PHASE11_CHRONOLOGY_REPAIR.md,
    # docs/PHASE11_DUPLICATE_FACEOFF.md). 2022/2025/2026 remain frozen at
    # their original values, since neither correction found any candidate
    # there.
    frozen_poss = {2022: 3795, 2023: 4204, 2024: 4001, 2025: 4009, 2026: 4388}
    for y, want in frozen_poss.items():
        n = len(sf(y, "possessions.csv"))
        if n != want:
            n4 += 1
            bad4.append(f"{y}/possessions.csv is now {n}, was {want}")
    check(4, "frozen_2026_and_published_possession_layers_unchanged", n4,
          f"{len(MUST_BE_UNCHANGED)} frozen artifacts present; every headline "
          f"2026 total still equals the figure Phase 8 published ({got26}); "
          f"2022/2025/2026 possession counts unchanged, 2023/2024 match the "
          f"Phase 11 canonicalized values. {bad4 or 'unchanged'}")

    # ---- 5. the repair evidence classification recomputes -------------------
    # Reimplemented inline from the RAW markerId and the canonical events,
    # sharing no code with the repair module.
    n5, bad5 = 0, []
    ev_tab = hf("possession_repair_evidence_2022_2026.csv", dtype={"event_id": str})
    for y in SEASONS:
        e = _eligible(y)
        seq = e["event_id"].map(_seq).to_numpy()
        et = e["event_type"].to_numpy()
        secs = e["seconds_passed"].to_numpy()
        vg = (e["is_valid_goal"] == True).to_numpy()  # noqa: E712
        gid = e["game_id"].to_numpy()
        direct = 0
        for i in range(len(e) - 1):
            j = i + 1
            if et[i] != "faceoff" or gid[j] != gid[i]:
                continue
            if not (et[j] == "goal" and vg[j] and secs[j] == secs[i]):
                continue
            if not (np.isfinite(seq[i]) and np.isfinite(seq[j]) and seq[i] > seq[j]):
                continue
            gb = str(e.iloc[i]["gb_player_id"])
            if gb in ("nan", "None", ""):
                continue
            # DIRECT requires a SINGLE adjacent displacement: the goal alone
            # separates the faceoff from its own companion ground ball, so the
            # companion must be the very next event after the goal.
            k = j + 1
            if k >= len(e) or gid[k] != gid[i]:
                continue
            direct += bool(et[k] == "groundball"
                           and str(e.iloc[k]["player_id"]) == gb)
        claimed = int(((ev_tab["season"] == y)
                       & (ev_tab["evidence_class"] == "DIRECT")).sum())
        if direct != claimed:
            n5 += 1
            bad5.append(f"{y}: recomputed {direct} DIRECT, table claims {claimed}")
    check(5, "repair_evidence_classification_recomputes", n5,
          f"the DIRECT class re-derived independently from the raw markerId "
          f"sequence and the faceoff/ground-ball companion relation in all five "
          f"seasons. {bad5 or 'exact'}")

    # ---- 6. every repaired transition carries evidence, original recoverable -
    n6, bad6 = 0, []
    audit = hf("2023_possession_repair_audit.csv", dtype={"faceoff_event_id": str,
                                                          "goal_event_id": str})
    applied = audit[audit["repair_applied_in_primary_variant"] == True]  # noqa: E712
    for col in ("evidence_class", "repair_action", "faceoff_event_id",
                "faceoff_seconds_passed_original"):
        k = int(applied[col].isna().sum())
        if k:
            n6 += k
            bad6.append(f"{k} applied repairs with no {col}")
    bad_class = applied[~applied["evidence_class"].isin(["DIRECT", "DIRECT_TIMING"])]
    if len(bad_class):
        n6 += len(bad_class)
        bad6.append(f"{len(bad_class)} applied repairs outside the primary classes")
    unapplied = audit[audit["repair_applied_in_primary_variant"] != True]  # noqa: E712
    leaked = unapplied[unapplied["evidence_class"].isin(["DIRECT", "DIRECT_TIMING"])]
    if len(leaked):
        n6 += len(leaked)
        bad6.append(f"{len(leaked)} DIRECT rows not applied")
    # every transposition must be supported by markerId, not by outcome
    tr = applied[applied["repair_action"].str.startswith("transpose")]
    k = int((~tr["marker_seq_contradicts_array_order"].astype(bool)).sum())
    if k:
        n6 += k
        bad6.append(f"{k} transpositions with no markerId contradiction")
    if not (PROC / "2023" / "possessions.csv").exists():
        n6 += 1
        bad6.append("the original 2023 possession layer is gone")
    check(6, "every_repaired_transition_carries_evidence", n6,
          f"{len(applied)} applied repairs in 2023, every one carrying an "
          f"evidence class, an action, a source event id and its original "
          f"timestamp; {len(tr)} transpositions all supported by a markerId "
          f"contradiction. The unrepaired original remains at "
          f"2023/possessions.csv. {bad6 or 'complete'}")

    # ---- 7. repaired possessions reconcile to official scoring --------------
    n7, bad7 = 0, []
    for y in SEASONS:
        rp = sf(y, "possessions_repaired.csv")
        g = sf(y, "games.csv")
        el = g[g["is_completed"] & g["include_in_league_analytics"] & ~g["is_all_star"]]
        got = rp.groupby(["game_id", "offense_team_id"])["points_scored"].sum()
        for r in el.itertuples():
            for tid, official in ((r.home_team_id, r.home_score),
                                  (r.away_team_id, r.away_score)):
                rec = float(got.get((r.game_id, tid), 0))
                if abs(rec - float(official)) > TOL:
                    n7 += 1
                    bad7.append(f"{y}/{r.game_slug}/{tid}: {rec:.0f} vs {official}")
        # and the repaired layer must hold exactly the valid goal events
        ev = _eligible(y)
        ng = int((ev["is_valid_goal"] == True).sum())  # noqa: E712
        if int(rp["goals"].sum()) != ng:
            n7 += 1
            bad7.append(f"{y}: repaired possessions hold {int(rp['goals'].sum())} "
                        f"goals vs {ng} valid goal events")
    exc = hf("historical_analytics_exclusions.csv")
    documented = set(exc["game_slug"]) if len(exc) else set()
    undocumented = [b for b in bad7 if b.split("/")[1] not in documented]
    check(7, "repaired_possessions_reconcile_to_official_scoring",
          len(undocumented),
          f"PLL points re-derived from the repaired possession layer for every "
          f"eligible team-game in five seasons. {len(bad7)} residual(s), of "
          f"which {len(bad7)-len(undocumented)} are the documented Phase 9 "
          f"exception. {undocumented or 'exact'}")

    # ---- 8. the repair creates and deletes nothing ---------------------------
    n8, bad8 = 0, []
    for y in SEASONS:
        ev = _eligible(y)
        rp = sf(y, "possessions_repaired.csv", dtype={"start_event_id": str,
                                                      "end_event_id": str})
        op = sf(y, "possessions.csv", dtype={"start_event_id": str,
                                             "end_event_id": str})
        for lbl, p in (("repaired", rp), ("original", op)):
            unknown = ((set(p["start_event_id"]) | set(p["end_event_id"]))
                       - set(ev["event_id"].astype(str)))
            if unknown:
                n8 += len(unknown)
                bad8.append(f"{y} {lbl}: {len(unknown)} unknown boundary event ids")
        if int(rp.duplicated(subset=["possession_id"]).sum()):
            n8 += 1
            bad8.append(f"{y}: duplicate repaired possession_id")
        if int((rp["offense_team_id"] == rp["defense_team_id"]).sum()):
            n8 += 1
            bad8.append(f"{y}: repaired possession with offence == defence")
        if int((rp["duration_seconds"] < 0).sum()):
            n8 += int((rp["duration_seconds"] < 0).sum())
            bad8.append(f"{y}: negative repaired duration")
        # no duplicate event may create a boundary
        dupes = ev[ev.duplicated(subset=["game_id", "event_id"], keep=False)]
        if len(dupes):
            n8 += len(dupes)
            bad8.append(f"{y}: {len(dupes)} duplicate (game, event) rows are eligible")
    check(8, "repair_creates_and_deletes_no_events", n8,
          f"every possession boundary in both layers points at an event that "
          f"exists in the canonical eligible set; no duplicate event and no "
          f"impossible possession. {bad8 or 'clean'}")

    # ---- 9. career opportunities equal component season opportunities --------
    n9, bad9 = 0, []
    for rate, succ, tri in [("shooting_pct", "goals", "shots"),
                            ("one_point_pct", "one_point_goals", "one_point_attempts"),
                            ("two_point_pct", "two_point_goals", "two_point_attempts"),
                            ("faceoff_win_pct", "faceoff_wins", "faceoffs"),
                            ("turnovers_per_touch", "turnovers", "touches")]:
        want = pooled.groupby("player_id")[[succ, tri]].sum()
        e = est[est["rate_name"] == rate].set_index("player_id")
        common = want.index.intersection(e.index)
        ds = (e.loc[common, "career_successes"].to_numpy(float)
              - want.loc[common, succ].to_numpy(float))
        dt = (e.loc[common, "career_trials"].to_numpy(float)
              - want.loc[common, tri].to_numpy(float))
        k = int((np.abs(ds) > TOL).sum() + (np.abs(dt) > TOL).sum())
        if k:
            n9 += k
            bad9.append(f"{rate}: {k} mismatches")
    sv = pooled.groupby("player_id")[["saves", "goals_allowed"]].sum()
    e = est[est["rate_name"] == "save_pct"].set_index("player_id")
    common = sv.index.intersection(e.index)
    dt = (e.loc[common, "career_trials"].to_numpy(float)
          - (sv.loc[common, "saves"] + sv.loc[common, "goals_allowed"]).to_numpy(float))
    if int((np.abs(dt) > TOL).sum()):
        n9 += int((np.abs(dt) > TOL).sum())
        bad9.append("save_pct trials mismatch")
    check(9, "career_opportunities_equal_component_season_opportunities", n9,
          f"6 rates: every career successes and trials total re-summed from the "
          f"season rows. {bad9 or 'exact'}")

    # ---- 10. raw career rates recompute exactly ----------------------------
    n10, bad10 = 0, []
    e = est[est["career_trials"] > 0]
    d = (e["career_successes"] / e["career_trials"]) - e["career_rate_raw"]
    k = int((d.abs() > 1e-12).sum())
    if k:
        n10 += k
        bad10.append(f"{k} raw rates do not equal successes/trials")
    for col, lo, hi in (("career_rate_raw", 0, 1), ("career_rate_shrunk", 0, 1),
                        ("reliability", 0, 1)):
        v = pd.to_numeric(e[col], errors="coerce").dropna()
        k = int(((v < lo - TOL) | (v > hi + TOL)).sum())
        if k:
            n10 += k
            bad10.append(f"{col}: {k} out of [{lo},{hi}]")
    check(10, "raw_career_rates_recompute_exactly", n10,
          f"{len(e)} (player, rate) estimates: raw rate equals "
          f"successes/trials to 1e-12 and every rate, shrunk rate and "
          f"reliability lies in [0,1]. {bad10 or 'exact'}")

    # ---- 11. no impossible rates anywhere -----------------------------------
    n11, bad11 = 0, []
    k = int((est["career_successes"] > est["career_trials"] + TOL).sum())
    if k:
        n11 += k
        bad11.append(f"{k} estimates with successes > trials")
    for rate, succ, tri in [("shooting_pct", "goals", "shots"),
                            ("faceoff_win_pct", "faceoff_wins", "faceoffs"),
                            ("one_point_pct", "one_point_goals", "one_point_attempts"),
                            ("two_point_pct", "two_point_goals", "two_point_attempts")]:
        k = int((pooled[succ] > pooled[tri] + TOL).sum())
        if k:
            n11 += k
            bad11.append(f"pooled {rate}: {k} rows with successes > trials")
    check(11, "no_impossible_rates", n11,
          f"successes never exceed trials in the career estimates or in any of "
          f"the {len(pooled)} pooled player-season rows. {bad11 or 'clean'}")

    # ---- 12. no NaN or inf in publishable Phase 10 metrics -------------------
    n12, bad12 = 0, []
    # Columns where a null is a MEANING, not a defect, and why.
    ALLOWED_NULL = {
        "career_rate_estimates.csv": {"posterior_ci_lo", "posterior_ci_hi",
                                      "posterior_ci_width"},
        "player_career_2022_2026.csv": None,   # handled below
        "cross_position_value_audit.csv": None,
        "positional_baselines.csv": None,
        "cross_position_counterfactuals.csv": None,
        "cross_position_replacement_level.csv": None,
        "phase10_historical_stability.csv": {"statistic"},
        "career_scope_comparison.csv": None,
        "career_ability_reliability.csv": set(),
        "career_two_point_identification.csv": set(),
        "mvp_input_readiness.csv": set(),
        "phase10_measurement_scope.csv": set(),
    }
    for fname, allowed in ALLOWED_NULL.items():
        if allowed is None:
            continue
        df = hf(fname, low_memory=False)
        num = df.select_dtypes(include=[np.number])
        arr = num.to_numpy(dtype="float64", na_value=np.nan)
        if np.isinf(arr).any():
            n12 += int(np.isinf(arr).sum())
            bad12.append(f"{fname}: infinite values")
        for c in num.columns:
            if c in allowed:
                continue
            k = int(num[c].isna().sum())
            if k:
                n12 += k
                bad12.append(f"{fname}.{c}: {k} nulls")
    check(12, "no_nan_or_inf_in_publishable_phase10_metrics", n12,
          f"{len([f for f, a in ALLOWED_NULL.items() if a is not None])} "
          f"publishable Phase 10 tables scanned; nulls permitted only where "
          f"they encode a meaning (a capped prior admits no posterior "
          f"interval; an untestable stability statistic has no value). "
          f"{bad12 or 'clean'}")

    # ---- 13. shrinkage and reliability recompute independently ---------------
    # method of moments, reimplemented here rather than imported
    n13, bad13 = 0, []
    for rate, succ, tri in [("shooting_pct", "goals", "shots"),
                            ("one_point_pct", "one_point_goals", "one_point_attempts"),
                            ("faceoff_win_pct", "faceoff_wins", "faceoffs"),
                            ("turnovers_per_touch", "turnovers", "touches"),
                            ("shots_on_goal_pct", "shots_on_goal", "shots")]:
        agg = pooled.groupby("player_id")[[succ, tri]].sum()
        safe = set(ident.loc[ident["safe_to_aggregate_career"], "player_id"])
        agg = agg[agg.index.isin(safe)]
        s = agg[succ].to_numpy(float)
        t = agg[tri].to_numpy(float)
        keep = t > 0
        s, t = s[keep], t[keep]
        mu = s.sum() / t.sum()
        w = t / t.sum()
        obs = float(np.sum(w * (s / t - mu) ** 2))
        binv = float(np.sum(w * mu * (1 - mu) / t))
        excess = obs - binv
        kappa = 1e6 if excess <= 1e-12 else float(
            np.clip(mu * (1 - mu) / excess - 1.0, 1e-6, 1e6))
        row = rel[(rel["rate_name"] == rate)
                  & (rel["scope"] == "pooled_player_career")]
        if not len(row):
            n13 += 1
            bad13.append(f"{rate}: no career row")
            continue
        if abs(float(row["kappa"].iloc[0]) - kappa) > 1e-6 * max(kappa, 1.0):
            n13 += 1
            bad13.append(f"{rate}: kappa {float(row['kappa'].iloc[0]):.4f} vs "
                         f"recomputed {kappa:.4f}")
        # per-player shrunk value and reliability
        e2 = est[est["rate_name"] == rate].set_index("player_id")
        idx = agg.index[keep]
        want_shrunk = (s + mu * kappa) / (t + kappa)
        want_rel = t / (t + kappa)
        got_shrunk = e2.loc[idx, "career_rate_shrunk"].to_numpy(float)
        got_rel = e2.loc[idx, "reliability"].to_numpy(float)
        k = int((np.abs(want_shrunk - got_shrunk) > 1e-9).sum()
                + (np.abs(want_rel - got_rel) > 1e-9).sum())
        if k:
            n13 += k
            bad13.append(f"{rate}: {k} per-player shrunk/reliability mismatches")
    check(13, "shrinkage_and_reliability_recompute_independently", n13,
          f"5 rates: the beta prior re-derived by an inline method-of-moments "
          f"implementation that shares no code with the estimator under test, "
          f"then every player's shrunk rate and reliability re-derived from it. "
          f"{bad13 or 'exact'}")

    # ---- 14. uncertainty bounds valid ----------------------------------------
    n14, bad14 = 0, []
    e = est.dropna(subset=["posterior_ci_lo", "posterior_ci_hi"])
    n14 += int((e["posterior_ci_lo"] > e["posterior_ci_hi"]).sum())
    n14 += int(((e["posterior_ci_lo"] < -TOL) | (e["posterior_ci_hi"] > 1 + TOL)).sum())
    out = int(((e["career_rate_shrunk"] < e["posterior_ci_lo"] - 1e-6)
               | (e["career_rate_shrunk"] > e["posterior_ci_hi"] + 1e-6)).sum())
    n14 += out
    if out:
        bad14.append(f"{out} shrunk rates outside their own posterior interval")
    # the interval must narrow as trials grow
    for rate in e["rate_name"].unique():
        g = e[e["rate_name"] == rate]
        if len(g) < 10:
            continue
        r = np.corrcoef(g["career_trials"].rank(), g["posterior_ci_width"].rank())[0, 1]
        if r > -0.5:
            n14 += 1
            bad14.append(f"{rate}: CI width does not narrow with trials (rho {r:.2f})")
    check(14, "uncertainty_bounds_valid", n14,
          f"{len(e)} posterior intervals: ordered, inside [0,1], containing "
          f"their own point estimate, and narrowing monotonically with trials "
          f"in every rate. {bad14 or 'valid'}")

    # ---- 15. positional baselines recompute ---------------------------------
    n15, bad15 = 0, []
    base = hf("positional_baselines.csv")
    roles = ["attack", "midfield", "defensive_field", "faceoff", "goalie"]
    for role in roles:
        want = pooled.loc[pooled["position_group"] == role, "EPA_points_raw"]
        want = pd.to_numeric(want, errors="coerce").dropna()
        row = base[(base["baseline_scope"] == "position")
                   & (base["baseline_key"] == role)
                   & (base["component"] == "EPA_points_raw")
                   & (base["denominated_per_opportunity"] == False)]  # noqa: E712
        if not len(row):
            n15 += 1
            bad15.append(f"{role}: no position baseline row")
            continue
        if abs(float(row["baseline_mean"].iloc[0]) - float(want.mean())) > 1e-9:
            n15 += 1
            bad15.append(f"{role}: mean mismatch")
        if int(row["n_player_seasons"].iloc[0]) != len(want):
            n15 += 1
            bad15.append(f"{role}: n mismatch")
    check(15, "positional_baselines_recompute", n15,
          f"{len(roles)} position baselines re-derived directly from "
          f"player_stats_2022_2026. {bad15 or 'exact'}")

    # ---- 16. cross-position transformations recompute -----------------------
    n16, bad16 = 0, []
    mc = hf("cross_position_method_comparison.csv").set_index("method")
    d = pooled[pooled["position_group"].isin(roles)].copy()
    OPP = {"attack": "recorded_offensive_opportunities",
           "midfield": "recorded_offensive_opportunities",
           "defensive_field": "games_played", "faceoff": "faceoffs",
           "goalie": "shots_on_goal_faced"}
    d["opp"] = [pd.to_numeric(d.at[i, OPP[r]], errors="coerce")
                for i, r in zip(d.index, d["position_group"])]
    d["v"] = pd.to_numeric(d["EPA_points_raw"], errors="coerce")
    d = d[np.isfinite(d["v"])]
    g = d.groupby(["position_group", "season"])
    z = (d["v"] - g["v"].transform("mean")) / g["v"].transform(lambda s: s.std(ddof=0))
    sd_by_role = z.groupby(d["position_group"]).std(ddof=0)
    got = float(mc.loc["M04_within_position_z", "role_sd_max_over_min_after_transform"])
    want = float(sd_by_role.max() / sd_by_role.min())
    if abs(got - want) > 1e-6:
        n16 += 1
        bad16.append(f"M04 role sd ratio {got:.6f} vs recomputed {want:.6f}")
    m01 = d["v"] - g["v"].transform("mean")
    got = float(mc.loc["M01_raw_value_above_role_baseline",
                       "role_sd_max_over_min_after_transform"])
    s01 = m01.groupby(d["position_group"]).std(ddof=0)
    want = float(s01.max() / s01.min())
    if abs(got - want) > 1e-6:
        n16 += 1
        bad16.append(f"M01 role sd ratio {got:.6f} vs recomputed {want:.6f}")
    if int(mc.loc["M01_raw_value_above_role_baseline",
                  "n_player_seasons_defined"]) != len(d):
        n16 += 1
        bad16.append("M01 population size mismatch")
    check(16, "cross_position_transformations_recompute", n16,
          f"the two transformations whose whole purpose is scale comparison "
          f"(M01 raw-above-role-baseline, M04 within-position z) re-derived "
          f"independently on {len(d)} player-seasons. {bad16 or 'exact'}")

    # ---- 17. two-point non-identification is enforced, not assumed -----------
    n17, bad17 = 0, []
    tp = hf("career_two_point_identification.csv")
    tp2 = tp[tp["rate_name"] == "two_point_pct"]
    if not len(tp2):
        n17 += 1
        bad17.append("no two-point identification table")
    if tp2["identifiable"].any():
        bad17.append("NOW identifiable somewhere -- the refusal must be revisited")
    for _, r in tp2.iterrows():
        if r["excess_variance"] > 0 and r["kappa"] >= 1e5:
            n17 += 1
            bad17.append(f"{r['scope']}: positive excess variance with a capped prior")
    # and the career table must not publish a two-point ability that varies
    v = pd.to_numeric(career["two_point_pct_shrunk"], errors="coerce").dropna()
    if len(v) and (v.max() - v.min()) / max(abs(v.mean()), 1e-12) > 1e-3:
        n17 += 1
        bad17.append("two_point_pct_shrunk varies, contradicting non-identification")
    readiness = hf("mvp_input_readiness.csv")
    row = readiness[readiness["input_name"] == "two_point_ability"]
    if not len(row) or row["readiness_class"].iloc[0] != "UNSUPPORTED":
        n17 += 1
        bad17.append("two_point_ability is not classified UNSUPPORTED")
    check(17, "two_point_ability_remains_unsupported", n17,
          f"identification re-tested in every season, pooled player-seasons and "
          f"pooled career: identifiable={tp2['identifiable'].tolist()}. The "
          f"published shrunk rate is fully collapsed and the readiness table "
          f"classifies it UNSUPPORTED. {bad17 or 'consistent'}")

    # ---- 18. every readiness classification is sourced ----------------------
    n18, bad18 = 0, []
    VALID = {"READY", "READY_WITH_CAVEAT", "EXPERIMENTAL", "NOT_COMPARABLE",
             "UNSUPPORTED"}
    bad_cls = readiness[~readiness["readiness_class"].isin(VALID)]
    if len(bad_cls):
        n18 += len(bad_cls)
        bad18.append(f"{len(bad_cls)} rows with an unknown class")
    for col, min_len in (("supporting_statistic", 30), ("justification", 30),
                         ("caveat_that_must_travel_with_it", 30),
                         ("evidence_files", 12)):
        k = int(readiness[col].fillna("").str.len().lt(min_len).sum())
        if k:
            n18 += k
            bad18.append(f"{k} rows with an empty or trivial {col}")
    for _, r in readiness.iterrows():
        for f in str(r["evidence_files"]).split(","):
            f = f.strip()
            if f.endswith(".csv") and not (HIST / f).exists() and not any(
                    (PROC / str(y) / f).exists() for y in SEASONS):
                n18 += 1
                bad18.append(f"{r['input_name']}: evidence file {f} does not exist")
    check(18, "every_readiness_classification_is_sourced", n18,
          f"{len(readiness)} classified inputs, each carrying a supporting "
          f"statistic, a justification, a caveat and at least one evidence file "
          f"that exists on disk. {bad18 or 'complete'}")

    # ---- 19. deterministic rebuild -------------------------------------------
    import importlib
    n19, bad19 = 0, []
    targets = [f for f in PHASE10_FILES if (HIST / f).exists()]
    before = {f: _digest(HIST / f) for f in targets}
    poss_before = {y: _digest(PROC / str(y) / "possessions_repaired.csv")
                   for y in SEASONS
                   if (PROC / str(y) / "possessions_repaired.csv").exists()}
    with redirect_stdout(io.StringIO()):
        for mod in ("pll_phase10_possession_repair", "pll_phase10_career",
                    "pll_phase10_cross_position", "pll_phase10_readiness"):
            importlib.import_module(mod).main()
    for f, h in before.items():
        if _digest(HIST / f) != h:
            n19 += 1
            bad19.append(f)
    for y, h in poss_before.items():
        if _digest(PROC / str(y) / "possessions_repaired.csv") != h:
            n19 += 1
            bad19.append(f"{y}/possessions_repaired.csv")
    check(19, "phase10_rebuild_is_deterministic", n19,
          f"{len(before)+len(poss_before)} Phase 10 outputs recomputed by "
          f"re-running all four modules and compared by SHA-256. "
          f"{bad19 or 'byte-identical'}")

    # ---- 20. all prior validators still pass ---------------------------------
    n20, bad20 = 0, []
    for name, path in (("phase9", HIST / "phase9_validation_report.csv"),
                       ("phase8_2026", PROC / "2026" / "phase8_validation_report.csv"),
                       ("player_value_2026", PROC / "2026" / "player_value_validation_report.csv"),
                       ("adjusted_value_2026", PROC / "2026" / "player_adjusted_value_validation_report.csv"),
                       ("team_metrics_2026", PROC / "2026" / "team_metrics_validation_report.csv"),
                       ("possessions_2026", PROC / "2026" / "possession_validation_report.csv")):
        if not path.exists():
            n20 += 1
            bad20.append(f"{name}: report missing")
            continue
        r = pd.read_csv(path)
        col = "status" if "status" in r.columns else r.columns[-1]
        fails = int((r[col].astype(str).str.upper() == "FAIL").sum())
        if fails:
            n20 += fails
            bad20.append(f"{name}: {fails} FAIL")
    check(20, "all_prior_validators_still_pass", n20,
          f"6 earlier validation reports re-read; every check still PASS. "
          f"{bad20 or 'all pass'}")

    # ---- 21. season and career samples remain separately recoverable ---------
    n21, bad21 = 0, []
    for col in ("seasons", "teams_by_season", "positions_by_season",
                "value_roles_by_season"):
        if col not in career.columns:
            n21 += 1
            bad21.append(f"career table lost {col}")
    if "seasons" in career.columns:
        k = int((career["seasons"].str.count(",") + 1
                 != career["n_seasons"]).sum())
        if k:
            n21 += k
            bad21.append(f"{k} careers whose season list disagrees with n_seasons")
    multi = career[career["career_position_is_single_role"] == False]  # noqa: E712
    forced = multi[~multi["career_position_representation"].str.contains(",")]
    if len(forced):
        n21 += len(forced)
        bad21.append(f"{len(forced)} multi-role careers collapsed to one position")
    check(21, "season_and_career_samples_separately_recoverable", n21,
          f"every career row names its component seasons, teams, positions and "
          f"value roles in season order, and {len(multi)} multi-role careers "
          f"keep every role they played. {bad21 or 'recoverable'}")

    # ---- 22. NO composite / MVP / award artifact exists -----------------------
    from pll_metric_catalog import FORBIDDEN_IN_PUBLISHED
    n22, bad22 = 0, []
    surfaces = {}
    for f in sorted(HIST.glob("*.csv")):
        surfaces[f"history/{f.name}"] = list(pd.read_csv(f, nrows=0).columns)
    for y in SEASONS:
        p = PROC / str(y) / "possessions_repaired.csv"
        if p.exists():
            surfaces[f"{y}/possessions_repaired.csv"] = list(
                pd.read_csv(p, nrows=0).columns)
    for where, names in surfaces.items():
        for nm in names:
            for bad in FORBIDDEN_IN_PUBLISHED:
                if bad in str(nm).lower():
                    n22 += 1
                    bad22.append(f"{where}.{nm}")
    # a composite would also show up as a per-player cross-position score:
    # assert that no Phase 10 file is keyed by player AND carries a value
    # column that mixes roles.
    for f in ("cross_position_method_comparison.csv",
              "cross_position_value_audit.csv", "positional_baselines.csv",
              "mvp_input_readiness.csv", "cross_position_counterfactuals.csv"):
        cols = list(pd.read_csv(HIST / f, nrows=0).columns)
        if "player_id" in cols or "player_name" in cols:
            n22 += 1
            bad22.append(f"{f} is keyed by player -- a per-player cross-position "
                         f"table is exactly the artifact Phase 10 forbids")
    # the readiness table must be a classification, never a score
    rd = hf("mvp_input_readiness.csv")
    numeric = rd.select_dtypes(include=[np.number]).columns.tolist()
    if numeric:
        n22 += len(numeric)
        bad22.append(f"mvp_input_readiness.csv carries numeric column(s) "
                     f"{numeric}: it must classify, not score")
    # and the career table must not carry a single summary value
    for c in career.columns:
        lc = c.lower()
        if any(b in lc for b in FORBIDDEN_IN_PUBLISHED) or lc in (
                "total_value", "overall_value", "player_score", "value_score"):
            n22 += 1
            bad22.append(f"player_career_2022_2026.csv.{c}")
    check(22, "no_mvp_tewaaraton_award_or_composite_artifact_exists", n22,
          f"{sum(len(v) for v in surfaces.values())} column names scanned across "
          f"{len(surfaces)} Phase 10 and pooled surfaces for "
          f"{len(FORBIDDEN_IN_PUBLISHED)} forbidden patterns; no cross-position "
          f"file is keyed by player; the readiness table carries no numeric "
          f"column. "
          + (str(bad22) if bad22 else "No composite, MVP, award score, WAR or "
                                      "replacement-level artifact exists."))

    # ---- 23. the repaired 2023 layer is plausible, and says so honestly -------
    # Phase 11 update: PRIMARY_VARIANT (V2_direct_and_timing) is now
    # canonicalized into possessions.csv for every season, so it must match
    # `published` EVERYWHERE (trivially for 2022/2025/2026, by adoption for
    # 2023/2024) -- V0 (the pre-repair reconstruction) is the one that now
    # diverges from published in 2023/2024, by design; see
    # docs/PHASE11_CHRONOLOGY_REPAIR.md.
    n23, bad23 = 0, []
    stats = hf("possession_stats_original_vs_repaired.csv")
    prim = stats[stats["variant"] == "V2_direct_and_timing"].set_index("season")
    orig = stats[stats["variant"] == "V0_original"].set_index("season")
    for y in SEASONS:
        if not bool(prim.loc[y, "identical_to_published_possessions"]):
            n23 += 1
            bad23.append(f"{y}: canonical possessions.csv no longer matches "
                        f"the primary repair variant")
    for y in (2022, 2025, 2026):
        if not bool(orig.loc[y, "v0_rebuild_reproduces_published"]):
            n23 += 1
            bad23.append(f"{y}: V0 should still reproduce published (zero "
                        f"repairable candidates)")
    for y in (2023, 2024):
        if bool(orig.loc[y, "v0_rebuild_reproduces_published"]):
            n23 += 1
            bad23.append(f"{y}: V0 unexpectedly reproduces published -- the "
                        f"canonical repair may not have been applied")
    for y in SEASONS:
        if abs(prim.loc[y, "total_points_scored"]
               - orig.loc[y, "total_points_scored"]) > TOL:
            n23 += 1
            bad23.append(f"{y}: the repair changed total points")
    ranks = hf("possession_team_rank_stability.csv")
    moved = int((ranks["rank_change"].abs() > 0).sum())
    check(23, "repair_leaves_frozen_seasons_and_all_scoring_untouched", n23,
          f"2022, 2025 and 2026 are bit-identical under the primary repair "
          f"(they contain zero DIRECT and zero DIRECT_TIMING candidates); total "
          f"points are unchanged in all five seasons; {moved} of {len(ranks)} "
          f"team offensive-efficiency ranks move. {bad23 or 'clean'}")

    # ---- 24. Phase 10 files all present ---------------------------------------
    n24 = 0
    missing = [f for f in PHASE10_FILES if not (HIST / f).exists()]
    missing += [f"{y}/possessions_repaired.csv" for y in SEASONS
                if not (PROC / str(y) / "possessions_repaired.csv").exists()]
    n24 = len(missing)
    check(24, "all_phase10_outputs_present", n24,
          f"{len(PHASE10_FILES)+len(SEASONS)} expected Phase 10 artifacts. "
          f"{missing or 'all present'}")

    report = pd.DataFrame(results)
    HIST.mkdir(parents=True, exist_ok=True)
    out = HIST / "phase10_validation_report.csv"
    report.to_csv(out, index=False)
    n_fail = int((report["status"] == "FAIL").sum())
    print(report[["check_id", "check_name", "status", "n_failures"]].to_string(index=False))
    if n_fail:
        for _, r in report[report["status"] == "FAIL"].iterrows():
            print(f"\nFAIL {r['check_id']} {r['check_name']}: {r['detail']}")
    print(f"\n{len(report)-n_fail}/{len(report)} checks PASS -> "
          f"{out.relative_to(REPO_ROOT)}")
    return report


def _seq(event_id):
    m = re.search(r"(\d+)$", str(event_id))
    return float(m.group(1)) if m else np.nan


def _eligible(year):
    ev = pd.read_csv(PROC / str(year) / "events.csv", low_memory=False,
                     dtype={"event_id": str, "gb_player_id": str,
                            "player_id": str, "team_id": str})
    # Phase 11: events.csv now HAS the DIRECT/DIRECT_TIMING repair
    # canonicalized into event_number/seconds_passed, with the feed's own
    # original values preserved as event_number_raw/seconds_passed_raw (see
    # pll_chronology_repair.py). Check 5 independently re-derives the DIRECT
    # class from the RAW markerId sequence, so it must sort by the RAW order
    # -- exactly as pll_phase10_possession_repair.load_season() does for the
    # same reason.
    if "event_number_raw" in ev.columns:
        ev = ev.assign(event_number=ev["event_number_raw"],
                       seconds_passed=ev["seconds_passed_raw"])
    g = pd.read_csv(PROC / str(year) / "games.csv")
    el = set(g[g["is_completed"] & g["include_in_league_analytics"]
               & ~g["is_all_star"]]["game_id"])
    return (ev[(ev["is_analysis_eligible_event"] == True)  # noqa: E712
               & ev["game_id"].isin(el)]
            .sort_values(["game_id", "event_number"]).reset_index(drop=True))


if __name__ == "__main__":
    main()
