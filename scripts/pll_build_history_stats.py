"""
Phase 9: run the Phase 5 / 6 / 7 / 8 statistical layers for each historical
season, then build the pooled 2022-2026 outputs.

Every layer is the EXISTING builder, pointed at a different season directory.
No metric formula is re-implemented, re-tuned or season-specialised. The SQL in
sql/ already takes {data_dir}, so the season is purely an I/O concern -- which
is precisely what makes a cross-season comparison meaningful: a difference
between 2022 and 2026 is a difference in the league, not in the code.

Two things ARE re-estimated per season, and must be:
  * every empirical baseline (shot conversion, faceoff win probability,
    positional caused-turnover rates, the beta priors). A 2026 baseline applied
    to 2022 would silently express 2022 in 2026's units.
  * the Phase 7 usage model, which is refitted by cross-validation per season.

Pooled outputs carry `season` on every row and are the concatenation of the
season files, never a re-derivation -- so `pooled == union(seasons)` is a
testable identity rather than a hope.

Usage:
    python3 pll_build_history_stats.py [--years 2022,2023]
"""
import argparse
import io
import sys
import traceback
from contextlib import redirect_stdout
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pll_build_team_metrics as p5           # noqa: E402
import pll_build_player_value as p6           # noqa: E402
import pll_build_adjusted_player_value as p7  # noqa: E402
import pll_build_phase8_stats as p8           # noqa: E402

HISTORY = [2022, 2023, 2024, 2025]
ALL_SEASONS = [2022, 2023, 2024, 2025, 2026]
HIST_DIR = REPO_ROOT / "data" / "processed" / "history"

# (pooled output name, per-season filename template)
POOLED = [
    ("team_stats_2022_2026.csv", "team_stats_{y}.csv"),
    ("player_stats_2022_2026.csv", "player_stats_{y}.csv"),
    ("team_leaderboards_2022_2026.csv", "team_leaderboards_{y}.csv"),
    ("player_leaderboards_2022_2026.csv", "player_leaderboards_{y}.csv"),
    ("two_point_audit_2022_2026.csv", "two_point_audit_{y}.csv"),
    ("metric_sanity_flags_2022_2026.csv", "metric_sanity_flags_{y}.csv"),
]


def run_layer(name, mod, season):
    """Run one builder against one season, capturing its output."""
    data_dir = REPO_ROOT / "data" / "processed" / str(season)
    buf = io.StringIO()
    saved = mod.DATA_DIR
    saved_scratch = getattr(mod, "SCRATCH_DIR", None)
    saved_tag = getattr(mod, "SEASON_TAG", None)
    try:
        with redirect_stdout(buf):
            if hasattr(mod, "set_season"):
                mod.set_season(season)
            else:
                mod.DATA_DIR = data_dir
            mod.main()
        return {"season": season, "layer": name, "status": "ok", "detail": "",
                "log": buf.getvalue().replace("\n", " | ")[:1500]}
    except Exception:  # noqa: BLE001
        return {"season": season, "layer": name, "status": "failed",
                "detail": traceback.format_exc().strip().splitlines()[-1],
                "log": buf.getvalue().replace("\n", " | ")[:1500]}
    finally:
        mod.DATA_DIR = saved
        if saved_scratch is not None:
            mod.SCRATCH_DIR = saved_scratch
        if saved_tag is not None:
            mod.SEASON_TAG = saved_tag


def build_pooled(seasons):
    """Concatenate the per-season files, stamping `season` on every row."""
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    made = []
    for pooled_name, tmpl in POOLED:
        frames = []
        for y in seasons:
            p = REPO_ROOT / "data" / "processed" / str(y) / tmpl.format(y=y)
            if not p.exists():
                print(f"  MISSING {p.relative_to(REPO_ROOT)} -- pooled file will "
                      f"not contain {y}")
                continue
            df = pd.read_csv(p, low_memory=False)
            df.insert(0, "season", y)
            frames.append(df)
        if not frames:
            continue
        # union of columns, so a season that lacks a column carries NULL there
        # rather than the column being silently dropped for everyone
        out = pd.concat(frames, ignore_index=True, sort=False)
        out.to_csv(HIST_DIR / pooled_name, index=False)
        made.append((pooled_name, len(out), out["season"].nunique()))
        print(f"  {pooled_name:42s} {len(out):7d} rows  {out['season'].nunique()} seasons")
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=str, default=None)
    ap.add_argument("--skip-pooled", action="store_true")
    args = ap.parse_args()
    seasons = ([int(y) for y in args.years.split(",")] if args.years else list(HISTORY))

    layers = [("phase5_team_metrics", p5), ("phase6_player_value", p6),
              ("phase7_adjusted_value", p7), ("phase8_stat_layer", p8)]
    report = []
    for season in seasons:
        print(f"=== {season} ===")
        for name, mod in layers:
            r = run_layer(name, mod, season)
            report.append(r)
            print(f"  {name:24s} {r['status']}"
                  + (f"  -- {r['detail']}" if r["status"] == "failed" else ""))
            if r["status"] == "failed":
                break

    rep = pd.DataFrame(report)
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    rep_path = HIST_DIR / "historical_stat_layer_report.csv"
    rep.to_csv(rep_path, index=False)
    print(f"\nWrote {rep_path.relative_to(REPO_ROOT)}")

    if not args.skip_pooled:
        print("\nPooled 2022-2026 outputs:")
        build_pooled(ALL_SEASONS)
    return rep


if __name__ == "__main__":
    main()
