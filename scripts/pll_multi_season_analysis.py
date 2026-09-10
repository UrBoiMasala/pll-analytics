"""
Phase 9: multi-season analysis, 2022-2026.

The point of adding four seasons is not to make the dataset bigger. It is to
put the 2026-only conclusions under pressure. Every section below is written to
be capable of overturning a Phase 8 finding, and reports the answer either way.

Sections
  1. metric distributions by season   -- are the seasons even poolable?
  2. reliability / shrinkage          -- does more data identify these skills?
  3. year-to-year stability           -- does last season predict next season?
  4. usage model                      -- does the constant still win?
  5. two-point analysis               -- is two-point ability identifiable yet?
  6. opponent adjustment feasibility  -- is the schedule connected enough?

Writes to data/processed/history/:
    multi_season_metric_distributions.csv
    multi_season_reliability.csv
    player_year_to_year_stability.csv
    multi_season_usage_model.csv
    multi_season_two_point_analysis.csv
    multi_season_opponent_adjustment.csv
"""
import sys
from pathlib import Path

import warnings

import numpy as np
import pandas as pd

# The BLAS on some macOS builds emits spurious divide/overflow warnings from
# matmul on well-conditioned float64 arrays; the inputs are verified finite.
warnings.filterwarnings("ignore", category=RuntimeWarning, module="numpy")

REPO_ROOT = Path(__file__).resolve().parent.parent
HIST = REPO_ROOT / "data" / "processed" / "history"
SEASONS = [2022, 2023, 2024, 2025, 2026]

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Phase 6's own estimator, imported not reimplemented, so a pooled prior is
# directly comparable with the per-season priors Phases 6-8 published.
from pll_player_value_models import beta_prior_by_moments  # noqa: E402

RNG_SEED = 20260908

# The rate components re-estimated in section 2. (successes, trials) as they
# appear in player_stats_YEAR.csv.
RATE_SPECS = [
    ("shooting_pct", "goals", "shots"),
    ("one_point_pct", "one_point_goals", "one_point_attempts"),
    ("two_point_pct", "two_point_goals", "two_point_attempts"),
    ("save_pct", "saves", None),           # trials = saves + goals_allowed
    ("faceoff_win_pct", "faceoff_wins", "faceoffs"),
    ("turnovers_per_touch", "turnovers", "touches"),
]

# Team metrics whose season distribution decides poolability.
TEAM_METRICS = [
    "offensive_efficiency", "defensive_efficiency", "net_efficiency",
    "team_possessions_per_game", "shooting_pct", "shots_per_possession",
    "turnover_rate", "faceoff_win_pct", "save_pct_official",
    "one_point_conversion_pct", "two_point_attempt_rate",
    "two_point_conversion_pct", "points_per_shot", "points_per_game",
    "man_up_points_per_opportunity", "shots_on_goal_pct",
    "ground_balls_per_possession", "shot_clock_expiration_rate",
]


def load_pooled(name):
    return pd.read_csv(HIST / name, low_memory=False)


def player_pooled():
    df = load_pooled("player_stats_2022_2026.csv")
    df["player_id"] = df["player_id"].astype(str).str.zfill(6)
    return df


def trials_for(df, spec):
    """(successes, trials) series for one rate spec."""
    name, succ, tri = spec
    s = pd.to_numeric(df[succ], errors="coerce").fillna(0)
    if name == "save_pct":
        t = (pd.to_numeric(df["saves"], errors="coerce").fillna(0)
             + pd.to_numeric(df["goals_allowed"], errors="coerce").fillna(0))
    else:
        t = pd.to_numeric(df[tri], errors="coerce").fillna(0)
    return s, t


# ---------------------------------------------------------------------------
# 1. Distributions by season
# ---------------------------------------------------------------------------
def metric_distributions():
    team = load_pooled("team_stats_2022_2026.csv")
    rows = []
    for m in TEAM_METRICS:
        if m not in team.columns:
            continue
        by = team.groupby("season")[m]
        overall = pd.to_numeric(team[m], errors="coerce").dropna()
        gm = overall.mean()
        # between-season variance vs within-season variance: a crude but
        # honest one-way ANOVA F. With 5 seasons x 8 teams this is a weak
        # test and is reported as a descriptive ratio, not a p-value.
        groups = [pd.to_numeric(g, errors="coerce").dropna().to_numpy()
                  for _, g in by]
        groups = [g for g in groups if len(g) > 1]
        k = len(groups)
        n = sum(len(g) for g in groups)
        if k > 1 and n > k:
            ssb = sum(len(g) * (g.mean() - gm) ** 2 for g in groups)
            ssw = sum(((g - g.mean()) ** 2).sum() for g in groups)
            msb = ssb / (k - 1)
            msw = ssw / (n - k) if n > k else np.nan
            f = msb / msw if msw and msw > 0 else np.nan
            eta2 = ssb / (ssb + ssw) if (ssb + ssw) > 0 else np.nan
        else:
            f = eta2 = np.nan
        season_means = by.mean()
        rows.append({
            "metric": m,
            "pooled_mean": gm, "pooled_sd": overall.std(ddof=0),
            "n_team_seasons": len(overall),
            **{f"mean_{y}": season_means.get(y, np.nan) for y in SEASONS},
            "season_range": season_means.max() - season_means.min(),
            "between_season_F": f,
            "share_variance_between_seasons": eta2,
            "season_effect": (
                "material" if pd.notna(eta2) and eta2 >= 0.25 else
                "modest" if pd.notna(eta2) and eta2 >= 0.10 else "negligible"),
            "pooling_guidance": (
                "centre within season before pooling"
                if pd.notna(eta2) and eta2 >= 0.25 else
                "poolable; report the season mean alongside"
                if pd.notna(eta2) and eta2 >= 0.10 else
                "poolable as-is"),
        })
    return pd.DataFrame(rows).sort_values(
        "share_variance_between_seasons", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2. Reliability, 2026-only vs pooled
# ---------------------------------------------------------------------------
def reliability():
    p = player_pooled()
    rows = []
    for spec in RATE_SPECS:
        name = spec[0]
        for scope, sub in ([("2026_only", p[p["season"] == 2026])]
                           + [(f"season_{y}", p[p["season"] == y]) for y in SEASONS]
                           + [("pooled_player_seasons", p),
                              ("pooled_player_career", None)]):
            if scope == "pooled_player_career":
                # career totals: sum successes and trials per player across
                # every season in which identity is confirmed
                s_all, t_all = trials_for(p, spec)
                tmp = pd.DataFrame({"player_id": p["player_id"],
                                    "s": s_all, "t": t_all})
                agg = tmp.groupby("player_id").sum()
                s, t = agg["s"], agg["t"]
            else:
                s, t = trials_for(sub, spec)
            s, t = s.to_numpy(float), t.to_numpy(float)
            keep = t > 0
            if keep.sum() < 3:
                continue
            a, b = beta_prior_by_moments(s, t)
            kappa = a + b
            mu = a / (a + b) if (a + b) else np.nan
            tt = t[keep]
            rel = tt / (tt + kappa)
            # implied true between-player sd from the fitted prior
            true_var = mu * (1 - mu) / (kappa + 1) if kappa > 0 else np.nan
            rows.append({
                "rate": name, "scope": scope,
                "n_units_with_trials": int(keep.sum()),
                "total_trials": float(tt.sum()),
                "median_trials": float(np.median(tt)),
                "max_trials": float(tt.max()),
                "prior_mean": mu,
                "prior_strength_kappa": kappa,
                "trials_for_reliability_0_5": kappa,
                "implied_true_sd_between_players": np.sqrt(true_var)
                if pd.notna(true_var) else np.nan,
                "n_reaching_reliability_0_5": int((rel >= 0.5).sum()),
                "pct_reaching_reliability_0_5": 100 * float((rel >= 0.5).mean()),
                "mean_reliability": float(rel.mean()),
                "max_reliability": float(rel.max()),
                "identified": ("not identified: observed spread is no wider than "
                               "binomial noise, prior capped"
                               if kappa >= 1e5 else
                               "identified: between-player spread detected"),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. Year-to-year stability
# ---------------------------------------------------------------------------
def stability(min_trials=20, n_boot=2000):
    """Correlation of a player's rate in season t with season t+1.

    A naive correlation of two noisy rates is attenuated toward zero by
    measurement error, so the raw correlation UNDERSTATES persistence. Both are
    reported: the observed correlation, and a reliability-corrected version
    (Spearman's disattenuation) using the empirical-Bayes reliability of each
    year's estimate. The corrected figure is an upper bound and is labelled as
    MODELED, not observed.
    """
    p = player_pooled()
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for spec in RATE_SPECS:
        name = spec[0]
        s_all, t_all = trials_for(p, spec)
        d = pd.DataFrame({"player_id": p["player_id"], "season": p["season"],
                          "s": s_all, "t": t_all})
        d = d[d["t"] >= min_trials].copy()
        d["rate"] = d["s"] / d["t"]
        # prior strength from the pooled player-seasons, for disattenuation
        sa, ta = trials_for(p, spec)
        a, b = beta_prior_by_moments(sa.to_numpy(float), ta.to_numpy(float))
        kappa = a + b
        pairs = []
        for y in SEASONS[:-1]:
            cur = d[d["season"] == y][["player_id", "rate", "t"]]
            nxt = d[d["season"] == y + 1][["player_id", "rate", "t"]]
            m = cur.merge(nxt, on="player_id", suffixes=("_t", "_t1"))
            m["from_season"] = y
            pairs.append(m)
        allp = pd.concat(pairs, ignore_index=True) if pairs else pd.DataFrame()
        if len(allp) < 5:
            rows.append({"rate": name, "min_trials": min_trials, "n_pairs": len(allp),
                         "observed_r": np.nan, "note": "too few paired seasons"})
            continue
        x, y_ = allp["rate_t"].to_numpy(), allp["rate_t1"].to_numpy()
        r = float(np.corrcoef(x, y_)[0, 1])
        rho = float(np.corrcoef(pd.Series(x).rank(), pd.Series(y_).rank())[0, 1])
        rel_t = allp["t_t"] / (allp["t_t"] + kappa)
        rel_t1 = allp["t_t1"] / (allp["t_t1"] + kappa)
        denom = np.sqrt(rel_t.mean() * rel_t1.mean())
        r_corr = r / denom if denom > 0 else np.nan
        boot = np.array([
            np.corrcoef(x[i], y_[i])[0, 1]
            for i in (rng.integers(0, len(x), len(x)) for _ in range(n_boot))
        ])
        rows.append({
            "rate": name, "min_trials": min_trials, "n_pairs": len(allp),
            "n_players": allp["player_id"].nunique(),
            "median_trials_t": float(allp["t_t"].median()),
            "observed_r": r, "observed_spearman": rho,
            "boot_ci_low": float(np.nanpercentile(boot, 2.5)),
            "boot_ci_high": float(np.nanpercentile(boot, 97.5)),
            "mean_reliability_t": float(rel_t.mean()),
            "disattenuated_r_MODELED": min(r_corr, 1.0) if pd.notna(r_corr) else np.nan,
            "note": ("OBSERVED r is attenuated by measurement error; the "
                     "disattenuated figure is MODELED and is an upper bound"),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4. Usage model
# ---------------------------------------------------------------------------
def usage_model(n_folds=5):
    """Refit E[offensive EPA | usage] on 2022-2026 and compare constant /
    linear / quadratic by cross-validated MSE, exactly as Phase 7 did for 2026.

    Folds are cut by PLAYER, not by row, so the same player's five seasons
    cannot sit on both sides of a split and inflate the apparent fit.
    """
    p = player_pooled()
    pop = p[p["value_role"].isin(["offensive_field", "defensive_field"])
            & (pd.to_numeric(p["recorded_offensive_opportunities"],
                             errors="coerce").fillna(0) > 0)].copy()
    x = pd.to_numeric(pop["offensive_play_share"], errors="coerce").to_numpy(float)
    y = pd.to_numeric(pop["offensive_EPA_points_raw"], errors="coerce").to_numpy(float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    players = pop.loc[ok, "player_id"].to_numpy()
    seasons = pop.loc[ok, "season"].to_numpy()

    rng = np.random.default_rng(RNG_SEED)
    uniq = np.unique(players)
    fold_of = dict(zip(uniq, rng.integers(0, n_folds, len(uniq))))
    folds = np.array([fold_of[p_] for p_ in players])

    rows = []
    for degree, label in ((0, "constant"), (1, "linear"), (2, "quadratic")):
        cv_err, n_used = [], 0
        for f in range(n_folds):
            tr, te = folds != f, folds == f
            if te.sum() == 0 or tr.sum() <= degree + 1:
                continue
            coef = np.polyfit(x[tr], y[tr], degree) if degree > 0 else \
                np.array([y[tr].mean()])
            pred = np.polyval(coef, x[te]) if degree > 0 else \
                np.full(te.sum(), y[tr].mean())
            cv_err.append(((y[te] - pred) ** 2).sum())
            n_used += te.sum()
        cv_mse = sum(cv_err) / n_used if n_used else np.nan
        coef_full = (np.polyfit(x, y, degree) if degree > 0
                     else np.array([y.mean()]))
        pred_full = (np.polyval(coef_full, x) if degree > 0
                     else np.full(len(y), y.mean()))
        ss_res = ((y - pred_full) ** 2).sum()
        ss_tot = ((y - y.mean()) ** 2).sum()
        rows.append({
            "model": label, "degree": degree,
            "n_player_seasons": len(y), "n_players": len(uniq),
            "cv_folds": n_folds, "fold_unit": "player (not row)",
            "mse_in_sample": ss_res / len(y),
            "mse_cross_validated": cv_mse,
            "r2_in_sample": 1 - ss_res / ss_tot if ss_tot else np.nan,
            "coefficients": ",".join(f"{c:.6g}" for c in coef_full),
            "pearson_r_usage_vs_offensive_EPA": float(np.corrcoef(x, y)[0, 1]),
            "spearman_r_usage_vs_offensive_EPA": float(
                np.corrcoef(pd.Series(x).rank(), pd.Series(y).rank())[0, 1]),
            "population": "field players with >=1 recorded offensive opportunity, 2022-2026",
        })
    df = pd.DataFrame(rows)
    best = df.loc[df["mse_cross_validated"].idxmin(), "model"]
    df["selected_model"] = df["model"] == best
    df["improvement_vs_constant"] = (
        df.loc[df["model"] == "constant", "mse_cross_validated"].iloc[0]
        - df["mse_cross_validated"])

    # does the answer hold season by season?
    per = []
    for yy in SEASONS:
        m = seasons == yy
        if m.sum() < 20:
            continue
        per.append({"season": yy, "n": int(m.sum()),
                    "pearson_r": float(np.corrcoef(x[m], y[m])[0, 1])})
    ps = pd.DataFrame(per)
    df["per_season_pearson_r"] = "; ".join(
        f"{r.season}:{r.pearson_r:+.3f}" for r in ps.itertuples())
    return df


# ---------------------------------------------------------------------------
# 5. Two-point
# ---------------------------------------------------------------------------
def two_point():
    team = load_pooled("team_stats_2022_2026.csv")
    p = player_pooled()
    rows = []

    def wilson(k, n, z=1.96):
        if n <= 0:
            return (np.nan, np.nan)
        den = n + z * z
        c = (k + z * z / 2) / den
        h = z / den * np.sqrt(k * (n - k) / n + z * z / 4)
        return (c - h, c + h)

    for y in SEASONS + ["POOLED"]:
        t = team if y == "POOLED" else team[team["season"] == y]
        oa, og = t["one_point_attempts"].sum(), t["one_point_goals"].sum()
        ta, tg = t["two_point_attempts"].sum(), t["two_point_goals"].sum()
        lo, hi = wilson(tg, ta)
        rows.append({
            "scope": str(y),
            "one_point_attempts": int(oa), "one_point_goals": int(og),
            "two_point_attempts": int(ta), "two_point_goals": int(tg),
            "two_point_attempt_share": ta / (oa + ta) if (oa + ta) else np.nan,
            "one_point_conversion": og / oa if oa else np.nan,
            "two_point_conversion": tg / ta if ta else np.nan,
            "two_point_conversion_wilson_low": lo,
            "two_point_conversion_wilson_high": hi,
            "points_per_one_point_attempt": og / oa if oa else np.nan,
            "points_per_two_point_attempt": 2 * tg / ta if ta else np.nan,
            "two_point_minus_one_point_return":
                (2 * tg / ta - og / oa) if (ta and oa) else np.nan,
        })
    league = pd.DataFrame(rows)

    # player level: is ability identifiable, per season and pooled?
    ident_rows = []
    spec = ("two_point_pct", "two_point_goals", "two_point_attempts")
    for scope in [str(y) for y in SEASONS] + ["POOLED_SEASONS", "POOLED_CAREER"]:
        if scope == "POOLED_SEASONS":
            sub = p
        elif scope == "POOLED_CAREER":
            s_all, t_all = trials_for(p, spec)
            agg = pd.DataFrame({"player_id": p["player_id"], "s": s_all,
                                "t": t_all}).groupby("player_id").sum()
            s, t = agg["s"].to_numpy(float), agg["t"].to_numpy(float)
            sub = None
        else:
            sub = p[p["season"] == int(scope)]
        if sub is not None:
            s, t = trials_for(sub, spec)
            s, t = s.to_numpy(float), t.to_numpy(float)
        keep = t > 0
        if keep.sum() < 3:
            continue
        a, b = beta_prior_by_moments(s, t)
        kappa = a + b
        mu = a / (a + b)
        rel = t[keep] / (t[keep] + kappa)
        # the diagnostic that decides identification
        rates = s[keep] / t[keep]
        w = t[keep] / t[keep].sum()
        obs_var = float(np.sum(w * (rates - mu) ** 2))
        bin_var = float(np.sum(w * mu * (1 - mu) / t[keep]))
        ident_rows.append({
            "scope": scope, "n_shooters": int(keep.sum()),
            "total_attempts": float(t[keep].sum()),
            "median_attempts": float(np.median(t[keep])),
            "max_attempts": float(t[keep].max()),
            "observed_between_player_variance": obs_var,
            "binomial_noise_variance": bin_var,
            "excess_variance": obs_var - bin_var,
            "prior_strength_kappa": kappa,
            "max_reliability": float(rel.max()),
            "n_reaching_reliability_0_5": int((rel >= 0.5).sum()),
            "identifiable": bool(obs_var > bin_var and kappa < 1e5),
            "verdict": ("IDENTIFIABLE: observed spread exceeds binomial noise"
                        if (obs_var > bin_var and kappa < 1e5) else
                        "NOT IDENTIFIABLE: observed spread does not exceed "
                        "binomial noise; no player-level ability estimate is "
                        "supportable at this sample"),
        })
    return league, pd.DataFrame(ident_rows)


# ---------------------------------------------------------------------------
# 6. Opponent adjustment feasibility
# ---------------------------------------------------------------------------
def opponent_adjustment(n_boot=400):
    """Is opponent adjustment worth implementing for 2022-2026?

    Feasibility has two separate questions, and they have different answers.

    (1) IS IT IDENTIFIABLE?  It needs a connected schedule graph. PLL plays an
        8-team near-round-robin, so every one of the 28 possible pairings
        occurs in every season: connectivity is 1.00, the best possible case.

    (2) IS IT WORTH ANYTHING?  A perfectly balanced schedule leaves almost
        nothing to adjust FOR. The measure that matters is the spread in the
        strength of opposition each team actually faced. If every team faces
        essentially the same slate, the adjustment is inert by construction and
        adding it buys complexity without buying accuracy.

    Fitted as a ridge-regularised two-way model of team-game offensive
    efficiency on offence and defence indicators, with the ratings centred to
    sum to zero so "adjustment" means "relative to the league", and bootstrapped
    over GAMES so the reported movement carries its own uncertainty.
    """
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for y in SEASONS:
        D = REPO_ROOT / "data" / "processed" / str(y)
        tga = pd.read_csv(D / "team_game_advanced.csv")
        g = pd.read_csv(D / "games.csv")
        el = set(g[g["is_completed"] & g["include_in_league_analytics"]
                   & ~g["is_all_star"]]["game_id"])
        t = tga[tga["game_id"].isin(el)].copy()
        t["off"] = pd.to_numeric(t["offensive_efficiency"], errors="coerce")
        t = t[np.isfinite(t["off"])]
        teams = sorted(set(t["team_id"]) | set(t["opponent_team_id"]))
        idx = {tm: i for i, tm in enumerate(teams)}
        k = len(teams)

        def fit(sub):
            n = len(sub)
            X = np.zeros((n, 2 * k), dtype=float)
            for i, r in enumerate(sub.itertuples()):
                X[i, idx[r.team_id]] = 1.0
                X[i, k + idx[r.opponent_team_id]] = 1.0
            yv = sub["off"].to_numpy(dtype=float)
            mu = yv.mean()
            lam = 1.0
            with np.errstate(all="ignore"):   # spurious BLAS warnings on macOS
                A = X.T @ X + lam * np.eye(2 * k)
                beta = np.linalg.solve(A, X.T @ (yv - mu))
            off = beta[:k] - beta[:k].mean()      # centre: sum-to-zero
            return off, mu

        off, mu = fit(t)
        raw = t.groupby("team_id")["off"].mean().reindex(teams)
        adj = pd.Series(off + mu, index=teams)
        both = pd.DataFrame({"raw": raw, "adj": adj}).dropna()
        rank_change = (both["raw"].rank(ascending=False)
                       - both["adj"].rank(ascending=False)).abs()

        # --- schedule balance: spread in strength of opposition faced -------
        opp_strength = t.groupby("opponent_team_id")["off"].mean()
        faced = t.groupby("team_id")["opponent_team_id"].apply(
            lambda s: opp_strength.reindex(s).mean())
        sos_sd = float(faced.std(ddof=0))

        # --- bootstrap over GAMES -------------------------------------------
        games = t["game_id"].unique()
        boot = []
        for _ in range(n_boot):
            pick = rng.choice(games, len(games), replace=True)
            sub = pd.concat([t[t["game_id"] == gg] for gg in pick],
                            ignore_index=True)
            try:
                b, _ = fit(sub)
                boot.append(b)
            except np.linalg.LinAlgError:
                continue
        boot = np.array(boot) if boot else np.zeros((0, k))
        adj_se = boot.std(axis=0, ddof=1) if len(boot) > 2 else np.full(k, np.nan)

        pairs = {tuple(sorted((r.team_id, r.opponent_team_id)))
                 for r in t.itertuples()}
        possible = k * (k - 1) / 2
        rows.append({
            "scope": str(y), "n_team_games": len(t), "n_teams": k,
            "distinct_opponent_pairs": len(pairs),
            "possible_pairs": int(possible),
            "schedule_connectivity": len(pairs) / possible if possible else np.nan,
            "games_per_team": len(t) / k,
            "strength_of_schedule_sd": sos_sd,
            "raw_sd": float(both["raw"].std(ddof=0)),
            "sos_sd_as_share_of_raw_sd":
                sos_sd / both["raw"].std(ddof=0) if both["raw"].std(ddof=0) else np.nan,
            "adjustment_sd": float(np.std(off)),
            "mean_bootstrap_se_of_adjustment": float(np.nanmean(adj_se)),
            "adjustment_signal_to_noise":
                float(np.std(off) / np.nanmean(adj_se)) if np.nanmean(adj_se) else np.nan,
            "max_rank_change": float(rank_change.max()),
            "mean_rank_change": float(rank_change.mean()),
            "spearman_raw_vs_adjusted": float(np.corrcoef(
                both["raw"].rank(), both["adj"].rank())[0, 1]),
            "n_bootstrap": len(boot),
        })
    df = pd.DataFrame(rows)
    df["verdict"] = np.where(
        df["adjustment_signal_to_noise"] >= 1.0,
        "identifiable AND the adjustment exceeds its own bootstrap error",
        "identifiable but the adjustment is SMALLER than its own bootstrap "
        "standard error -- fitting it would add a number less reliable than the "
        "unadjusted one")
    df["pooling_note"] = (
        "Opponent effects are estimated WITHIN a season. Pooling seasons into "
        "one opponent model would treat a 2022 roster and a 2026 roster as the "
        "same unit, which they are not; extra seasons replicate the feasibility "
        "question rather than adding connectivity to a single graph.")
    return df


def main():
    HIST.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 250)

    dist = metric_distributions()
    dist.to_csv(HIST / "multi_season_metric_distributions.csv", index=False)
    print("=== 1. SEASON EFFECTS (share of variance between seasons) ===")
    print(dist[["metric"] + [f"mean_{y}" for y in SEASONS]
               + ["share_variance_between_seasons", "season_effect"]]
          .round(4).to_string(index=False))

    rel = reliability()
    rel.to_csv(HIST / "multi_season_reliability.csv", index=False)
    print("\n=== 2. RELIABILITY: 2026-only vs pooled ===")
    show = rel[rel["scope"].isin(["2026_only", "pooled_player_seasons",
                                  "pooled_player_career"])]
    print(show[["rate", "scope", "n_units_with_trials", "total_trials",
                "prior_strength_kappa", "n_reaching_reliability_0_5",
                "implied_true_sd_between_players"]].round(3).to_string(index=False))

    stab = stability()
    stab.to_csv(HIST / "player_year_to_year_stability.csv", index=False)
    print("\n=== 3. YEAR-TO-YEAR STABILITY ===")
    print(stab[["rate", "n_pairs", "n_players", "median_trials_t", "observed_r",
                "boot_ci_low", "boot_ci_high", "disattenuated_r_MODELED"]]
          .round(3).to_string(index=False))

    um = usage_model()
    um.to_csv(HIST / "multi_season_usage_model.csv", index=False)
    print("\n=== 4. USAGE MODEL (2022-2026) ===")
    print(um[["model", "n_player_seasons", "mse_in_sample",
              "mse_cross_validated", "r2_in_sample", "selected_model"]]
          .round(5).to_string(index=False))
    print("  per-season r:", um["per_season_pearson_r"].iloc[0])

    league, ident = two_point()
    league.to_csv(HIST / "multi_season_two_point_analysis.csv", index=False)
    ident.to_csv(HIST / "multi_season_two_point_identification.csv", index=False)
    print("\n=== 5. TWO-POINT: league ===")
    print(league.round(4).to_string(index=False))
    print("\n=== 5b. TWO-POINT: identification ===")
    print(ident[["scope", "n_shooters", "total_attempts", "median_attempts",
                 "observed_between_player_variance", "binomial_noise_variance",
                 "excess_variance", "prior_strength_kappa", "max_reliability",
                 "identifiable"]].round(6).to_string(index=False))

    oa = opponent_adjustment()
    oa.to_csv(HIST / "multi_season_opponent_adjustment.csv", index=False)
    print("\n=== 6. OPPONENT ADJUSTMENT FEASIBILITY ===")
    print(oa[["scope", "n_team_games", "schedule_connectivity",
              "strength_of_schedule_sd", "raw_sd", "sos_sd_as_share_of_raw_sd",
              "adjustment_sd", "mean_bootstrap_se_of_adjustment",
              "adjustment_signal_to_noise", "max_rank_change",
              "spearman_raw_vs_adjusted"]].round(4).to_string(index=False))
    print("  verdict:", oa["verdict"].iloc[0])
    return dist, rel, stab, um, league, ident, oa


if __name__ == "__main__":
    main()
