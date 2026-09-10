"""
Phase 7: statistical estimation for the usage / reliability layer.

Everything here produces a NUMBER that the SQL layer then joins, ranks or
partitions. Four estimators live in this module:

1. `null_variance_components` -- the variance each EPA_points component would
   have UNDER CHANCE ALONE at the player's own opportunity volume. This is the
   backbone of Phase 7. Every Phase 6 component is a sum of independent
   opportunity outcomes minus a fixed expectation, so its sampling variance is
   available in closed form from the same league baselines the component was
   built with. It gives:
     - a per-player standard error that scales correctly with volume,
     - the "how unusual is this given how many chances he had" standardization
       the Phase 7 brief asks for, and
     - a league-level signal-to-noise diagnostic: if the observed spread of a
       component is no wider than its null spread, the data contain no evidence
       that players differ on it at all.
   No resampling is used because none is needed: a bootstrap over the same 80
   shot outcomes estimates the same binomial variance with extra Monte Carlo
   noise on top.

2. `reliability_table` -- per-player, per-rate reliability. Reuses Phase 6's
   own empirical-Bayes estimator (imported, not reimplemented, so a change to
   Phase 6's shrinkage cannot silently diverge from Phase 7's reliability) and
   converts the prior strength into the standard reliability coefficient
   n / (n + kappa), i.e. the weight the posterior puts on the player's own
   record. Exact beta-posterior intervals accompany it.

3. `fit_usage_model` -- the empirical relationship between usage and value.
   Compares a constant, a linear and a quadratic mean function by 5-fold
   cross-validated mean squared error and keeps the simplest model that is not
   beaten out of sample. No functional form is assumed in advance.

4. `betainc` / `beta_quantile` -- the regularized incomplete beta function and
   its inverse, written out so the beta-posterior intervals are exact rather
   than normal approximations. This repo runs without scipy by choice; these
   are short enough to audit directly.

Deterministic: fixed seeds for every fold assignment; no unseeded randomness.
"""
from __future__ import annotations  # this repo runs on Python 3.9

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pll_player_value_models import (  # noqa: E402
    beta_prior_by_moments, empirical_bayes_rates,
)

SEED = 20260907
CV_FOLDS = 5

# A model must beat the simpler one by more than this relative margin in
# cross-validated MSE to be preferred. Same 1% rule Phase 6 used to reject the
# richer shot model, restated here so the two phases apply one standard.
MODEL_SELECTION_MARGIN = 0.01

# Reliability at which a rate is treated as sufficiently identified to rank
# players on. 0.5 is the point at which the empirical-Bayes posterior puts more
# weight on the player's own record than on the league prior -- i.e. where the
# observation carries more information than the assumption. It is a property of
# the estimator, not a round number chosen for convenience, and the trial count
# it corresponds to is DIFFERENT for every rate (16 draws, 71 shots, 300 shots
# on goal) because it is derived from each rate's own estimated prior strength.
RELIABILITY_RANKING_THRESHOLD = 0.5


# ---------------------------------------------------------------------------
# 0. Regularized incomplete beta, and its inverse
# ---------------------------------------------------------------------------
def _betacf(a: float, b: float, x: float, itmax: int = 300, eps: float = 3e-14) -> float:
    """Continued-fraction expansion for the incomplete beta (Lentz's method)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b) = P(Beta(a, b) <= x)."""
    if not (a > 0 and b > 0):
        return float("nan")
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_front = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                + a * math.log(x) + b * math.log1p(-x))
    front = math.exp(ln_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def beta_quantile(a: float, b: float, p: float, tol: float = 1e-10) -> float:
    """Inverse of `betainc` by bisection. Monotone and bounded, so bisection is
    both sufficient and immune to the convergence failures a Newton step can
    hit near 0 and 1 for very strong priors."""
    if not (a > 0 and b > 0) or not (0.0 < p < 1.0):
        return float("nan")
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if betainc(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# 1. Null (chance-alone) variance of each EPA_points component
# ---------------------------------------------------------------------------
def _baseline_lookup(baselines: pd.DataFrame) -> dict:
    return dict(zip(baselines["baseline_name"], baselines["baseline_value"]))


def null_variance_components(components: pd.DataFrame,
                             baselines: pd.DataFrame) -> pd.DataFrame:
    """Sampling variance of each Phase 6 component under the null hypothesis
    that the player converts his own opportunities at exactly the league rate.

    Each component is `observed - expected` where `expected` is a constant given
    the opportunity counts, so Var(component) = Var(observed), and `observed` is
    a sum of independent opportunity outcomes:

      shooting        a one-point attempt yields 1 point with probability p1
                      and a two-point attempt yields 2 with probability p2, so
                      Var = n1*p1*(1-p1) + n2*4*p2*(1-p2). The factor 4 is where
                      PLL two-point scoring enters: a two-point attempt is not
                      just rarer, it is a higher-variance bet.
      turnover        turnovers ~ Binomial(touches, group rate), scaled by the
                      turnover coefficient squared.
      faceoff         wins ~ Binomial(faceoffs, league win probability), scaled
                      by the marginal-win coefficient squared.
      caused turnover counts over games; modelled as Poisson with mean
                      games x group rate, which is the appropriate null for a
                      count with no natural denominator (there is no such thing
                      as a "caused-turnover chance" in this feed).
      goalie          the same structure as shooting, on shots on goal faced.

    This is the null for CHANCE, not a claim that every player is average. It is
    the yardstick against which "is this player's total unusual?" is answered.
    """
    b = _baseline_lookup(baselines)
    p1 = b["expected_points_per_one_point_attempt"]              # E[pts | 1pt attempt] == P(goal)
    p2 = b["expected_points_per_two_point_attempt"] / 2.0        # P(goal | 2pt attempt)
    q1 = b["expected_points_allowed_per_one_point_shot_on_goal"]
    q2 = b["expected_points_allowed_per_two_point_shot_on_goal"] / 2.0
    fo_p = b["faceoff_win_probability"]
    c_to = -b["event_value__turnover"]
    c_fo = 2 * b["event_value__faceoff_win"]

    to_rate = {k.replace("turnovers_per_touch__", ""): v for k, v in b.items()
               if k.startswith("turnovers_per_touch__")}
    ct_rate = {k.replace("caused_turnovers_per_game__", ""): v for k, v in b.items()
               if k.startswith("caused_turnovers_per_game__")}

    d = components
    r_to = d["baseline_group"].map(to_rate).astype(float)
    r_ct = d["baseline_group"].map(ct_rate).astype(float)

    out = pd.DataFrame({"player_id": d["player_id"]})
    out["shooting_value_null_variance"] = (
        d["one_point_attempts"] * p1 * (1 - p1)
        + d["two_point_attempts"] * 4.0 * p2 * (1 - p2))
    out["turnover_value_null_variance"] = (c_to ** 2) * d["touches"] * r_to * (1 - r_to)
    out["faceoff_value_null_variance"] = (c_fo ** 2) * d["faceoffs"] * fo_p * (1 - fo_p)
    out["caused_turnover_value_null_variance"] = (c_to ** 2) * d["games_played"] * r_ct
    out["goalie_value_null_variance"] = (
        d["one_point_shots_on_goal_faced"] * q1 * (1 - q1)
        + d["two_point_shots_on_goal_faced"] * 4.0 * q2 * (1 - q2))

    # NULL, not zero, wherever the component itself is NULL: a player who took
    # no draws has no faceoff sampling variance to report, and reporting 0 would
    # read as "his faceoff value is known exactly".
    for comp, opp in [("shooting_value", "shots"),
                      ("turnover_value", "touches"),
                      ("faceoff_value", "faceoffs"),
                      ("goalie_value", "shots_on_goal_faced")]:
        out.loc[d[opp].to_numpy() == 0, f"{comp}_null_variance"] = np.nan

    for c in [c for c in out.columns if c.endswith("_null_variance")]:
        out[c.replace("_variance", "_sd")] = np.sqrt(out[c])
    return out


def null_signal_to_noise(components: pd.DataFrame, nulls: pd.DataFrame,
                         value_col: str, variance_col: str,
                         opportunity_col: str) -> dict:
    """League-level identification diagnostic for one component.

    z_i = value_i / null_sd_i is, under chance alone, a draw with unit variance.
    So sd(z) over the league is 1.0 if nobody differs in ability and larger the
    more real between-player spread there is. The implied share of the observed
    variance that is real skill rather than sampling noise is 1 - 1/var(z),
    floored at 0 because a negative estimate means "no detectable spread".
    """
    m = components.merge(nulls, on="player_id")
    m = m[(m[opportunity_col] > 0) & m[value_col].notna() & (m[variance_col] > 0)]
    z = m[value_col].to_numpy(float) / np.sqrt(m[variance_col].to_numpy(float))
    var_z = float(np.var(z, ddof=1))
    return {
        "component": value_col,
        "n_players": int(len(z)),
        "total_opportunities": float(m[opportunity_col].sum()),
        "sd_of_null_standardized_value": float(np.sqrt(var_z)),
        "variance_ratio_observed_to_null": var_z,
        "implied_skill_share_of_variance": float(max(0.0, 1.0 - 1.0 / var_z)) if var_z > 0 else np.nan,
        "mean_null_standardized_value": float(z.mean()),
    }


# ---------------------------------------------------------------------------
# 2. Reliability
# ---------------------------------------------------------------------------
RATE_SPECS = [
    # (rate name, successes column, trials expression, human description)
    ("shooting_pct", "goals", "shots", "goals per shot attempt (all classes)"),
    ("one_point_pct", "one_point_goals", "one_point_attempts", "goals per one-point attempt"),
    ("two_point_pct", "two_point_goals", "two_point_attempts", "goals per two-point attempt"),
    ("faceoff_win_pct", "faceoff_wins", "faceoffs", "faceoffs won per faceoff taken"),
    ("save_pct", "saves", "save_denominator", "saves per shot on goal faced"),
]


def reliability_table(opportunities: pd.DataFrame) -> pd.DataFrame:
    """Long-format raw vs shrunk vs reliability for every rate, every player.

    reliability = n / (n + kappa) is the weight the empirical-Bayes posterior
    mean places on the player's own record; 1 - reliability is the weight it
    places on the league prior. It is the classical reliability coefficient for
    a binomial rate and it is derived entirely from the data: kappa is the prior
    strength the method of moments implies from the league's observed
    between-player spread net of binomial noise.

    Reported alongside: the exact 95% beta-posterior interval and its width,
    which is what actually tells a reader whether two players can be separated.
    """
    df = opportunities.copy()
    df["save_denominator"] = df["saves"] + df["goals_allowed"]
    rows = []
    for name, succ, trials, desc in RATE_SPECS:
        sub = df[df[trials] > 0]
        a, b = beta_prior_by_moments(sub[succ].to_numpy(), sub[trials].to_numpy())
        kappa = a + b
        for _, r in df.iterrows():
            n = float(r[trials])
            k = float(r[succ])
            has = n > 0
            post_a, post_b = a + k, b + (n - k)
            lo = beta_quantile(post_a, post_b, 0.025) if has else np.nan
            hi = beta_quantile(post_a, post_b, 0.975) if has else np.nan
            raw = k / n if has else np.nan
            shrunk = (k + a) / (n + kappa) if has else np.nan
            rows.append({
                "player_id": r["player_id"],
                "player_name": r["player_name"],
                "rate_name": name,
                "rate_description": desc,
                "successes": k if has else np.nan,
                "trials": n,
                "rate_raw": raw,
                "rate_shrunk": shrunk,
                "shrinkage_shift": (shrunk - raw) if has else np.nan,
                "prior_mean": a / kappa,
                "prior_strength_trials": kappa,
                "reliability": (n / (n + kappa)) if has else np.nan,
                "posterior_alpha": post_a if has else np.nan,
                "posterior_beta": post_b if has else np.nan,
                "posterior_ci_lo": lo,
                "posterior_ci_hi": hi,
                "posterior_ci_width": (hi - lo) if has else np.nan,
                "reliability_method": ("empirical-Bayes beta-binomial posterior weight "
                                       "n / (n + kappa); kappa by method of moments"),
                "interval_method": "exact 95% beta posterior quantiles",
            })
    out = pd.DataFrame(rows)
    return out.sort_values(["rate_name", "player_id"]).reset_index(drop=True)


def rate_identification_summary(reliability: pd.DataFrame) -> pd.DataFrame:
    """One row per rate: how identified is it league-wide, and how many players
    clear the reliability threshold."""
    rows = []
    for name, grp in reliability.groupby("rate_name"):
        has = grp[grp["trials"] > 0]
        kappa = float(grp["prior_strength_trials"].iloc[0])
        # implied true between-player sd of the rate under the beta prior
        mu = float(grp["prior_mean"].iloc[0])
        prior_var = mu * (1 - mu) / (kappa + 1.0)
        rows.append({
            "rate_name": name,
            "n_players_with_trials": int(len(has)),
            "total_trials": float(has["trials"].sum()),
            "median_trials": float(has["trials"].median()) if len(has) else np.nan,
            "max_trials": float(has["trials"].max()) if len(has) else np.nan,
            "prior_mean": mu,
            "prior_strength_trials": kappa,
            "implied_true_sd_between_players": float(np.sqrt(prior_var)),
            "trials_for_reliability_0_5": kappa,
            "n_players_reliability_ge_0_5": int((has["reliability"] >= RELIABILITY_RANKING_THRESHOLD).sum()),
            "mean_reliability": float(has["reliability"].mean()) if len(has) else np.nan,
            "max_reliability": float(has["reliability"].max()) if len(has) else np.nan,
            "raw_sd": float(has["rate_raw"].std()) if len(has) else np.nan,
            "shrunk_sd": float(has["rate_shrunk"].std()) if len(has) else np.nan,
            "identification": _identification_label(kappa, has),
        })
    return pd.DataFrame(rows).sort_values("prior_strength_trials").reset_index(drop=True)


def _identification_label(kappa: float, has: pd.DataFrame) -> str:
    """Verbal grade, stated as a rule rather than a judgement call.

    Deliberately COMPOUND, because two different things can be true at once and
    collapsing them into one adjective is how "partially identified" ends up
    meaning whatever the reader wants:

      part 1 -- does the league show any between-player spread beyond binomial
                noise at all? That is what a finite prior strength means.
      part 2 -- can INDIVIDUAL players be ranked on it? That is how many of
                them reach reliability 0.5, and it is a much harder test.

    Save percentage is the case that forces the distinction: real spread exists
    (the estimated true between-goalie sd is about 3 percentage points), yet
    only 1 of 16 goalies has faced enough shots for his own record to outweigh
    the prior.
    """
    if kappa >= 1e5:
        return ("no between-player spread beyond binomial noise: not identified, "
                "no player-level estimate is supportable")
    n = len(has)
    n_ok = int((has["reliability"] >= RELIABILITY_RANKING_THRESHOLD).sum()) if n else 0
    share = n_ok / n if n else 0.0
    grade = ("strong" if share >= 0.30 else
             "partial" if share >= 0.10 else
             "weak" if n_ok > 0 else "none")
    return (f"between-player spread detected (prior strength {kappa:.1f} trials); "
            f"individual identification {grade}: {n_ok}/{n} players "
            f"({share:.0%}) reach reliability 0.5")


# ---------------------------------------------------------------------------
# 3. The usage -> value relationship
# ---------------------------------------------------------------------------
def _design(x: np.ndarray, degree: int) -> np.ndarray:
    cols = [np.ones(len(x))]
    for d in range(1, degree + 1):
        cols.append(x ** d)
    return np.column_stack(cols)


def _ols(X: np.ndarray, y: np.ndarray, w: np.ndarray = None) -> np.ndarray:
    if w is None:
        w = np.ones(len(y))
    XtW = X.T * w
    return np.linalg.lstsq(XtW @ X, XtW @ y, rcond=None)[0]


def fit_usage_model(usage: np.ndarray, value: np.ndarray, weights: np.ndarray = None,
                    folds: int = CV_FOLDS, seed: int = SEED) -> tuple:
    """Choose a mean function for E[value | usage] by cross-validated MSE.

    Candidates are a constant, a straight line and a quadratic. No functional
    form is assumed: the constant is the null that "usage tells you nothing
    about expected value", and it is kept unless a curve beats it out of sample
    by more than MODEL_SELECTION_MARGIN.

    `weights`, when supplied, are 1 / null variance: the components are
    heteroskedastic BY CONSTRUCTION (a 90-shot player's value has ~7x the
    sampling variance of a 13-shot player's), so an unweighted fit lets the
    noisiest players dominate the slope. The weighted fit is run as the
    alternative in the sensitivity analysis; the published fit is unweighted so
    the reported expectation is the expectation for an actual player at that
    usage rather than for a precision-weighted composite.

    Returns (comparison table, fitted values under the selected model,
    coefficients, selected degree).
    """
    x = np.asarray(usage, dtype=float)
    y = np.asarray(value, dtype=float)
    n = len(x)
    rng = np.random.default_rng(seed)
    fold_id = rng.permutation(n) % folds
    w = np.ones(n) if weights is None else np.asarray(weights, dtype=float)

    rows, fitted, coeffs = [], {}, {}
    for degree, label in [(0, "constant"), (1, "linear"), (2, "quadratic")]:
        X = _design(x, degree)
        oof = np.zeros(n)
        for k in range(folds):
            tr, te = fold_id != k, fold_id == k
            beta = _ols(X[tr], y[tr], w[tr])
            oof[te] = X[te] @ beta
        beta_full = _ols(X, y, w)
        insample = X @ beta_full
        rows.append({
            "model": label,
            "degree": degree,
            "n_players": n,
            "mse_in_sample": float(np.mean((y - insample) ** 2)),
            "mse_cross_validated": float(np.mean((y - oof) ** 2)),
            "r2_in_sample": float(1 - ((y - insample) ** 2).sum() / ((y - y.mean()) ** 2).sum()),
            "cv_folds": folds,
            "coefficients": ",".join(f"{c:.6f}" for c in beta_full),
        })
        fitted[degree] = insample
        coeffs[degree] = beta_full

    cv = pd.DataFrame(rows)
    const_mse = cv.loc[cv["degree"] == 0, "mse_cross_validated"].iloc[0]
    cv["improvement_vs_constant"] = (const_mse - cv["mse_cross_validated"]) / const_mse

    selected = 0
    for degree in (1, 2):
        gain = cv.loc[cv["degree"] == degree, "improvement_vs_constant"].iloc[0]
        if gain > MODEL_SELECTION_MARGIN:
            selected = degree
    cv["selected_model"] = cv["degree"] == selected
    return cv, fitted[selected], coeffs[selected], selected


# ---------------------------------------------------------------------------
# 4. Standardization helpers (used by the validator's independent recomputation)
# ---------------------------------------------------------------------------
def robust_z(values: np.ndarray) -> np.ndarray:
    """(x - median) / (1.4826 * MAD). The 1.4826 makes the scale match a normal
    sd, so a robust z and an ordinary z are on the same footing when the
    distribution happens to be normal and diverge only when it is not."""
    v = np.asarray(values, dtype=float)
    med = np.nanmedian(v)
    mad = np.nanmedian(np.abs(v - med))
    scale = 1.4826 * mad
    if not np.isfinite(scale) or scale == 0:
        return np.full_like(v, np.nan)
    return (v - med) / scale


def midrank_percentile(values: np.ndarray) -> np.ndarray:
    """Empirical CDF percentile with ties given their mid-rank, expressed on
    0-100. Mid-ranks matter here: several positional groups have many players
    on identical small counts, and a naive rank would order them arbitrarily."""
    s = pd.Series(values, dtype=float)
    return (s.rank(method="average", na_option="keep") - 0.5) / s.notna().sum() * 100.0
