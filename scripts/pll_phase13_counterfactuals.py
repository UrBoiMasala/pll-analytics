"""
Phase 13 Section O: counterfactual tests against the IMPLEMENTED models.

Phase 12's counterfactual_tests.csv used SYNTHETIC players built from role
distributions to test the concept of a model family. This script runs the
same style of test against the ACTUAL, PUBLISHED 2026 leaderboards
(offensive_value_2026.csv, faceoff_value_2026.csv, goalie_value_2026.csv),
using REAL player pairs selected from the real data wherever a real pair
approximates the theoretical case, and synthetic constructions (built from
real 2026 role statistics, same discipline as Phase 12) where no real pair
does. If a result is surprising but mathematically consistent with the
model's stated definition, it is recorded as PASS and NOT used to justify
a model change (Section Q/V discipline).

Output: data/processed/history/player_value_counterfactual_tests_v1.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"


def load():
    off = pd.read_csv(PROC / "2026" / "offensive_value_2026.csv", dtype={"player_id": str})
    fo = pd.read_csv(PROC / "2026" / "faceoff_value_2026.csv", dtype={"player_id": str})
    go = pd.read_csv(PROC / "2026" / "goalie_value_2026.csv", dtype={"player_id": str})
    return off, fo, go


def _best_pair(df: pd.DataFrame, hold_col: str, vary_col: str, min_vary_gap: float):
    """Among every pair with |vary_gap| >= min_vary_gap, returns the one that
    minimizes |hold_diff| (ties broken by the largest vary_gap). An O(n^2)
    exhaustive search over the real leaderboard -- correct and fast enough at
    these population sizes (< 120 rows per role) -- rather than a fixed
    absolute tolerance on hold_col, which is unreliable when hold_col's
    values cluster tightly (as offensive rate does near zero)."""
    arr = df.reset_index(drop=True)
    n = len(arr)
    best = None
    best_key = (np.inf, -np.inf)
    for i in range(n):
        for j in range(i + 1, n):
            vary_gap = abs(arr.loc[i, vary_col] - arr.loc[j, vary_col])
            if vary_gap < min_vary_gap:
                continue
            hold_gap = abs(arr.loc[i, hold_col] - arr.loc[j, hold_col])
            key = (hold_gap, -vary_gap)
            if key < best_key:
                best_key, best = key, (arr.loc[i], arr.loc[j])
    return best


def add(rows, test_id, family, description, dimension_varied, dimension_held,
        a_desc, b_desc, metric, a_val, b_val, expected, observed, passes, interp):
    rows.append({
        "test_id": test_id, "family": family, "description": description,
        "dimension_varied": dimension_varied, "dimension_held_constant": dimension_held,
        "player_a": a_desc, "player_b": b_desc, "metric_tested": metric,
        "value_a": round(a_val, 3) if pd.notna(a_val) else np.nan,
        "value_b": round(b_val, 3) if pd.notna(b_val) else np.nan,
        "theoretically_expected_behavior": expected, "observed_behavior": observed,
        "passes_theoretical_expectation": passes, "interpretation": interp,
    })


def offense_tests(off: pd.DataFrame) -> list:
    rows = []
    q = off[off["shots"] >= 15].copy()
    q["rate"] = q["offensive_value"] / q["shots"]

    # O1: same efficiency, greater volume -- the two players with the SMALLEST
    # rate difference among all pairs whose shot-volume gap is at least 30
    best_pair = _best_pair(q, hold_col="rate", vary_col="shots", min_vary_gap=30)
    if best_pair:
        a, b = best_pair
        lo, hi = (a, b) if a["shots"] < b["shots"] else (b, a)
        add(rows, "O1_same_efficiency_greater_volume", "offense",
            "real pair with near-identical per-shot rate, largest volume gap available",
            "shots", "offensive_value/shots rate", lo["player_name"], hi["player_name"],
            "offensive_value", lo["offensive_value"], hi["offensive_value"],
            "the higher-volume player should have >= offensive_value at equal rate",
            f"{hi['player_name']} ({hi['offensive_value']:.2f}) vs {lo['player_name']} ({lo['offensive_value']:.2f})",
            bool(hi["offensive_value"] >= lo["offensive_value"]),
            "PASS is the theoretically required behavior for a total-value metric; a FAIL here would be an implementation bug.")

    # O2: same volume, greater efficiency -- smallest shots-gap among all
    # pairs whose rate difference is at least 0.05 (a real efficiency gap,
    # not a rounding artifact of the near-zero clustering O1 exposed)
    best_pair2 = _best_pair(q, hold_col="shots", vary_col="rate", min_vary_gap=0.05)
    if best_pair2:
        a, b = best_pair2
        lo, hi = (a, b) if a["rate"] < b["rate"] else (b, a)
        add(rows, "O2_same_volume_greater_efficiency", "offense",
            "real pair with near-identical shot volume, largest per-shot-rate gap available",
            "offensive_value/shots rate", "shots", lo["player_name"], hi["player_name"],
            "offensive_value", lo["offensive_value"], hi["offensive_value"],
            "the higher-rate player should have >= offensive_value at equal volume",
            f"{hi['player_name']} ({hi['offensive_value']:.2f}) vs {lo['player_name']} ({lo['offensive_value']:.2f})",
            bool(hi["offensive_value"] >= lo["offensive_value"]), "Basic monotonicity check.")

    # O3: same scoring (scoring_points), fewer turnovers
    q3 = off[off["scoring_points"] >= 5].copy()
    q3_by_pts = q3.sort_values("scoring_points")
    arr3 = q3_by_pts.reset_index(drop=True)
    best_pair3, best_gap3 = None, -1
    for i in range(len(arr3) - 1):
        if arr3.loc[i, "scoring_points"] == arr3.loc[i + 1, "scoring_points"]:
            gap = abs(arr3.loc[i, "turnovers"] - arr3.loc[i + 1, "turnovers"])
            if gap > best_gap3:
                best_gap3, best_pair3 = gap, (arr3.loc[i], arr3.loc[i + 1])
    if best_pair3:
        a, b = best_pair3
        fewer, more = (a, b) if a["turnovers"] < b["turnovers"] else (b, a)
        add(rows, "O3_same_scoring_fewer_turnovers", "offense",
            f"real pair tied on scoring_points ({fewer['scoring_points']:.0f}), largest turnover-count gap available",
            "turnovers", "scoring_points", fewer["player_name"], more["player_name"],
            "offensive_value", fewer["offensive_value"], more["offensive_value"],
            "the player with fewer turnovers should have strictly greater offensive_value",
            f"{fewer['player_name']} ({fewer['offensive_value']:.2f}) vs {more['player_name']} ({more['offensive_value']:.2f})",
            bool(fewer["offensive_value"] > more["offensive_value"]),
            "Confirms turnover_value strictly discounts scoring credit -- ball security is never free.")

    # O4: same total points, different shot efficiency (points per shot)
    q4 = off[off["scoring_points"] >= 5].copy()
    q4["pps"] = q4["scoring_points"] / q4["shots"]
    q4_by_pts = q4.sort_values("scoring_points")
    arr4 = q4_by_pts.reset_index(drop=True)
    best_pair4, best_gap4 = None, -1
    for i in range(len(arr4) - 1):
        if arr4.loc[i, "scoring_points"] == arr4.loc[i + 1, "scoring_points"]:
            gap = abs(arr4.loc[i, "pps"] - arr4.loc[i + 1, "pps"])
            if gap > best_gap4:
                best_gap4, best_pair4 = gap, (arr4.loc[i], arr4.loc[i + 1])
    if best_pair4:
        a, b = best_pair4
        eff, ineff = (a, b) if a["pps"] > b["pps"] else (b, a)
        add(rows, "O4_same_points_different_efficiency", "offense",
            f"real pair tied on scoring_points ({eff['scoring_points']:.0f}), largest points-per-shot gap "
            "(i.e. same output, very different volume of attempts to get there)",
            "shots (points-per-shot)", "scoring_points", ineff["player_name"], eff["player_name"],
            "offensive_value", ineff["offensive_value"], eff["offensive_value"],
            "the more efficient (fewer shots for the same points) player should score higher on "
            "offensive_value, since fewer shots means a smaller expected-points baseline to clear",
            f"{eff['player_name']} ({eff['offensive_value']:.2f}) vs {ineff['player_name']} ({ineff['offensive_value']:.2f})",
            bool(eff["offensive_value"] > ineff["offensive_value"]),
            "Confirms the baseline scales with attempts, not just makes -- taking more shots to reach the "
            "same score is priced as below-average efficiency.")

    # O5: same one-point production, different 2PT attempt behavior
    q5 = off[(off["one_point_goals"] >= 3)].copy()
    arr5 = q5.sort_values("one_point_goals").reset_index(drop=True)
    best_pair5, best_gap5 = None, -1
    for i in range(len(arr5) - 1):
        if arr5.loc[i, "one_point_goals"] == arr5.loc[i + 1, "one_point_goals"]:
            gap = abs(arr5.loc[i, "two_point_attempt_share_raw"] - arr5.loc[i + 1, "two_point_attempt_share_raw"])
            if pd.notna(gap) and gap > best_gap5:
                best_gap5, best_pair5 = gap, (arr5.loc[i], arr5.loc[i + 1])
    if best_pair5:
        a, b = best_pair5
        low2, high2 = (a, b) if a["two_point_attempt_share_raw"] < b["two_point_attempt_share_raw"] else (b, a)
        add(rows, "O5_same_one_point_production_different_2pt_selection", "offense",
            f"real pair tied on one_point_goals ({low2['one_point_goals']:.0f}), largest two-point-attempt-share gap",
            "two_point_attempt_share_raw", "one_point_goals", low2["player_name"], high2["player_name"],
            "two_point_attempt_share_raw", low2["two_point_attempt_share_raw"], high2["two_point_attempt_share_raw"],
            "no directional prediction -- selection is a descriptive tendency, not a value claim "
            "(model_spec_v1 explicitly does not price selection independently of its shots)",
            f"selection shares differ ({low2['two_point_attempt_share_raw']:.2f} vs {high2['two_point_attempt_share_raw']:.2f}) "
            f"while offensive_value ({low2['offensive_value']:.2f} vs {high2['offensive_value']:.2f}) is driven by shooting_value_raw, not selection share",
            None,
            "NOT A PASS/FAIL TEST. Confirms (by construction) that two_point_attempt_share_raw does not "
            "itself enter offensive_value -- it is a reported descriptive column, exactly as specified.")

    # O6: high volume average efficiency vs low volume elite efficiency
    q6 = off[off["shots"] >= 10].copy()
    q6["rate"] = q6["offensive_value"] / q6["shots"]
    median_rate = q6["rate"].median()
    high_vol_avg = q6[(q6["shots"] >= q6["shots"].quantile(0.85)) &
                      (q6["rate"].between(median_rate * 0.7, median_rate * 1.3))]
    low_vol_elite = q6[(q6["shots"] <= q6["shots"].quantile(0.25)) &
                       (q6["rate"] >= q6["rate"].quantile(0.9))]
    if len(high_vol_avg) and len(low_vol_elite):
        a = high_vol_avg.iloc[0]
        b = low_vol_elite.iloc[0]
        add(rows, "O6_high_volume_average_vs_low_volume_elite", "offense",
            "real high-volume/average-rate player vs real low-volume/elite-rate player",
            "both shots and rate", "nothing (the genuinely ambiguous case)",
            a["player_name"], b["player_name"], "offensive_value", a["offensive_value"], b["offensive_value"],
            "no single correct answer -- this is the case Phase 10/12 identify as one where total-value and "
            "per-shot-rate metrics can legitimately disagree",
            f"total value favors {'the high-volume player' if a['offensive_value']>b['offensive_value'] else 'the low-volume player'}; "
            f"per-shot rate favors the low-volume player by construction ({b['rate']:.3f} vs {a['rate']:.3f})",
            None,
            "NOT A PASS/FAIL TEST, by design -- documents the ambiguity rather than resolving it.")
    return rows


def faceoff_tests(fo: pd.DataFrame) -> list:
    rows = []
    q = fo[fo["faceoffs"] >= 20].copy()

    # F1: same win%, different draw volume
    arr = q.sort_values("faceoff_win_pct").reset_index(drop=True)
    best_pair, best_gap = None, -1
    for i in range(len(arr) - 1):
        if abs(arr.loc[i, "faceoff_win_pct"] - arr.loc[i + 1, "faceoff_win_pct"]) < 0.02:
            gap = abs(arr.loc[i, "faceoffs"] - arr.loc[i + 1, "faceoffs"])
            if gap > best_gap:
                best_gap, best_pair = gap, (arr.loc[i], arr.loc[i + 1])
    if best_pair:
        a, b = best_pair
        lo, hi = (a, b) if a["faceoffs"] < b["faceoffs"] else (b, a)
        add(rows, "F1_same_win_pct_different_volume", "faceoff",
            "real pair with near-identical win%, largest draw-count gap available",
            "faceoffs", "faceoff_win_pct", lo["player_name"], hi["player_name"],
            "faceoff_value_total", lo["faceoff_value_total"], hi["faceoff_value_total"],
            "the higher-volume player should have >= faceoff_value_total (this is the workload confound, "
            "expected and disclosed, not a defect)",
            f"{hi['player_name']} ({hi['faceoff_value_total']:.2f}) vs {lo['player_name']} ({lo['faceoff_value_total']:.2f})",
            bool(hi["faceoff_value_total"] >= lo["faceoff_value_total"]),
            "PASS reproduces the mechanical workload effect Phase 10/12 already documented (probe P5).")

    # F2: same draw volume, different win%
    arr2 = q.sort_values("faceoffs").reset_index(drop=True)
    best_pair2, best_gap2 = None, -1
    for i in range(len(arr2) - 1):
        if abs(arr2.loc[i, "faceoffs"] - arr2.loc[i + 1, "faceoffs"]) <= 10:
            gap = abs(arr2.loc[i, "faceoff_win_pct"] - arr2.loc[i + 1, "faceoff_win_pct"])
            if gap > best_gap2:
                best_gap2, best_pair2 = gap, (arr2.loc[i], arr2.loc[i + 1])
    if best_pair2:
        a, b = best_pair2
        lo, hi = (a, b) if a["faceoff_win_pct"] < b["faceoff_win_pct"] else (b, a)
        add(rows, "F2_same_volume_different_win_pct", "faceoff",
            "real pair with near-identical draw count, largest win% gap available",
            "faceoff_win_pct", "faceoffs", lo["player_name"], hi["player_name"],
            "faceoff_value_total", lo["faceoff_value_total"], hi["faceoff_value_total"],
            "the higher-win% player should have strictly greater faceoff_value_total",
            f"{hi['player_name']} ({hi['faceoff_value_total']:.2f}) vs {lo['player_name']} ({lo['faceoff_value_total']:.2f})",
            bool(hi["faceoff_value_total"] > lo["faceoff_value_total"]), "Basic monotonicity check.")

    # F3: above vs below baseline
    above = q[q["faceoff_win_pct"] > q["baseline_faceoff_win_pct"]]
    below = q[q["faceoff_win_pct"] < q["baseline_faceoff_win_pct"]]
    if len(above) and len(below):
        add(rows, "F3_above_vs_below_baseline", "faceoff",
            "every above-baseline vs every below-baseline faceoff player",
            "faceoff_win_pct relative to league baseline", "n/a",
            f"{len(above)} above-baseline players", f"{len(below)} below-baseline players",
            "faceoff_value_total", float(above["faceoff_value_total"].min()),
            float(below["faceoff_value_total"].max()),
            "every above-baseline player's value should exceed every below-baseline player's, "
            "AT THE SAME VOLUME -- but volume differs, so this need not hold exactly",
            f"min above-baseline value ({above['faceoff_value_total'].min():.2f}) vs "
            f"max below-baseline value ({below['faceoff_value_total'].max():.2f})",
            bool(above["faceoff_value_total"].min() > below["faceoff_value_total"].max())
            if len(above) and len(below) else None,
            "A FAIL here is expected and is NOT evidence of a defect if it occurs -- it would simply mean a "
            "low-volume above-baseline player is outscored in TOTAL value by a high-volume below-baseline one, "
            "exactly the workload confound this model discloses rather than corrects.")
    return rows


def goalie_tests(go: pd.DataFrame) -> list:
    rows = []
    q = go[go["shots_on_goal_faced"] >= 30].copy()

    # G1: same save%, different shots faced
    arr = q.sort_values("save_pct").reset_index(drop=True)
    best_pair, best_gap = None, -1
    for i in range(len(arr) - 1):
        if abs(arr.loc[i, "save_pct"] - arr.loc[i + 1, "save_pct"]) < 0.02:
            gap = abs(arr.loc[i, "shots_on_goal_faced"] - arr.loc[i + 1, "shots_on_goal_faced"])
            if gap > best_gap:
                best_gap, best_pair = gap, (arr.loc[i], arr.loc[i + 1])
    if best_pair:
        a, b = best_pair
        lo, hi = (a, b) if a["shots_on_goal_faced"] < b["shots_on_goal_faced"] else (b, a)
        add(rows, "G1_same_save_pct_different_shots_faced", "goalie",
            "real pair with near-identical save%, largest shots-faced gap available",
            "shots_on_goal_faced", "save_pct", lo["player_name"], hi["player_name"],
            "goalie_value_total", lo["goalie_value_total"], hi["goalie_value_total"],
            "the busier goalie should have >= goalie_value_total (the workload confound, expected)",
            f"{hi['player_name']} ({hi['goalie_value_total']:.2f}) vs {lo['player_name']} ({lo['goalie_value_total']:.2f})",
            bool(hi["goalie_value_total"] >= lo["goalie_value_total"]),
            "PASS reproduces the mechanical workload effect Phase 10/12 already documented (probe P4).")

    # G2: same workload, different save%
    arr2 = q.sort_values("shots_on_goal_faced").reset_index(drop=True)
    best_pair2, best_gap2 = None, -1
    for i in range(len(arr2) - 1):
        if abs(arr2.loc[i, "shots_on_goal_faced"] - arr2.loc[i + 1, "shots_on_goal_faced"]) <= 15:
            gap = abs(arr2.loc[i, "save_pct"] - arr2.loc[i + 1, "save_pct"])
            if gap > best_gap2:
                best_gap2, best_pair2 = gap, (arr2.loc[i], arr2.loc[i + 1])
    if best_pair2:
        a, b = best_pair2
        lo, hi = (a, b) if a["save_pct"] < b["save_pct"] else (b, a)
        add(rows, "G2_same_workload_different_save_pct", "goalie",
            "real pair with near-identical shots faced, largest save% gap available",
            "save_pct", "shots_on_goal_faced", lo["player_name"], hi["player_name"],
            "goalie_value_total", lo["goalie_value_total"], hi["goalie_value_total"],
            "the higher-save% goalie should have strictly greater goalie_value_total",
            f"{hi['player_name']} ({hi['goalie_value_total']:.2f}) vs {lo['player_name']} ({lo['goalie_value_total']:.2f})",
            bool(hi["goalie_value_total"] > lo["goalie_value_total"]), "Basic monotonicity check.")

    # G3: small-sample perfect goalie vs large-sample strong goalie
    small = go[(go["shots_on_goal_faced"] < 20) & (go["shots_on_goal_faced"] > 0)]
    large = go[go["shots_on_goal_faced"] >= 200]
    if len(small) and len(large):
        best_small = small.loc[small["save_pct"].idxmax()]
        best_large = large.loc[large["save_pct"].idxmax()]
        add(rows, "G3_small_sample_perfect_vs_large_sample_strong", "goalie",
            "best-save% small-sample goalie vs best-save% large-sample goalie",
            "shots_on_goal_faced", "n/a",
            best_small["player_name"], best_large["player_name"], "goalie_value_total",
            best_small["goalie_value_total"], best_large["goalie_value_total"],
            "no single correct ranking is implied by the model's own definition -- a small-sample goalie's "
            "PER-SHOT rate value could exceed a large-sample goalie's, but this table ranks by TOTAL value, "
            "which rewards the large sample's cumulative production",
            f"small-sample goalie ({best_small['shots_on_goal_faced']:.0f} SOG, save% "
            f"{best_small['save_pct']:.3f}): {best_small['goalie_value_total']:.2f}; "
            f"large-sample goalie ({best_large['shots_on_goal_faced']:.0f} SOG, save% "
            f"{best_large['save_pct']:.3f}): {best_large['goalie_value_total']:.2f}",
            None,
            "NOT A PASS/FAIL TEST -- the qualification_state column (SMALL_SAMPLE vs QUALIFIED) is exactly "
            "how this model discloses which of the two is more trustworthy, rather than resolving the ranking.")
    return rows


def main():
    off, fo, go = load()
    rows = offense_tests(off) + faceoff_tests(fo) + goalie_tests(go)
    df = pd.DataFrame(rows)
    out = HIST / "player_value_counterfactual_tests_v1.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out.relative_to(REPO_ROOT)}: {len(df)} tests")
    determinate = df[df["passes_theoretical_expectation"].notna()]
    print(f"Determinate tests: {len(determinate)}, all PASS: "
         f"{bool(determinate['passes_theoretical_expectation'].astype(bool).all())}")
    print(df[["test_id", "passes_theoretical_expectation"]].to_string(index=False))


if __name__ == "__main__":
    main()
