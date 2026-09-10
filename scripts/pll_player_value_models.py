"""
Phase 6: statistical estimation for the player-value framework.

Everything in this module estimates a NUMBER that the SQL layer then applies.
Three estimators live here:

1. `estimate_event_values` -- the empirical net-scoring value of each event
   type, in PLL points, using the forward-window method Lacrosse Reference
   documents publicly (count PLL points for and against in the next 60 seconds
   of game clock after each event; value = (for - against) / occurrences).
   This is what makes the turnover and faceoff coefficients EMPIRICAL rather
   than invented. Values are reported net of a measured neutral reference (the
   same statistic over all team-attributed events), so each coefficient is a
   deviation from the average game state rather than from an assumed zero.

2. `fit_shot_models` -- the expected-points-per-shot model. Compares the simple
   two-class empirical baseline (one-point vs two-point attempt) against a
   logistic model with game-state features, using 5-fold cross-validated Brier
   score. The simple model is kept unless the richer one materially beats it.

3. `empirical_bayes_rates` -- beta-binomial shrinkage for the unstable rate
   statistics (shooting %, two-point %, save %, faceoff %), estimated by method
   of moments so the prior is derived from the league data rather than assumed.

No scipy/sklearn: the logistic fit is plain IRLS and the beta prior is a
closed-form moment match, both short enough to audit directly. That is a
deliberate choice -- these are small, transparent estimators and an opaque
dependency would make the numbers harder, not easier, to check.

Deterministic: fixed seeds for every bootstrap and every CV fold assignment.
"""
from __future__ import annotations  # this repo runs on Python 3.9

from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"

FORWARD_WINDOW_SECONDS = 60
N_BOOTSTRAP = 2000
SEED = 20260907
CV_FOLDS = 5

# Event classes valued by the forward-window method. Every class is defined
# from columns that Phases 1-5 already validated; none is a new classifier.
EVENT_CLASSES = {
    "faceoff_win": "a faceoff event (recorded for the winning team)",
    "ground_ball": "a ground-ball recovery",
    "shot_missed": "a shot that missed the goal",
    "shot_saved": "a shot saved by the goalie",
    "shot_on_goal_no_save": "a shot on goal recorded as neither saved nor a goal",
    "goal_1pt": "a one-point goal",
    "goal_2pt": "a two-point goal",
    "turnover": "a turnover",
    "shot_clock_expiration": "a shot-clock violation",
    "penalty": "a penalty committed",
}


# ---------------------------------------------------------------------------
# Shared loading
# ---------------------------------------------------------------------------
def load_eligible_events(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    events = pd.read_csv(
        data_dir / "events.csv", low_memory=False,
        dtype={"team_id": str, "player_id": str, "goalie_id": str,
               "gb_player_id": str, "event_id": str},
    )
    games = pd.read_csv(data_dir / "games.csv")
    eligible = set(games.loc[games["is_completed"] & games["include_in_league_analytics"]
                             & ~games["is_all_star"], "game_id"])
    ev = events[(events["is_analysis_eligible_event"] == True)  # noqa: E712
                & events["game_id"].isin(eligible)].copy()
    ev["is_goal"] = ev["is_valid_goal"] == True  # noqa: E712
    ev["is_two_point"] = ev["is_two_point_attempt"] == True  # noqa: E712
    ev["pll_points"] = np.where(ev["is_goal"], np.where(ev["is_two_point"], 2, 1), 0)
    ev["is_shot_on_goal"] = ev["shot_outcome"].isin(["goal", "saved", "on_goal_no_save"])
    return ev


def classify_events(ev: pd.DataFrame) -> pd.Series:
    """Map each event to one of EVENT_CLASSES, or NaN if it is not valued."""
    cls = pd.Series(np.nan, index=ev.index, dtype=object)
    is_shot = ev["event_type"].isin(["shot", "goal"])
    cls[is_shot & (ev["shot_outcome"] == "missed")] = "shot_missed"
    cls[is_shot & (ev["shot_outcome"] == "saved")] = "shot_saved"
    cls[is_shot & (ev["shot_outcome"] == "on_goal_no_save")] = "shot_on_goal_no_save"
    cls[is_shot & ev["is_goal"] & ~ev["is_two_point"]] = "goal_1pt"
    cls[is_shot & ev["is_goal"] & ev["is_two_point"]] = "goal_2pt"
    cls[ev["event_type"] == "turnover"] = "turnover"
    cls[ev["event_type"] == "groundball"] = "ground_ball"
    cls[ev["event_type"] == "faceoff"] = "faceoff_win"
    cls[ev["event_type"] == "shotclockexpired"] = "shot_clock_expiration"
    cls[(ev["event_type"] == "penalty") & (ev["is_valid_penalty"] == True)] = "penalty"  # noqa: E712
    return cls


# ---------------------------------------------------------------------------
# 1. Forward-window event values
# ---------------------------------------------------------------------------
def _forward_window_net_points(ev: pd.DataFrame, window: int,
                               goal_source: pd.DataFrame = None) -> np.ndarray:
    """Net PLL points (acting team minus opponent) scored in the `window`
    seconds of game clock after each event, within the same period.

    `goal_source` supplies the goal timeline and MUST be the full eligible
    event frame. It defaults to `ev` only for the case where `ev` already is
    that frame -- passing a filtered subset (e.g. only ground balls) without
    it would silently produce an empty goal timeline and value every event at
    zero.

    Restricted to the same period on purpose: the clock resets between periods
    and a possession never crosses one (POSSESSION_METHODOLOGY.md), so a window
    that spanned the break would count points from a different game state.
    """
    if goal_source is None:
        goal_source = ev
    goals = goal_source.loc[goal_source["is_goal"],
                            ["game_id", "period", "seconds_passed", "team_id", "pll_points"]]
    by_period = {k: (v["seconds_passed"].to_numpy(),
                     v["team_id"].to_numpy(),
                     v["pll_points"].to_numpy())
                 for k, v in goals.groupby(["game_id", "period"])}
    out = np.zeros(len(ev), dtype=float)
    for i, (gid, per, t0, team) in enumerate(zip(
            ev["game_id"], ev["period"], ev["seconds_passed"], ev["team_id"])):
        entry = by_period.get((gid, per))
        if entry is None:
            continue
        secs, teams, pts = entry
        sel = (secs > t0) & (secs <= t0 + window)
        if not sel.any():
            continue
        p, tm = pts[sel], teams[sel]
        out[i] = p[tm == team].sum() - p[tm != team].sum()
    return out


def estimate_event_values(ev: pd.DataFrame | None = None,
                          window: int = FORWARD_WINDOW_SECONDS,
                          n_boot: int = N_BOOTSTRAP,
                          seed: int = SEED) -> pd.DataFrame:
    """Empirical net PLL points per event type, with bootstrap intervals.

    Also returns the neutral reference: the same statistic computed over every
    team-attributed event. Each event class's `value_vs_neutral` is its raw
    mean minus that reference, so a coefficient of 0 means "this event leaves
    the scoring outlook exactly where an average moment of play would".
    """
    if ev is None:
        ev = load_eligible_events()
    ev = ev.copy()
    ev["event_class"] = classify_events(ev)
    valued = ev[ev["event_class"].notna() & ev["team_id"].notna()].copy()
    valued["net_points"] = _forward_window_net_points(valued, window, goal_source=ev)

    # Window is truncated when the period ends before `window` seconds elapse.
    period_end = ev.groupby(["game_id", "period"])["seconds_passed"].max().rename("period_end")
    valued = valued.merge(period_end, on=["game_id", "period"], how="left")
    valued["window_truncated"] = (valued["period_end"] - valued["seconds_passed"]) < window

    rng = np.random.default_rng(seed)
    neutral = float(valued["net_points"].mean())

    rows = []
    for cls, grp in valued.groupby("event_class"):
        x = grp["net_points"].to_numpy(dtype=float)
        n = len(x)
        boot = np.array([rng.choice(x, size=n, replace=True).mean() for _ in range(n_boot)])
        untrunc = grp.loc[~grp["window_truncated"], "net_points"]
        rows.append({
            "event_class": cls,
            "description": EVENT_CLASSES.get(cls, ""),
            "n_events": n,
            "n_window_truncated": int(grp["window_truncated"].sum()),
            "points_for": float(grp["net_points"].clip(lower=0).sum()),
            "mean_net_points": float(x.mean()),
            "std_net_points": float(x.std(ddof=1)),
            "se_net_points": float(x.std(ddof=1) / np.sqrt(n)),
            "boot_ci_lo": float(np.percentile(boot, 2.5)),
            "boot_ci_hi": float(np.percentile(boot, 97.5)),
            "mean_net_points_untruncated_window": float(untrunc.mean()) if len(untrunc) else np.nan,
            "neutral_reference": neutral,
            "value_vs_neutral": float(x.mean() - neutral),
        })
    out = pd.DataFrame(rows).sort_values("value_vs_neutral", ascending=False)
    out["window_seconds"] = window
    out["n_bootstrap"] = n_boot
    return out.reset_index(drop=True)


def ground_ball_context_values(ev: pd.DataFrame, possessions: pd.DataFrame,
                               window: int = FORWARD_WINDOW_SECONDS) -> pd.DataFrame:
    """Forward-window value of a ground ball split by the only three contexts
    the feed can actually distinguish:

      GB_faceoff_scrum       -- the event immediately follows a faceoff
      GB_possession_gaining  -- the event opens a new possession
      GB_retained_possession -- neither: the recovering team already had the ball

    Used to decide whether a context-specific ground-ball model is supportable
    (PLAYER_VALUE_METHODOLOGY.md "Ground balls").
    """
    ev = ev.copy()
    faceoff_keys = set(zip(ev.loc[ev["event_type"] == "faceoff", "game_slug"],
                           ev.loc[ev["event_type"] == "faceoff", "event_number"]))
    start_ids = set(possessions["start_event_id"])
    gb = ev[ev["event_type"] == "groundball"].copy()
    gb["post_faceoff"] = [(gs, en - 1) in faceoff_keys
                          for gs, en in zip(gb["game_slug"], gb["event_number"])]
    gb["starts_possession"] = gb["event_id"].isin(start_ids)
    gb["context"] = np.where(
        gb["post_faceoff"], "GB_faceoff_scrum",
        np.where(gb["starts_possession"], "GB_possession_gaining", "GB_retained_possession"))
    gb["net_points"] = _forward_window_net_points(gb, window, goal_source=ev)

    rows = []
    for ctx, grp in gb.groupby("context"):
        x = grp["net_points"].to_numpy(dtype=float)
        se = x.std(ddof=1) / np.sqrt(len(x))
        rows.append({"context": ctx, "n": len(x), "mean_net_points": float(x.mean()),
                     "se": float(se), "ci_lo": float(x.mean() - 1.96 * se),
                     "ci_hi": float(x.mean() + 1.96 * se)})
    return pd.DataFrame(rows).sort_values("mean_net_points", ascending=False).reset_index(drop=True)


def faceoff_ground_ball_overlap(ev: pd.DataFrame) -> dict:
    """How often the ground ball following a faceoff is recovered by the
    faceoff-winning team, and by the winner himself. This is the evidence for
    the ground-ball / faceoff double-counting decision."""
    fo = ev[ev["event_type"] == "faceoff"]
    fo_map = {(gs, en): (t, str(p)) for gs, en, t, p in
              zip(fo["game_slug"], fo["event_number"], fo["team_id"], fo["player_id"])}
    gb = ev[ev["event_type"] == "groundball"]
    same_team = same_player = total = 0
    for gs, en, t, p in zip(gb["game_slug"], gb["event_number"], gb["team_id"], gb["player_id"]):
        hit = fo_map.get((gs, en - 1))
        if hit is None:
            continue
        total += 1
        same_team += int(hit[0] == t)
        same_player += int(hit[1] == str(p))
    return {"post_faceoff_ground_balls": total,
            "recovered_by_faceoff_winning_team": same_team,
            "recovered_by_faceoff_winner_himself": same_player,
            "share_same_team": same_team / total if total else np.nan,
            "share_same_player": same_player / total if total else np.nan}


# ---------------------------------------------------------------------------
# 2. Shot model
# ---------------------------------------------------------------------------
def _irls_logistic(X: np.ndarray, y: np.ndarray, ridge: float = 1e-4,
                   max_iter: int = 50, tol: float = 1e-9) -> np.ndarray:
    """Plain iteratively-reweighted-least-squares logistic regression with a
    small ridge term for numerical stability. Returns the coefficient vector."""
    assert np.isfinite(X).all() and np.isfinite(y).all(), "non-finite input to IRLS"
    beta = np.zeros(X.shape[1])
    # numpy 2.0.2 on macOS/Accelerate raises spurious divide-by-zero, overflow
    # and invalid-value RuntimeWarnings from plain matmul even when every input
    # is finite and the result is exactly zero (reproducible with
    # np.ones((n, p)) @ np.zeros(p)). The assert above is the real guard on the
    # inputs; this only silences the BLAS artifact.
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        for _ in range(max_iter):
            # clip the linear predictor: an unbounded eta overflows exp() and
            # turns the whole fit into NaN, which is easy to miss because the
            # Brier score still returns a number.
            eta = np.clip(X @ beta, -30.0, 30.0)
            mu = 1.0 / (1.0 + np.exp(-eta))
            # Floor the IRLS weights well above zero: a near-separated
            # observation drives w toward 0, and the working response
            # z = eta + (y-mu)/w then overflows to inf and poisons the normal
            # equations with NaN.
            w = np.clip(mu * (1 - mu), 1e-6, None)
            z = np.clip(eta + (y - mu) / w, -1e6, 1e6)
            XtW = X.T * w
            try:
                new = np.linalg.solve(XtW @ X + ridge * np.eye(X.shape[1]), XtW @ z)
            except np.linalg.LinAlgError:
                break
            if not np.isfinite(new).all():
                break
            if np.max(np.abs(new - beta)) < tol:
                beta = new
                break
            beta = new
    return beta


def _predict(X: np.ndarray, beta: np.ndarray) -> np.ndarray:
    """Logistic prediction, shielded from the spurious Accelerate matmul
    warnings described in `_irls_logistic`."""
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        return 1.0 / (1.0 + np.exp(-np.clip(X @ beta, -30.0, 30.0)))


def _brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def _shot_feature_frame(ev: pd.DataFrame, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Attempt-level features. Deliberately short: the 2026 feed carries NO
    shot location, distance or defender information (verified across all 51 raw
    games -- the only populated shot `details` keys are shotOnGoal/shotSaved/
    saveType), and the man-up shot_type tags appear on goals only, so man-up
    state is not observable at attempt time. What is left is the shot's point
    value and the game state around it."""
    shots = ev[ev["event_type"].isin(["shot", "goal"]) & ev["shot_outcome"].notna()].copy()
    games = pd.read_csv(data_dir / "games.csv")
    if games["game_id"].duplicated().any():
        raise ValueError("Duplicate game metadata")
    if not shots["game_id"].isin(games["game_id"]).all():
        raise ValueError("Shot events do not match season game metadata")
    home = games.set_index("game_id")["home_team_id"].to_dict()
    is_home = np.array([home.get(g) == t for g, t in zip(shots["game_id"], shots["team_id"])])
    home_sc = shots["home_score_corrected"].fillna(0).to_numpy(dtype=float)
    away_sc = shots["away_score_corrected"].fillna(0).to_numpy(dtype=float)
    # The feed's score columns ALREADY INCLUDE the goal on the row itself
    # (verified: the first goal of 2026-ev-1 carries away_score 1). Using them
    # raw would leak the shot's own outcome into a model that is supposed to
    # predict it -- a goal would arrive pre-labelled with a +1 margin swing that
    # a miss at the same instant does not have. Subtract the row's own points
    # from the shooting side to recover the pre-shot score.
    own = shots["pll_points"].to_numpy(dtype=float)
    home_pre = home_sc - np.where(is_home, own, 0.0)
    away_pre = away_sc - np.where(is_home, 0.0, own)
    shots["score_margin"] = np.where(is_home, home_pre - away_pre, away_pre - home_pre)
    shots["is_two_point"] = (shots["is_two_point_attempt"] == True).astype(float)  # noqa: E712
    shots["y"] = (shots["is_valid_goal"] == True).astype(float)  # noqa: E712
    shots["period_late"] = (shots["period"] >= 4).astype(float)
    shots["game_progress"] = shots["seconds_passed"] / 2880.0
    return shots


def fit_shot_models(ev: pd.DataFrame | None = None, folds: int = CV_FOLDS,
                    seed: int = SEED, data_dir: Path = DATA_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare candidate expected-points-per-shot models by cross-validated
    Brier score. Returns (comparison table, per-class empirical baseline)."""
    if ev is None:
        ev = load_eligible_events(data_dir)
    shots = _shot_feature_frame(ev, data_dir=data_dir)
    y = shots["y"].to_numpy(dtype=float)
    n = len(shots)
    rng = np.random.default_rng(seed)
    fold_id = rng.permutation(n) % folds

    feature_sets = {
        "intercept_only": [],
        "shot_class": ["is_two_point"],
        "shot_class_plus_game_state": ["is_two_point", "score_margin", "period_late",
                                       "game_progress"],
    }

    rows = []
    for name, feats in feature_sets.items():
        X = np.column_stack([np.ones(n)] + [shots[f].to_numpy(dtype=float) for f in feats])
        oof = np.zeros(n)
        for k in range(folds):
            tr, te = fold_id != k, fold_id == k
            beta = _irls_logistic(X[tr], y[tr])
            oof[te] = _predict(X[te], beta)
        beta_full = _irls_logistic(X, y)
        insample = _predict(X, beta_full)
        rows.append({
            "model": name,
            "n_features": len(feats),
            "features": ",".join(feats) if feats else "(intercept only)",
            "n_shots": n,
            "brier_in_sample": _brier(y, insample),
            "brier_cross_validated": _brier(y, oof),
            "log_loss_cross_validated": float(
                -np.mean(y * np.log(np.clip(oof, 1e-12, 1)) +
                         (1 - y) * np.log(np.clip(1 - oof, 1e-12, 1)))),
            "cv_folds": folds,
        })

    # The published baseline: empirical conversion by shot class. Identical in
    # expectation to the `shot_class` logistic model but stated as a rate, which
    # is what the SQL layer applies and what a reader can verify by hand.
    base_rows = []
    for label, mask, mult in [("one_point_attempt", shots["is_two_point"] == 0, 1),
                              ("two_point_attempt", shots["is_two_point"] == 1, 2)]:
        sub = shots[mask]
        k, m = float(sub["y"].sum()), len(sub)
        p = k / m
        se = np.sqrt(p * (1 - p) / m)
        base_rows.append({
            "shot_class": label, "attempts": m, "goals": int(k),
            "p_goal": p, "p_goal_se": se,
            "points_per_goal": mult,
            "expected_points_per_attempt": p * mult,
            "expected_points_per_attempt_se": se * mult,
        })
    baseline = pd.DataFrame(base_rows)

    cv = pd.DataFrame(rows)
    simple = cv.loc[cv["model"] == "shot_class", "brier_cross_validated"].iloc[0]
    rich = cv.loc[cv["model"] == "shot_class_plus_game_state", "brier_cross_validated"].iloc[0]
    cv["brier_improvement_vs_shot_class"] = simple - cv["brier_cross_validated"]
    cv["relative_improvement"] = (simple - cv["brier_cross_validated"]) / simple
    cv.attrs["richer_model_helps"] = bool((simple - rich) / simple > 0.01)
    return cv, baseline


def goalie_shot_baselines(ev: pd.DataFrame | None = None) -> pd.DataFrame:
    """Expected PLL points conceded per shot ON GOAL faced, split one-point vs
    two-point. Separate from the shooter baselines because a goalie's
    opportunity set is shots on goal, not shot attempts -- he is not
    responsible for a shot that missed the cage."""
    if ev is None:
        ev = load_eligible_events()
    sog = ev[ev["event_type"].isin(["shot", "goal"]) & ev["is_shot_on_goal"]]
    rows = []
    for label, mask, mult in [("one_point_shot_on_goal", ~sog["is_two_point"], 1),
                              ("two_point_shot_on_goal", sog["is_two_point"], 2)]:
        sub = sog[mask]
        k, m = float(sub["is_goal"].sum()), len(sub)
        p = k / m
        se = np.sqrt(p * (1 - p) / m)
        rows.append({"shot_class": label, "shots_on_goal_faced": m, "goals": int(k),
                     "p_goal": p, "p_goal_se": se, "points_per_goal": mult,
                     "expected_points_per_shot_on_goal": p * mult,
                     "expected_points_per_shot_on_goal_se": se * mult})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. Empirical-Bayes shrinkage
# ---------------------------------------------------------------------------
def beta_prior_by_moments(successes: np.ndarray, trials: np.ndarray) -> tuple[float, float]:
    """Method-of-moments beta prior for a set of binomial rates.

    Uses only players with at least one trial. The prior mean is the pooled
    rate; the prior's strength is set so that the between-player variance the
    prior implies matches the observed between-player variance net of the
    binomial noise each player's own sample contributes. When the observed
    spread is no wider than binomial noise alone (i.e. the data give no
    evidence of real between-player differences) the excess variance is
    non-positive and a strong prior is returned, which is the correct
    behaviour: shrink everything to the mean.
    """
    keep = trials > 0
    s, t = successes[keep].astype(float), trials[keep].astype(float)
    if len(s) < 2:
        return np.nan, np.nan
    mu = s.sum() / t.sum()
    rates = s / t
    # weight players by trials so a 1-shot player does not dominate the spread
    w = t / t.sum()
    observed_var = float(np.sum(w * (rates - mu) ** 2))
    binomial_var = float(np.sum(w * mu * (1 - mu) / t))
    excess = observed_var - binomial_var
    if excess <= 1e-12:
        kappa = 1e6  # no detectable true spread -> shrink hard to the mean
    else:
        kappa = mu * (1 - mu) / excess - 1.0
        kappa = float(np.clip(kappa, 1e-6, 1e6))
    return mu * kappa, (1 - mu) * kappa


def empirical_bayes_rates(df: pd.DataFrame, success_col: str, trial_col: str,
                          out_prefix: str) -> pd.DataFrame:
    """Add raw and beta-binomial-shrunk rate columns to `df`."""
    a, b = beta_prior_by_moments(df[success_col].to_numpy(), df[trial_col].to_numpy())
    out = df.copy()
    trials = out[trial_col].to_numpy(dtype=float)
    succ = out[success_col].to_numpy(dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        raw = np.where(trials > 0, succ / trials, np.nan)
    out[f"{out_prefix}_raw"] = raw
    out[f"{out_prefix}_shrunk"] = (succ + a) / (trials + a + b)
    out[f"{out_prefix}_prior_alpha"] = a
    out[f"{out_prefix}_prior_beta"] = b
    out[f"{out_prefix}_prior_mean"] = a / (a + b)
    out[f"{out_prefix}_prior_strength_trials"] = a + b
    # a rate with no trials cannot be shrunk toward anything meaningful either
    out.loc[trials == 0, f"{out_prefix}_shrunk"] = np.nan
    return out


def bootstrap_ci(values: np.ndarray, n_boot: int = N_BOOTSTRAP, seed: int = SEED,
                 statistic=np.mean) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(values)
    if n == 0:
        return np.nan, np.nan
    draws = np.array([statistic(rng.choice(values, size=n, replace=True)) for _ in range(n_boot)])
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))
