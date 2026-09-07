"""
Phase 4: possession diagnostic report (descriptive statistics only — NOT
advanced analytics). Prints a summary and saves
data/processed/2026/possession_diagnostics.csv (one row per game) plus
prints season-wide distributions to stdout.
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"


def main():
    poss = pd.read_csv(DATA_DIR / "possessions.csv")

    print("=== Season totals ===")
    print(f"Total possessions: {len(poss)}")
    print(f"Games: {poss['game_slug'].nunique()}")
    print(f"Possessions per game: mean={poss.groupby('game_slug').size().mean():.1f}, "
          f"min={poss.groupby('game_slug').size().min()}, max={poss.groupby('game_slug').size().max()}")

    print()
    print("=== Possessions per team per game (summary) ===")
    per_team = poss.groupby(["game_slug", "offense_team_id"]).size()
    print(f"mean={per_team.mean():.1f}, min={per_team.min()}, max={per_team.max()}")

    print()
    print("=== start_reason distribution ===")
    print(poss["start_reason"].value_counts())
    print()
    print("=== end_reason distribution ===")
    print(poss["end_reason"].value_counts())

    print()
    print("=== Duration distribution (seconds) ===")
    print(poss["duration_seconds"].describe())

    print()
    print("=== Goals / points per possession ===")
    print("possessions with a goal:", int((poss["goals"] > 0).sum()), f"({100*(poss['goals']>0).mean():.1f}%)")
    print(poss["points_scored"].value_counts().sort_index())

    print()
    print("=== Truncated / ambiguous ===")
    print(f"truncated: {int(poss['is_truncated'].sum())} ({100*poss['is_truncated'].mean():.1f}%)")
    print(f"ambiguous: {int(poss['is_ambiguous'].sum())} ({100*poss['is_ambiguous'].mean():.1f}%)")

    print()
    print("=== Two-point / man-up ===")
    print(f"has_two_point_attempt: {int(poss['has_two_point_attempt'].sum())}")
    print(f"has_man_up_shot: {int(poss['has_man_up_shot'].sum())}")

    print()
    print("=== Games with unusually high/low possession counts ===")
    counts = poss.groupby("game_slug").size().sort_values()
    print("Lowest 5:")
    print(counts.head(5))
    print("Highest 5:")
    print(counts.tail(5))

    per_game = poss.groupby("game_slug").agg(
        n_possessions=("possession_id", "count"),
        n_ambiguous=("is_ambiguous", "sum"),
        n_truncated=("is_truncated", "sum"),
        total_points=("points_scored", "sum"),
    ).reset_index()
    per_game["pct_ambiguous"] = 100 * per_game["n_ambiguous"] / per_game["n_possessions"]
    out_path = DATA_DIR / "possession_diagnostics.csv"
    per_game.to_csv(out_path, index=False)
    print()
    print(f"Saved per-game diagnostics to {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
