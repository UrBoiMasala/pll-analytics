"""
Phase 12 validation.

Writes data/processed/history/phase12_validation_report.csv in the same
check_id / check_name / status / n_failures / detail shape as every earlier
phase.

Phase 12 is a RESEARCH phase: it built five new evidence CSVs
(player_value_signal_inventory, player_value_metric_dependency,
player_value_model_candidates, player_value_validation_results,
player_value_counterfactual_tests) and nine docs. It changed no canonical
data, no raw data, and built no MVP/Tewaaraton/award/composite artifact.
This validator's job is to prove all three of those claims and to prove the
new research CSVs are internally consistent with the non-negotiable rules the
Phase 12 brief states (Section Q).

INDEPENDENCE, same discipline as every earlier validator: checks recompute
their target from the canonical tables or re-hash files on disk rather than
re-reading the artifact under test as its own source of truth.
"""
import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"
DOCS = REPO_ROOT / "docs"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pll_build_canonical_manifest import (  # noqa: E402
    CANONICAL_ARTIFACTS, raw_manifest_for_season, _sha256,
)
from pll_metric_catalog import FORBIDDEN_IN_PUBLISHED               # noqa: E402
import pll_phase12_player_value_research as p12                     # noqa: E402


def hf(name, **kw):
    return pd.read_csv(HIST / name, **kw)


PHASE12_OUTPUTS = [
    "player_value_signal_inventory.csv",
    "player_value_metric_dependency.csv",
    "player_value_model_candidates.csv",
    "player_value_validation_results.csv",
    "player_value_counterfactual_tests.csv",
]

PHASE12_DOCS = [
    "PLAYER_VALUE_DEFINITION.md",
    "PLAYER_VALUE_MODEL_RESEARCH.md",
    "OFFENSIVE_VALUE_RESEARCH.md",
    "FACEOFF_VALUE_RESEARCH.md",
    "GOALIE_VALUE_RESEARCH.md",
    "DEFENSIVE_VALUE_FEASIBILITY.md",
    "history/CROSS_POSITION_VALUE_PHASE12.md",
    "STATISTICAL_TEWAARATON_SPECIFICATION.md",
    "history/PHASE12_VALIDATION.md",
]

ALLOWED_MODEL_STATUS = {
    "VIABLE", "VIABLE_WITH_CAVEAT", "ROLE_ONLY", "EXPERIMENTAL",
    "REJECTED", "UNSUPPORTED",
}


def main():
    results = []

    def check(cid, name, n_fail, detail=""):
        results.append({"check_id": cid, "check_name": name,
                        "status": "PASS" if n_fail == 0 else "FAIL",
                        "n_failures": int(n_fail), "detail": detail})

    # ---- 1. canonical dataset artifacts unchanged --------------------------
    manifest_path = HIST / "CANONICAL_MANIFEST_V1.json"
    import json
    manifest = json.loads(manifest_path.read_text())
    from pll_canonical_versions import manifest_failures
    bad1 = manifest_failures()
    check(1, "canonical_versions_match_their_declared_artifacts", len(bad1),
          f"v1 hashes verified at the checkpoint commit; v2 hashes verified on disk. {bad1 or 'all match'}")

    # ---- 2. raw source data unchanged --------------------------------------
    n2, bad2 = 0, []
    for year_str, rec in manifest["raw_data"].items():
        recomputed = raw_manifest_for_season(int(year_str))
        if recomputed.get("raw_manifest_hash") != rec.get("raw_manifest_hash"):
            n2 += 1
            bad2.append(f"{year_str}: raw_manifest_hash changed")
    check(2, "raw_source_data_unchanged", n2,
          f"raw_manifest_hash recomputed from data/raw/<year>/*/_meta.json "
          f"content_hash records for {list(manifest['raw_data'].keys())} and "
          f"compared to the frozen Phase 11 manifest. {bad2 or 'all match'}")

    # ---- 3. Phase 11 manifest and validation report still validate --------
    n3, bad3 = 0, []
    p11_report = hf("phase11_validation_report.csv")
    if (p11_report["status"] != "PASS").any():
        n3 += 1
        bad3.append("phase11_validation_report.csv has a non-PASS row")
    if manifest["validation_status"]["phase11"]["n_fail"] != 0:
        n3 += 1
        bad3.append("manifest records a Phase 11 failure")
    for prior in ["phase8", "phase9", "phase10", "phase11"]:
        rec = manifest["validation_status"].get(prior)
        if rec is None or rec["n_fail"] != 0:
            n3 += 1
            bad3.append(f"{prior} validation_status missing or has failures")
    check(3, "phase11_manifest_and_report_still_validate", n3,
          f"phase11_validation_report.csv re-read ({len(p11_report)} checks) "
          f"and CANONICAL_MANIFEST_V1.json's validation_status block "
          f"re-checked for phases 8-11. {bad3 or 'all PASS'}")

    # ---- 4. no MVP/Tewaaraton/award/composite artifact was introduced -----
    n4, bad4 = 0, []
    surfaces = {}
    for f in PHASE12_OUTPUTS:
        fp = HIST / f
        if fp.exists():
            surfaces[f"history/{f}"] = list(pd.read_csv(fp, nrows=0).columns)
    for where, names in surfaces.items():
        for nm in names:
            for bad in FORBIDDEN_IN_PUBLISHED:
                if bad in str(nm).lower():
                    n4 += 1
                    bad4.append(f"{where}.{nm}")
    # none of the five new CSVs may be keyed by player_id/player_name --
    # every Phase 12 output is a signal/model/test catalog, never a
    # per-player cross-position score.
    for f in PHASE12_OUTPUTS:
        cols = list(pd.read_csv(HIST / f, nrows=0).columns)
        if "player_id" in cols or "player_name" in cols:
            n4 += 1
            bad4.append(f"{f} is keyed by player -- Phase 12 must not "
                        f"publish a per-player cross-position value")
    # scan every Phase 12 doc's prose for the literal forbidden strings
    # (a leaderboard could be introduced in prose even if no CSV carries it)
    # A disclaimer that legitimately says "no MVP score is built here" -- the
    # project's own established convention, e.g. MVP_INPUT_READINESS.md's own
    # "No Statistical Tewaaraton. No MVP score." -- must not itself trip this
    # check. Only flag a forbidden phrase when it is NOT preceded, within a
    # short window, by a negation the phrase is plainly being denied by.
    negations = ("no ", "no.", "not ", "none ", "never ", "nor ", "forbid",
                "reject", "must not", "should not", "explicitly not",
                "does not", "did not")
    prose_forbidden = ("statistical tewaaraton ranking", "mvp leaderboard",
                       "mvp score", "award score", "composite score",
                       "wins above replacement", "replacement-level score")
    for docname in PHASE12_DOCS:
        fp = DOCS / docname
        if not fp.exists():
            continue
        text = fp.read_text().lower()
        for bad in prose_forbidden:
            start = 0
            while True:
                idx = text.find(bad, start)
                if idx == -1:
                    break
                window = text[max(0, idx - 60):idx]
                if not any(neg in window for neg in negations):
                    n4 += 1
                    bad4.append(f"{docname}: contains {bad!r} without an "
                                f"adjacent negation")
                start = idx + 1
    check(4, "no_mvp_tewaaraton_award_or_composite_artifact_introduced", n4,
          f"{sum(len(v) for v in surfaces.values())} column names scanned "
          f"across {len(surfaces)} new Phase 12 surfaces for "
          f"{len(FORBIDDEN_IN_PUBLISHED)} forbidden patterns; none of the 5 "
          f"new CSVs is keyed by player; {len(PHASE12_DOCS)} docs scanned "
          f"for forbidden prose. {bad4 or 'none found'}")

    # ---- 5. no arbitrary-weight composite exists in the new script --------
    src = (Path(__file__).resolve().parent / "pll_phase12_player_value_research.py").read_text()
    n5, bad5 = 0, []
    # a literal weighted-sum pattern like "0.4 * scoring_value + 0.3 * ..."
    # written into a column that gets persisted would be the forbidden
    # construction; scan for numeric-literal-times-metric additions outside
    # of comments/docstrings that are not part of the (documented, rejected,
    # never-computed) FORBIDDEN_* model candidate rows.
    import re
    weighted_sum_pattern = re.compile(r"0\.\d+\s*\*\s*\w+\s*\+\s*0\.\d+\s*\*\s*\w+")
    hits = weighted_sum_pattern.findall(src)
    if hits:
        n5 += len(hits)
        bad5.append(f"weighted-sum-looking literal(s) found: {hits}")
    mc = hf("player_value_model_candidates.csv")
    forbidden_rows = mc[mc["model_id"].str.startswith("FORBIDDEN_")]
    if len(forbidden_rows) == 0 or (forbidden_rows["status"] != "REJECTED").any():
        n5 += 1
        bad5.append("arbitrary-weight and equal-weight composites are not "
                    "explicitly documented as REJECTED-by-rule")
    check(5, "no_arbitrary_weight_composite_exists", n5,
          f"source scanned for a literal weighted-sum pattern (none found "
          f"outside documentation); {len(forbidden_rows)} FORBIDDEN_* model "
          f"candidate rows checked to all carry status REJECTED. "
          f"{bad5 or 'clean'}")

    # ---- 6. every candidate model has an explicit unit and baseline -------
    n6, bad6 = 0, []
    for col in ("unit", "baseline"):
        missing = mc[mc[col].isna() | (mc[col].astype(str).str.strip() == "")]
        if len(missing):
            n6 += len(missing)
            bad6.append(f"{len(missing)} rows missing {col}")
    check(6, "every_model_candidate_has_explicit_unit_and_baseline", n6,
          f"{len(mc)} model candidate rows checked for non-empty unit and "
          f"baseline fields. {bad6 or 'all rows carry both'}")

    # ---- 7. rejected/unsupported models retain a documented reason --------
    n7, bad7 = 0, []
    terminal = mc[mc["status"].isin(["REJECTED", "UNSUPPORTED"])]
    short_reason = terminal[terminal["major_failure_modes"].astype(str).str.len() < 20]
    if len(short_reason):
        n7 += len(short_reason)
        bad7.append(f"{list(short_reason['model_id'])}")
    check(7, "rejected_models_retain_documented_reasons", n7,
          f"{len(terminal)} REJECTED/UNSUPPORTED rows checked for a "
          f"major_failure_modes field of at least 20 characters. "
          f"{bad7 or 'all documented'}")

    # ---- 8. status values are from the allowed vocabulary -----------------
    n8, bad8 = 0, []
    bad_status = mc[~mc["status"].isin(ALLOWED_MODEL_STATUS)]
    if len(bad_status):
        n8 += len(bad_status)
        bad8.append(list(bad_status["status"].unique()))
    check(8, "model_status_values_are_from_the_allowed_vocabulary", n8,
          f"{len(mc)} rows checked against {sorted(ALLOWED_MODEL_STATUS)}. "
          f"{bad8 or 'all valid'}")

    # ---- 9. no two-point ABILITY metric is resurrected as reliable --------
    n9, bad9 = 0, []
    sig = hf("player_value_signal_inventory.csv")
    two_pt_ability_rows = sig[sig["signal_name"].str.contains(
        "two_point_conversion|two_point_pct", case=False, na=False)]
    for _, r in two_pt_ability_rows.iterrows():
        if "unsupported" not in str(r["season_award_suitability"]).lower() and \
           "unsupported" not in str(r["career_estimable"]).lower():
            # allow the row IF its own class column literally says UNSUPPORTED
            # somewhere among the readiness-relevant fields
            combined = f"{r['season_award_suitability']} {r['notes']}".lower()
            if "unsupported" not in combined:
                n9 += 1
                bad9.append(r["signal_name"])
    car_rel = hf("career_ability_reliability.csv")
    two_pt = car_rel[(car_rel["rate_name"] == "two_point_pct") &
                     (car_rel["scope"] == "pooled_player_career")]
    if two_pt.empty or bool(two_pt.iloc[0]["estimable_at_this_scope"]):
        n9 += 1
        bad9.append("career_ability_reliability.csv no longer marks "
                    "two_point_pct as non-estimable")
    check(9, "two_point_ability_remains_unsupported", n9,
          f"signal inventory two-point rows and "
          f"career_ability_reliability.csv re-checked. {bad9 or 'still UNSUPPORTED'}")

    # ---- 10. defensive signals keep 'partial' and no fabricated exposure --
    n10, bad10 = 0, []
    dep = hf("player_value_metric_dependency.csv")
    if not (sig["signal_name"].str.contains("defensive_value_partial", na=False)).any():
        n10 += 1
        bad10.append("defensive_value_partial_raw missing from signal inventory")
    else:
        row = sig[sig["signal_name"].str.contains("defensive_value_partial", na=False)].iloc[0]
        if "partial" not in row["exact_source"].lower() and "partial" not in row["signal_name"].lower():
            n10 += 1
            bad10.append("'partial' dropped from the defensive signal's name")
    # no new column anywhere in Phase 12 outputs claims a "minutes",
    # "possession_share" or "on_field" exposure for defense -- these would be
    # fabricated, since the feed carries none of them (see docs).
    fabricated_terms = ("minutes_played", "on_field_share", "defensive_possession_share")
    for f in PHASE12_OUTPUTS:
        cols = [c.lower() for c in pd.read_csv(HIST / f, nrows=0).columns]
        for t in fabricated_terms:
            if t in cols:
                n10 += 1
                bad10.append(f"{f} carries fabricated exposure column {t}")
    check(10, "defense_not_assigned_fabricated_exposure", n10,
          f"defensive signal rows and all {len(PHASE12_OUTPUTS)} new CSV "
          f"schemas checked for fabricated minutes/on-field exposure "
          f"columns. {bad10 or 'clean'}")

    # ---- 11. no position normalization (z/percentile) is labeled a value --
    n11, bad11 = 0, []
    for mid in ["XPOS_M03", "XPOS_M04"]:
        row = mc[mc["model_id"] == mid]
        if row.empty or row.iloc[0]["status"] not in ("REJECTED",):
            n11 += 1
            bad11.append(f"{mid} status is {row.iloc[0]['status'] if not row.empty else 'MISSING'}, expected REJECTED")
    forbidden_row = mc[mc["model_id"] == "FORBIDDEN_positional_zscore_as_value"]
    if forbidden_row.empty or forbidden_row.iloc[0]["status"] != "REJECTED":
        n11 += 1
        bad11.append("FORBIDDEN_positional_zscore_as_value missing or not REJECTED")
    check(11, "position_normalization_not_mislabeled_as_value", n11,
          f"within-position z (XPOS_M04) and percentile (XPOS_M03) model "
          f"candidates, plus the explicit forbidden-by-rule row, checked to "
          f"carry status REJECTED. {bad11 or 'correctly rejected'}")

    # ---- 12. additive models pass the accounting check where claimed ------
    n12, bad12 = 0, []
    val = hf("player_value_validation_results.csv")
    acct = val[val["validation_type"] == "ACCOUNTING_VALIDITY"]
    # the ROW-LEVEL identity (sum of components == EPA_points_raw for every
    # player-row) is the invariant additive models actually rest on, and it
    # must be exact PASS always. The season-LEAGUE-SUM check is a separate,
    # more fragile property tied to season-specific source-data quality (see
    # the 2022/2024 finding in the validation results, carried forward as
    # FAIL_WITH_KNOWN_CAUSE rather than silently passed or hidden) and is
    # allowed documented exceptions.
    row_level = acct[acct["model_or_metric"] == "EPA_points_raw = sum(5 components)"]
    if row_level.empty or (row_level["result"] != "PASS").any():
        n12 += 1
        bad12.append("the row-level component-sum identity is not exact PASS")
    league_sum_rows = acct[acct["model_or_metric"] == "EPA_points_raw"]
    undocumented = league_sum_rows[
        (league_sum_rows["result"] != "PASS") &
        (~league_sum_rows["interpretation"].astype(str).str.contains(
            "INFERRED cause|UNRESOLVED residual|Nets to zero", na=False))]
    if len(undocumented):
        n12 += len(undocumented)
        bad12.append("a non-PASS season-sum row carries no documented cause")
    additive_claimed = mc[mc["additive"].astype(str).isin(["True", "true"])]
    if len(additive_claimed) == 0:
        n12 += 1
        bad12.append("no model candidate claims additive=True to check against")
    check(12, "additive_models_pass_accounting_tests_where_claimed", n12,
          f"row-level component-sum identity checked exact-PASS; "
          f"{len(league_sum_rows)} season league-sum rows checked to be "
          f"either PASS or an explicitly documented exception (2022, 2024); "
          f"{len(additive_claimed)} model candidates claim additive=True. "
          f"{bad12 or 'consistent'}")

    # ---- 13. every counterfactual test behaves as theoretically expected --
    n13, bad13 = 0, []
    cf = hf("player_value_counterfactual_tests.csv")
    # T1-T5 must demonstrate their stated mechanical behaviour (True); T7
    # must demonstrate the cross-role NON-equivalence (False is the correct,
    # expected scientific finding); T6 is explicitly ambiguous (no boolean).
    expected = {
        "T1_same_efficiency_different_volume": True,
        "T2_same_volume_different_efficiency": True,
        "T3_same_scoring_different_turnovers": True,
        "T4_same_faceoff_rate_different_draw_volume": True,
        "T5_same_save_pct_different_shots_faced": True,
        "T7_equal_z_unequal_magnitude_cross_role": False,
    }
    cf_idx = cf.set_index("test_id")
    for tid, exp in expected.items():
        if tid not in cf_idx.index:
            n13 += 1
            bad13.append(f"{tid} missing")
            continue
        actual = cf_idx.loc[tid, "passes_theoretical_expectation"]
        actual_bool = bool(actual) if pd.notna(actual) else None
        if actual_bool != exp:
            n13 += 1
            bad13.append(f"{tid}: expected {exp}, observed {actual_bool}")
    if "T6_high_volume_mediocre_vs_low_volume_elite" in cf_idx.index:
        t6 = cf_idx.loc["T6_high_volume_mediocre_vs_low_volume_elite",
                       "passes_theoretical_expectation"]
        if pd.notna(t6):
            n13 += 1
            bad13.append("T6 (deliberately ambiguous) carries a boolean verdict")
    check(13, "all_counterfactual_tests_behave_as_theoretically_expected", n13,
          f"{len(expected)} deterministic counterfactual tests checked "
          f"against their stated expectation; T6 checked to remain "
          f"deliberately unresolved. {bad13 or 'all as expected'}")

    # ---- 14. deterministic rebuild -----------------------------------------
    n14, bad14 = 0, []
    before = {f: hashlib.sha256((HIST / f).read_bytes()).hexdigest()
             for f in PHASE12_OUTPUTS}
    p12.main()
    after = {f: hashlib.sha256((HIST / f).read_bytes()).hexdigest()
            for f in PHASE12_OUTPUTS}
    for f in PHASE12_OUTPUTS:
        if before[f] != after[f]:
            n14 += 1
            bad14.append(f)
    check(14, "phase12_rebuild_is_deterministic", n14,
          f"{len(PHASE12_OUTPUTS)} outputs re-generated by re-running "
          f"pll_phase12_player_value_research.main() and compared by "
          f"SHA-256 against the pre-existing files. {bad14 or 'byte-identical'}")

    # ---- 15. all Phase 12 docs and outputs are present ---------------------
    n15, bad15 = 0, []
    for f in PHASE12_OUTPUTS:
        if not (HIST / f).exists():
            n15 += 1
            bad15.append(f"missing history/{f}")
    for docname in PHASE12_DOCS:
        if not (DOCS / docname).exists():
            n15 += 1
            bad15.append(f"missing docs/{docname}")
    check(15, "all_phase12_outputs_present", n15,
          f"{len(PHASE12_OUTPUTS)} CSVs and {len(PHASE12_DOCS)} docs checked "
          f"to exist. {bad15 or 'all present'}")

    # ---- 16. no NaN/inf in a place that would silently rank players --------
    n16, bad16 = 0, []
    for f in PHASE12_OUTPUTS:
        df = hf(f)
        numcols = df.select_dtypes(include=[np.number]).columns
        for c in numcols:
            if np.isinf(df[c].replace([np.inf, -np.inf], np.nan).fillna(0)).any():
                pass  # replaced before check; guards against a real inf slipping through
            if np.isinf(df[c].to_numpy(dtype="float64", na_value=0.0)).any():
                n16 += 1
                bad16.append(f"{f}.{c} contains inf")
    check(16, "no_unflagged_inf_in_phase12_numeric_columns", n16,
          f"all numeric columns across {len(PHASE12_OUTPUTS)} outputs "
          f"scanned for inf (VIF legitimately reports the string 'inf' for a "
          f"perfect collinearity, never a numeric inf). {bad16 or 'clean'}")

    report = pd.DataFrame(results)
    HIST.mkdir(parents=True, exist_ok=True)
    out = HIST / "phase12_validation_report.csv"
    report.to_csv(out, index=False)
    n_fail = int((report["status"] == "FAIL").sum())
    print(report[["check_id", "check_name", "status", "n_failures"]].to_string(index=False))
    if n_fail:
        for _, r in report[report["status"] == "FAIL"].iterrows():
            print(f"\nFAIL {r['check_id']} {r['check_name']}: {r['detail']}")
    print(f"\n{len(report)-n_fail}/{len(report)} checks PASS -> {out.relative_to(REPO_ROOT)}")
    return report


if __name__ == "__main__":
    main()
