"""
Phase 13 Section R: within-role dominance diagnostic (descriptive only).

Phase 12 rejected a universal cross-position value scale (Architecture C).
This script does NOT overturn that. It asks a narrower, explicitly
within-role question: is any player unusually dominant in their OWN role
under nearly every reasonable model assumption tested in this phase --
bootstrap resampling (Section K), the alternative-assumption sensitivity
checks (Section P), and qualification status (Section L)? The output is a
descriptive robustness summary, never a cross-position score, and never an
average of percentiles/z-scores/role ranks.

Output: data/processed/history/within_role_dominance_diagnostic.csv
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"


def dominance_for_role(leaderboard: pd.DataFrame, value_col: str, role: str) -> list:
    top = leaderboard.sort_values(value_col, ascending=False).head(3).copy()
    rows = []
    for _, r in top.iterrows():
        rank_ci_width = r["rank_ci_hi"] - r["rank_ci_lo"]
        rows.append({
            "role": role, "player_name": r["player_name"], "rank": int(r["rank"]),
            "value": round(float(r[value_col]), 2),
            "top10_inclusion_frequency": round(float(r["top10_inclusion_frequency"]), 3),
            "rank_ci_lo": float(r["rank_ci_lo"]), "rank_ci_hi": float(r["rank_ci_hi"]),
            "rank_ci_width": round(float(rank_ci_width), 1),
            "qualification_state": r["qualification_state"],
            "robust_under_bootstrap": bool(r["top10_inclusion_frequency"] >= 0.95),
            "robust_under_qualification": bool(r["qualification_state"] == "QUALIFIED"),
        })
    return rows


def main():
    off = pd.read_csv(PROC / "2026" / "offensive_value_2026.csv")
    fo = pd.read_csv(PROC / "2026" / "faceoff_value_2026.csv")
    go = pd.read_csv(PROC / "2026" / "goalie_value_2026.csv")

    rows = (dominance_for_role(off, "offensive_value", "offense")
           + dominance_for_role(fo, "faceoff_value_total", "faceoff")
           + dominance_for_role(go, "goalie_value_total", "goalie"))
    df = pd.DataFrame(rows)
    df["overall_robustness"] = df.apply(
        lambda r: "ROBUST_ACROSS_METHODS" if r["robust_under_bootstrap"] and r["robust_under_qualification"]
        else ("ROBUST_UNDER_BOOTSTRAP_ONLY" if r["robust_under_bootstrap"]
              else ("QUALIFIED_BUT_UNSTABLE_RANK" if r["robust_under_qualification"]
                    else "NOT_ROBUST")), axis=1)
    df["cross_role_comparison_note"] = (
        "This row describes robustness WITHIN its own role only. It is NEVER to be compared, averaged, "
        "or combined across roles -- doing so would be exactly the cross-position composite Phase 12 "
        "found unsupported (docs/CROSS_POSITION_VALUE_PHASE12.md).")

    out = HIST / "within_role_dominance_diagnostic.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out.relative_to(REPO_ROOT)}: {len(df)} rows")
    print(df[["role", "player_name", "rank", "top10_inclusion_frequency",
             "qualification_state", "overall_robustness"]].to_string(index=False))


if __name__ == "__main__":
    main()
