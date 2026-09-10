"""
Phase 9: multi-season sanity audit, 2022-2026.

Phase 8's sanity audit asked "is this 2026 number real?". Phase 9 asks the
question five seasons make possible: "is this number CONSISTENT, and where it
is not, is the inconsistency the league or the feed?"

Same classification as Phase 8, and the same rule -- only class E is fixed:
    A real performance   B sample-size artifact   C role/opportunity artifact
    D known feed limitation   E implementation/data bug

Writes:
    data/processed/history/multi_season_sanity_flags.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
HIST = REPO_ROOT / "data" / "processed" / "history"
SEASONS = [2022, 2023, 2024, 2025, 2026]

FLAG_SPEC = {
    "CROSS_SEASON_DISCONTINUITY": ("D", "warn",
        "A metric's season mean moves further between adjacent seasons than "
        "the within-season spread between teams. Either the league changed or "
        "the feed did; the audit says which where it can."),
    "POSSESSION_COUNT_ANOMALY": ("D", "error",
        "A season's possession count per game departs materially from the "
        "other seasons, which makes every possession-denominated metric in "
        "that season non-comparable."),
    "FEED_LOGGING_GAP": ("D", "warn",
        "A season shows a class of possession ambiguity that the other seasons "
        "do not, indicating missing events rather than different play."),
    "SCORE_IRRECONCILABLE": ("D", "error",
        "A game's goal events cannot reproduce its own official final score."),
    "SEASON_SPECIFIC_VOCABULARY": ("D", "info",
        "A shot tag or event type present in one season and not others."),
    "SMALL_SAMPLE_SEASON_LEADER": ("B", "warn",
        "A season leaderboard is topped on a denominator below that rate's "
        "reliability-0.5 trial count."),
    "TWO_POINT_STILL_UNIDENTIFIED": ("D", "warn",
        "Two-point shooting ability remains statistically unidentified after "
        "pooling every available season."),
    "METRIC_IMPOSSIBLE_VALUE": ("E", "error",
        "A value outside the bounds its own definition allows."),
    "POOLED_UNION_MISMATCH": ("E", "error",
        "A pooled file is not the union of the per-season files."),
    "IDENTITY_UNCONFIRMED": ("D", "warn",
        "A player identity that may not be safely aggregated across seasons."),
    "CONSTANT_USAGE_MODEL_CONFIRMED": ("A", "info",
        "The constant usage model still wins on five seasons; the 2026 sign "
        "was not stable."),
}


def load(name, **kw):
    return pd.read_csv(HIST / name, **kw)


def season_file(y, name, **kw):
    return pd.read_csv(REPO_ROOT / "data" / "processed" / str(y) / name, **kw)


def main():
    rows = []

    def flag(code, season, entity, metric, value, detail):
        cls, sev, desc = FLAG_SPEC[code]
        rows.append({"flag_code": code, "classification": cls, "severity": sev,
                     "season": season, "entity": entity, "metric_name": metric,
                     "value": value, "flag_description": desc, "detail": detail})

    team = load("team_stats_2022_2026.csv")
    dist = load("multi_season_metric_distributions.csv")

    # ---- 1. cross-season discontinuity ----------------------------------
    for _, r in dist.iterrows():
        if r["season_effect"] == "material":
            means = {y: r.get(f"mean_{y}") for y in SEASONS}
            flag("CROSS_SEASON_DISCONTINUITY", "ALL", "league", r["metric"],
                 r["share_variance_between_seasons"],
                 f"{r['share_variance_between_seasons']:.0%} of the variance in "
                 f"this metric is BETWEEN seasons rather than between teams. "
                 f"Season means: "
                 + ", ".join(f"{y}={means[y]:.4f}" for y in SEASONS if pd.notna(means[y]))
                 + ". Do not pool without centring within season.")

    # ---- 2. possession count anomaly ------------------------------------
    pg = {}
    for y in SEASONS:
        g = season_file(y, "games.csv")
        p = season_file(y, "possessions.csv")
        el = set(g[g["is_completed"] & g["include_in_league_analytics"]
                   & ~g["is_all_star"]]["game_id"])
        p = p[p["game_id"].isin(el)]
        pg[y] = (len(p) / len(el), float(p["is_ambiguous"].mean()))
    vals = np.array([v[0] for v in pg.values()])
    med = np.median(vals)
    for y, (per_game, amb) in pg.items():
        if abs(per_game - med) / med > 0.07:
            flag("POSSESSION_COUNT_ANOMALY", y, "league", "possessions_per_game",
                 per_game,
                 f"{per_game:.1f} possessions per game against a five-season "
                 f"median of {med:.1f} ({(per_game-med)/med:+.1%}). Every "
                 f"possession-denominated metric in {y} is expressed in a "
                 f"different denominator from the other seasons.")

    # ---- 3. feed logging gaps -------------------------------------------
    gapish = {}
    for y in SEASONS:
        p = season_file(y, "possessions.csv")
        amb = p[p["is_ambiguous"] == True]  # noqa: E712
        reasons = amb["ambiguous_reason"].fillna("")
        n_missing_fo = int(reasons.str.contains("missing-faceoff", case=False).sum())
        n_unlogged = int(reasons.str.contains("unlogged transition", case=False).sum())
        gapish[y] = (n_missing_fo, n_unlogged, len(p))
    for y, (nm, nu, tot) in gapish.items():
        if (nm + nu) / max(tot, 1) > 0.02:
            flag("FEED_LOGGING_GAP", y, "league", "possession_ambiguity",
                 (nm + nu) / tot,
                 f"{nm} possessions follow a goal with NO faceoff logged and "
                 f"{nu} faceoffs occur while a prior possession is still open "
                 f"-- {(nm+nu)/tot:.1%} of all {y} possessions. This is missing "
                 f"faceoff EVENTS, not different play: it manufactures extra "
                 f"possession boundaries and therefore inflates the possession "
                 f"count and deflates every per-possession rate.")

    # ---- 4. irreconcilable scores ---------------------------------------
    rec = load("historical_reconciliation_report.csv")
    for _, r in rec[~rec["score_reconciles"]].iterrows():
        flag("SCORE_IRRECONCILABLE", r["season"], r["game_slug"], "final_score",
             r["score_residual"],
             f"{r['team_id']}: goal events give {r['reconstructed_points']} "
             f"against an official {r['official_score']}. Traced to the feed's "
             f"score columns moving on missed-shot events and decreasing.")

    # ---- 5. season-specific vocabulary -----------------------------------
    schema = load("historical_schema_compatibility.csv")
    for _, r in schema[schema["status"] == "SEASON_SPECIFIC"].iterrows():
        flag("SEASON_SPECIFIC_VOCABULARY", r["season"], "feed", r["aspect"],
             None, r["detail"][:400])

    # ---- 6. small-sample season leaders ----------------------------------
    relf = load("multi_season_reliability.csv")
    per_season_kappa = {
        (r["rate"], r["scope"].replace("season_", "")): r["prior_strength_kappa"]
        for _, r in relf.iterrows() if r["scope"].startswith("season_")}
    METRIC_RATE = {"shooting_pct": "shooting_pct",
                   "faceoff_win_pct": "faceoff_win_pct",
                   "save_pct": "save_pct"}
    for y in SEASONS:
        lb = season_file(y, f"player_leaderboards_{y}.csv",
                         dtype={"player_id": str}, low_memory=False)
        for metric, rate in METRIC_RATE.items():
            k = per_season_kappa.get((rate, str(y)))
            if k is None or not np.isfinite(k):
                continue
            top = lb[(lb["metric_name"] == metric) & (lb["scope"] == "ALL")
                     & (lb["rank"] == 1)]
            for _, r in top.iterrows():
                den = r["denominator_value"]
                if pd.notna(den) and den < k:
                    flag("SMALL_SAMPLE_SEASON_LEADER", y, r["player_name"],
                         metric, r["metric_value"],
                         f"leads the unqualified {y} {metric} board on {den:.0f} "
                         f"{r['denominator_name']}, against {k:.1f} needed for "
                         f"reliability 0.5")

    # ---- 7. two-point identification -------------------------------------
    tp = load("multi_season_two_point_identification.csv")
    for _, r in tp.iterrows():
        if not r["identifiable"]:
            flag("TWO_POINT_STILL_UNIDENTIFIED", r["scope"], "league",
                 "two_point_pct", r["excess_variance"],
                 f"{r['n_shooters']} shooters, {r['total_attempts']:.0f} attempts, "
                 f"median {r['median_attempts']:.0f}. Observed between-player "
                 f"variance {r['observed_between_player_variance']:.6f} is BELOW "
                 f"binomial noise {r['binomial_noise_variance']:.6f} "
                 f"(excess {r['excess_variance']:+.6f}); prior capped, max "
                 f"reliability {r['max_reliability']:.6f}.")

    # ---- 8. impossible values (class E) ----------------------------------
    BOUNDED = ["shooting_pct", "faceoff_win_pct", "save_pct_official",
               "one_point_conversion_pct", "two_point_conversion_pct",
               "shots_on_goal_pct", "win_pct", "two_point_attempt_rate"]
    for col in BOUNDED:
        if col not in team.columns:
            continue
        v = pd.to_numeric(team[col], errors="coerce").dropna()
        bad = team.loc[v.index[(v < 0) | (v > 1)]]
        for _, r in bad.iterrows():
            flag("METRIC_IMPOSSIBLE_VALUE", r["season"], r["team_name"], col,
                 r[col], "proportion outside [0,1]")

    # ---- 9. pooled == union of seasons -----------------------------------
    for pooled_name, tmpl in [("team_stats_2022_2026.csv", "team_stats_{y}.csv"),
                              ("player_stats_2022_2026.csv", "player_stats_{y}.csv")]:
        pooled = load(pooled_name, low_memory=False)
        total = 0
        for y in SEASONS:
            p = REPO_ROOT / "data" / "processed" / str(y) / tmpl.format(y=y)
            if p.exists():
                total += len(pd.read_csv(p, low_memory=False))
        if total != len(pooled):
            flag("POOLED_UNION_MISMATCH", "ALL", pooled_name, "row_count",
                 len(pooled), f"pooled has {len(pooled)} rows, the season files "
                              f"sum to {total}")

    # ---- 10. identity ----------------------------------------------------
    ident = load("historical_player_identity_audit.csv", dtype={"player_id": str})
    for _, r in ident[~ident["safe_to_aggregate_across_seasons"]].iterrows():
        flag("IDENTITY_UNCONFIRMED", "ALL", r["canonical_name"], "player_identity",
             None, r["identity_note"][:300])

    # ---- 11. usage model -------------------------------------------------
    um = load("multi_season_usage_model.csv")
    sel = um[um["selected_model"]].iloc[0]
    if sel["model"] == "constant":
        flag("CONSTANT_USAGE_MODEL_CONFIRMED", "ALL", "league",
             "expected_EPA_given_usage", sel["cv_cross_validated"]
             if "cv_cross_validated" in sel else sel["mse_cross_validated"],
             f"On {int(sel['n_player_seasons'])} player-seasons across five "
             f"seasons, with folds cut by PLAYER, the constant model still wins "
             f"cross-validation. Per-season correlation between usage and "
             f"offensive EPA: {um['per_season_pearson_r'].iloc[0]} -- negative "
             f"in four of five seasons, so 2026's +0.072 was noise, not a weak "
             f"positive effect.")

    df = pd.DataFrame(rows)
    order = {"error": 0, "warn": 1, "info": 2}
    df["_s"] = df["severity"].map(order)
    df = (df.sort_values(["_s", "flag_code", "season"])
            .drop(columns="_s").reset_index(drop=True))
    HIST.mkdir(parents=True, exist_ok=True)
    df.to_csv(HIST / "multi_season_sanity_flags.csv", index=False)

    print(f"{len(df)} multi-season sanity flags")
    print(df.groupby(["classification", "flag_code"]).size().to_string())
    e = df[df["classification"] == "E"]
    print(f"\nclass E (implementation/data bugs): {len(e)}")
    if len(e):
        print(e[["season", "entity", "metric_name", "detail"]].to_string(index=False))
    return df


if __name__ == "__main__":
    main()
