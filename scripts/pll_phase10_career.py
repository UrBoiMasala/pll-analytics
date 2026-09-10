"""
Phase 10 parts C, D and E: career player identity and career-level ability.

Phase 9 established the finding this module builds on: pooling player-SEASONS
as extra rows makes identification WORSE (shooting kappa 70.8 -> 145.5, zero of
863 player-seasons above reliability 0.5), while pooling a player's CAREER
makes it better (66 of 370 shooters, 8 of 27 goalies). Phase 10 takes that from
a summary table to a published, per-player, independently recomputable layer,
and puts three further questions to it:

  * does the identity layer still hold when a career is the unit of analysis?
  * which rates are estimable at career level, on evidence rather than on the
    fact that a number can be computed?
  * how much of the answer depends on WHICH seasons a player happens to have?

METHOD -- unchanged from Phases 6-9, deliberately
    `beta_prior_by_moments` and `beta_quantile` are IMPORTED from the Phase 6/7
    modules, never reimplemented, so a career prior is directly comparable with
    the per-season priors already published and cannot drift from them. The
    prior strength kappa is the number of trials at which the posterior weights
    a player's own record equally with the league; reliability = n / (n + kappa).

WHAT COUNTS AS ESTIMABLE
    Two conditions, both required, neither chosen for convenience:
      1. the observed between-player variance must exceed the binomial noise
         the players' own sample sizes imply (otherwise kappa is capped at 1e6
         and every shrunk value is the league mean -- an ability estimate that
         contains no information about the player);
      2. at least one real player must reach reliability >= 0.5 (otherwise the
         rate is identified for the LEAGUE but for no INDIVIDUAL).
    Condition 2 is reported as a count and a proportion rather than used as a
    filter, because "how many players can be separated" is the finding.

NO THRESHOLD IS INVENTED
    reliability >= 0.5 is not an arbitrary cut. It is the exact point at which
    the empirical-Bayes posterior stops being mostly prior, i.e. n >= kappa,
    and kappa is estimated from the data. Every table also reports the full
    reliability distribution so a reader can apply a different line.

Outputs, all in data/processed/history/:
    player_career_2022_2026.csv          one row per player: seasons, teams,
                                         positions, opportunities, raw rates,
                                         shrunk rates, reliability, state
    career_ability_reliability.csv       one row per (rate, scope): the
                                         estimator's own diagnostics
    career_rate_estimates.csv            one row per (player, rate): raw,
                                         shrunk, posterior interval
    career_scope_comparison.csv          single season vs pooled seasons vs
                                         career, per rate
    career_season_composition_sensitivity.csv  leave-one-season-out
    career_two_point_identification.csv  section E, re-tested at career level
    career_identity_audit.csv            section C
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"
SEASONS = [2022, 2023, 2024, 2025, 2026]

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pll_player_value_models import beta_prior_by_moments  # noqa: E402
from pll_adjusted_value_models import beta_quantile        # noqa: E402

RELIABILITY_GATE = 0.5

# (rate, successes column, trials column or None for save_pct, description,
#  whether Phase 8/9 already characterised it)
RATE_SPECS = [
    ("shooting_pct", "goals", "shots",
     "goals per shot attempt, all classes", "phase_6_8_9"),
    ("one_point_pct", "one_point_goals", "one_point_attempts",
     "goals per one-point attempt", "phase_6_8_9"),
    ("two_point_pct", "two_point_goals", "two_point_attempts",
     "goals per two-point attempt", "phase_6_8_9"),
    ("faceoff_win_pct", "faceoff_wins", "faceoffs",
     "faceoffs won per faceoff taken", "phase_6_8_9"),
    ("save_pct", "saves", None,
     "saves per shot on goal faced (saves + goals allowed)", "phase_6_8_9"),
    ("turnovers_per_touch", "turnovers", "touches",
     "turnovers per recorded touch", "phase_6_8_9"),
    # Phase 10 additions: existing player-rate quantities that Phase 8's
    # catalog records but whose career identifiability has never been tested.
    # All three are genuine binomials over an opportunity the feed counts.
    ("shots_on_goal_pct", "shots_on_goal", "shots",
     "shots on goal per shot attempt -- accuracy, separated from finishing",
     "phase_10_new"),
    ("goals_per_shot_on_goal", "goals", "shots_on_goal",
     "goals per shot ON GOAL -- finishing conditional on hitting the cage",
     "phase_10_new"),
    ("two_point_attempt_share", "two_point_attempts", "shots",
     "share of a player's attempts taken from two-point range -- shot "
     "SELECTION, which is a choice, not a conversion skill",
     "phase_10_new"),
]


def load_pooled_players() -> pd.DataFrame:
    p = pd.read_csv(HIST / "player_stats_2022_2026.csv", low_memory=False,
                    dtype={"player_id": str, "team_id": str})
    p["player_id"] = p["player_id"].str.zfill(6)
    return p


def trials_for(df: pd.DataFrame, spec):
    """(successes, trials) for one rate spec, as float Series."""
    name, succ, tri = spec[0], spec[1], spec[2]
    s = pd.to_numeric(df[succ], errors="coerce").fillna(0.0)
    if name == "save_pct":
        t = (pd.to_numeric(df["saves"], errors="coerce").fillna(0.0)
             + pd.to_numeric(df["goals_allowed"], errors="coerce").fillna(0.0))
    else:
        t = pd.to_numeric(df[tri], errors="coerce").fillna(0.0)
    # A rate can never have more successes than trials. This is an assertion
    # about the feed, not a clip: if it fires, something upstream is wrong.
    bad = int((s > t + 1e-9).sum())
    if bad:
        raise ValueError(f"{name}: {bad} rows with successes > trials")
    return s, t


# ---------------------------------------------------------------------------
# C. Career identity
# ---------------------------------------------------------------------------
def identity_audit(p: pd.DataFrame) -> pd.DataFrame:
    """Re-audit identity with the CAREER as the unit, before any aggregation.

    Phase 9 audited ids against players.csv. This audit asks the three
    questions that matter once careers are the row: is one human split across
    two careers, are two humans fused into one, and does a team or position
    change silently create or destroy a career?
    """
    rows = []
    for pid, g in p.groupby("player_id"):
        names = sorted(set(g["player_name"].dropna()))
        teams = sorted(set(g["team_id"].dropna()))
        pos = sorted(set(g["canonical_position"].dropna()))
        roles = sorted(set(g["value_role"].dropna()))
        seasons = sorted(g["season"].unique())
        rows.append({
            "player_id": pid,
            "player_name": names[0] if names else None,
            "n_name_spellings": len(names),
            "name_spellings": " | ".join(names),
            "n_seasons": len(seasons),
            "seasons": ",".join(str(s) for s in seasons),
            "first_season": seasons[0], "last_season": seasons[-1],
            "has_season_gap": (seasons[-1] - seasons[0] + 1) != len(seasons),
            "n_teams": len(teams), "teams": ",".join(teams),
            "changed_team": len(teams) > 1,
            "n_positions": len(pos), "positions": ",".join(pos),
            "changed_position": len(pos) > 1,
            "n_value_roles": len(roles), "value_roles": ",".join(roles),
            "changed_value_role": len(roles) > 1,
            "n_player_season_rows": len(g),
            "duplicate_player_season_rows":
                int(g.duplicated(subset=["season"]).sum()),
        })
    a = pd.DataFrame(rows)

    # a normalised name shared by two ids is the signature of a SPLIT career;
    # two ids for one human. It is reported, never auto-merged -- a fuzzy name
    # match is a hypothesis, not a registration.
    norm = (a["player_name"].fillna("").str.lower()
            .str.replace(r"[^a-z ]", "", regex=True)
            .str.replace(r"\b(jr|sr|ii|iii|iv)\b", "", regex=True)
            .str.replace(r"\s+", " ", regex=True).str.strip())
    a["normalized_name"] = norm
    dup = norm[norm != ""].duplicated(keep=False)
    a["shares_normalized_name_with_another_id"] = dup.reindex(a.index).fillna(False)

    a["career_aggregation_state"] = np.where(
        a["duplicate_player_season_rows"] > 0, "BLOCKED_DUPLICATE_SEASON_ROW",
        np.where(a["shares_normalized_name_with_another_id"],
                 "REVIEW_POSSIBLE_SPLIT_CAREER",
                 np.where(a["n_name_spellings"] > 1,
                          "REVIEW_MULTIPLE_NAME_SPELLINGS",
                          np.where(a["changed_value_role"],
                                   "SAFE_WITH_ROLE_CHANGE_CAVEAT", "SAFE"))))
    a["safe_to_aggregate_career"] = a["career_aggregation_state"].str.startswith(
        ("SAFE",))
    return a.sort_values("player_id").reset_index(drop=True)


# ---------------------------------------------------------------------------
# D. Career ability
# ---------------------------------------------------------------------------
def _fit(s: np.ndarray, t: np.ndarray):
    """Prior, reliability and identification diagnostics for one (s, t) set."""
    keep = t > 0
    s, t = s[keep], t[keep]
    if len(s) < 3:
        return None
    a, b = beta_prior_by_moments(s, t)
    kappa = a + b
    mu = a / kappa
    rates = s / t
    w = t / t.sum()
    obs_var = float(np.sum(w * (rates - mu) ** 2))
    bin_var = float(np.sum(w * mu * (1 - mu) / t))
    rel = t / (t + kappa)
    true_var = mu * (1 - mu) / (kappa + 1.0)
    return {
        "alpha": a, "beta": b, "kappa": kappa, "prior_mean": mu,
        "n_units": int(len(s)), "total_trials": float(t.sum()),
        "median_trials": float(np.median(t)), "max_trials": float(t.max()),
        "p25_trials": float(np.percentile(t, 25)),
        "p75_trials": float(np.percentile(t, 75)),
        "observed_between_player_variance": obs_var,
        "binomial_noise_variance": bin_var,
        "excess_variance": obs_var - bin_var,
        "implied_true_sd_between_players": float(np.sqrt(max(true_var, 0.0))),
        "raw_rate_sd": float(np.std(rates, ddof=0)),
        "shrunk_rate_sd": float(np.std((s + a) / (t + kappa), ddof=0)),
        "n_reaching_reliability_gate": int((rel >= RELIABILITY_GATE).sum()),
        "pct_reaching_reliability_gate": 100.0 * float((rel >= RELIABILITY_GATE).mean()),
        "mean_reliability": float(rel.mean()),
        "median_reliability": float(np.median(rel)),
        "max_reliability": float(rel.max()),
        "prior_is_capped": bool(kappa >= 1e5),
        "between_player_spread_exceeds_noise": bool(obs_var > bin_var),
    }


def career_totals(p: pd.DataFrame, spec) -> pd.DataFrame:
    s, t = trials_for(p, spec)
    return (pd.DataFrame({"player_id": p["player_id"], "s": s, "t": t})
            .groupby("player_id", as_index=False).sum())


def ability_tables(p: pd.DataFrame, identity: pd.DataFrame):
    """Returns (reliability_by_scope, per_player_estimates, scope_comparison)."""
    safe = set(identity.loc[identity["safe_to_aggregate_career"], "player_id"])
    rel_rows, est_rows, cmp_rows = [], [], []

    for spec in RATE_SPECS:
        name, provenance = spec[0], spec[4]

        scopes = {}
        for y in SEASONS:
            sub = p[p["season"] == y]
            s, t = trials_for(sub, spec)
            scopes[f"season_{y}"] = (s.to_numpy(float), t.to_numpy(float))
        s_all, t_all = trials_for(p, spec)
        scopes["pooled_player_seasons"] = (s_all.to_numpy(float), t_all.to_numpy(float))
        agg = career_totals(p, spec)
        agg = agg[agg["player_id"].isin(safe)]
        scopes["pooled_player_career"] = (agg["s"].to_numpy(float),
                                          agg["t"].to_numpy(float))

        for scope, (s, t) in scopes.items():
            f = _fit(s, t)
            if f is None:
                continue
            f.update({"rate_name": name, "scope": scope,
                      "rate_description": spec[3], "provenance": provenance,
                      "reliability_gate": RELIABILITY_GATE,
                      "estimable_at_this_scope": bool(
                          f["between_player_spread_exceeds_noise"]
                          and not f["prior_is_capped"]
                          and f["n_reaching_reliability_gate"] > 0),
                      "verdict": _verdict(f)})
            rel_rows.append(f)

        # per-player career estimates, from the career prior
        f = _fit(agg["s"].to_numpy(float), agg["t"].to_numpy(float))
        if f is None:
            continue
        a, b, kappa = f["alpha"], f["beta"], f["kappa"]
        for r in agg.itertuples():
            n, k = float(r.t), float(r.s)
            if n <= 0:
                continue
            post_a, post_b = a + k, b + (n - k)
            # A capped prior makes the posterior numerically degenerate and its
            # quantiles meaningless; report NaN rather than a spurious interval.
            if kappa >= 1e5:
                lo = hi = np.nan
            else:
                lo = beta_quantile(post_a, post_b, 0.025)
                hi = beta_quantile(post_a, post_b, 0.975)
            est_rows.append({
                "player_id": r.player_id, "rate_name": name,
                "career_successes": k, "career_trials": n,
                "career_rate_raw": k / n,
                "career_rate_shrunk": (k + a) / (n + kappa),
                "shrinkage_shift": (k + a) / (n + kappa) - k / n,
                "league_baseline_prior_mean": a / kappa,
                "prior_strength_trials_kappa": kappa,
                "reliability": n / (n + kappa),
                "meets_reliability_gate": (n / (n + kappa)) >= RELIABILITY_GATE,
                "posterior_alpha": post_a, "posterior_beta": post_b,
                "posterior_ci_lo": lo, "posterior_ci_hi": hi,
                "posterior_ci_width": hi - lo if np.isfinite(hi) else np.nan,
                "interval_method": ("exact 95% beta posterior quantiles; NaN "
                                    "where the prior is capped and the "
                                    "posterior carries no player information"),
            })

        # scope comparison, one row per rate
        by = {r["scope"]: r for r in rel_rows if r["rate_name"] == name}
        one = by.get("season_2026") or by.get("season_2025")
        ps, pc = by.get("pooled_player_seasons"), by.get("pooled_player_career")
        if one and ps and pc:
            cmp_rows.append({
                "rate_name": name, "provenance": provenance,
                "single_season_scope": one["scope"],
                "single_season_kappa": one["kappa"],
                "single_season_n_units": one["n_units"],
                "single_season_median_trials": one["median_trials"],
                "single_season_n_gate": one["n_reaching_reliability_gate"],
                "single_season_pct_gate": one["pct_reaching_reliability_gate"],
                "pooled_seasons_kappa": ps["kappa"],
                "pooled_seasons_n_units": ps["n_units"],
                "pooled_seasons_median_trials": ps["median_trials"],
                "pooled_seasons_n_gate": ps["n_reaching_reliability_gate"],
                "pooled_seasons_pct_gate": ps["pct_reaching_reliability_gate"],
                "career_kappa": pc["kappa"],
                "career_n_units": pc["n_units"],
                "career_median_trials": pc["median_trials"],
                "career_n_gate": pc["n_reaching_reliability_gate"],
                "career_pct_gate": pc["pct_reaching_reliability_gate"],
                "career_beats_single_season":
                    pc["pct_reaching_reliability_gate"] > one["pct_reaching_reliability_gate"],
                "pooling_seasons_beats_single_season":
                    ps["pct_reaching_reliability_gate"] > one["pct_reaching_reliability_gate"],
                "why": _why(one, ps, pc),
            })

    return (pd.DataFrame(rel_rows), pd.DataFrame(est_rows), pd.DataFrame(cmp_rows))


def _verdict(f):
    if f["prior_is_capped"]:
        return ("NOT IDENTIFIABLE: observed between-player spread does not "
                "exceed binomial noise; every shrunk value is the league mean")
    if f["n_reaching_reliability_gate"] == 0:
        return ("LEAGUE-IDENTIFIED, PLAYER-UNIDENTIFIED: real between-player "
                "spread exists but no individual has enough trials to be "
                "separated from the prior")
    return (f"IDENTIFIABLE for {f['n_reaching_reliability_gate']} of "
            f"{f['n_units']} units ({f['pct_reaching_reliability_gate']:.1f}%)")


def _why(one, ps, pc):
    return (f"trials per unit is the binding constraint: median "
            f"{one['median_trials']:.0f} for a single season, "
            f"{ps['median_trials']:.0f} pooling seasons as rows (unchanged -- "
            f"more units, not more evidence per unit, and kappa moves "
            f"{one['kappa']:.1f} -> {ps['kappa']:.1f}), "
            f"{pc['median_trials']:.0f} pooling a career "
            f"(kappa {pc['kappa']:.1f})")


# ---------------------------------------------------------------------------
# D (cont). Sensitivity to season composition
# ---------------------------------------------------------------------------
def season_composition_sensitivity(p: pd.DataFrame, identity: pd.DataFrame) -> pd.DataFrame:
    """Leave-one-season-out: how much of a career estimate is an artefact of
    which seasons the player happens to have played?

    Reported two ways, because they answer different questions: how much the
    LEAGUE-level prior moves, and how much individual players' shrunk rates
    and rank order move.
    """
    safe = set(identity.loc[identity["safe_to_aggregate_career"], "player_id"])
    rows = []
    for spec in RATE_SPECS:
        name = spec[0]
        full = career_totals(p, spec)
        full = full[full["player_id"].isin(safe)]
        f_full = _fit(full["s"].to_numpy(float), full["t"].to_numpy(float))
        if f_full is None:
            continue
        a0, k0 = f_full["alpha"], f_full["kappa"]
        base = full[full["t"] > 0].set_index("player_id")
        base_shrunk = (base["s"] + a0) / (base["t"] + k0)
        for drop in SEASONS:
            sub = p[p["season"] != drop]
            agg = career_totals(sub, spec)
            agg = agg[agg["player_id"].isin(safe)]
            f = _fit(agg["s"].to_numpy(float), agg["t"].to_numpy(float))
            if f is None:
                continue
            a, k = f["alpha"], f["kappa"]
            cur = agg[agg["t"] > 0].set_index("player_id")
            cur_shrunk = (cur["s"] + a) / (cur["t"] + k)
            common = base_shrunk.index.intersection(cur_shrunk.index)
            d = (cur_shrunk.reindex(common) - base_shrunk.reindex(common)).abs()
            rho = (np.corrcoef(base_shrunk.reindex(common).rank(),
                               cur_shrunk.reindex(common).rank())[0, 1]
                   if len(common) > 2 else np.nan)
            rows.append({
                "rate_name": name, "season_dropped": drop,
                "kappa_full": k0, "kappa_without_season": k,
                "kappa_pct_change": 100.0 * (k - k0) / k0 if k0 else np.nan,
                "n_players_full": int(len(base_shrunk)),
                "n_players_without_season": int(len(cur_shrunk)),
                "n_players_lost": int(len(base_shrunk) - len(common)),
                "mean_abs_change_in_shrunk_rate": float(d.mean()) if len(d) else np.nan,
                "max_abs_change_in_shrunk_rate": float(d.max()) if len(d) else np.nan,
                "spearman_rank_correlation_vs_full": float(rho),
                "n_gate_full": f_full["n_reaching_reliability_gate"],
                "n_gate_without_season": f["n_reaching_reliability_gate"],
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# E. Two-point, re-tested at career level
# ---------------------------------------------------------------------------
def two_point_identification(p: pd.DataFrame, identity: pd.DataFrame) -> pd.DataFrame:
    """Section E. Phase 9 found individual two-point ability unidentifiable in
    every season and both pooled scopes. This re-tests it on the final career
    aggregation, reports the full attempt distribution, and states the verdict
    either way. Nothing here is allowed to produce a leaderboard."""
    safe = set(identity.loc[identity["safe_to_aggregate_career"], "player_id"])
    spec = ("two_point_pct", "two_point_goals", "two_point_attempts", "", "")
    rows = []
    scopes = {f"season_{y}": p[p["season"] == y] for y in SEASONS}
    scopes["pooled_player_seasons"] = p
    for scope, sub in scopes.items():
        s, t = trials_for(sub, spec)
        rows.append(("two_point_pct", scope,
                     _fit(s.to_numpy(float), t.to_numpy(float))))
    agg = career_totals(p, spec)
    agg = agg[agg["player_id"].isin(safe)]
    rows.append(("two_point_pct", "pooled_player_career",
                 _fit(agg["s"].to_numpy(float), agg["t"].to_numpy(float))))

    # the comparison that makes the verdict interpretable: the same diagnostic
    # for one-point conversion, which IS identifiable, on the same players
    spec1 = ("one_point_pct", "one_point_goals", "one_point_attempts", "", "")
    agg1 = career_totals(p, spec1)
    agg1 = agg1[agg1["player_id"].isin(safe)]
    rows.append(("one_point_pct_reference", "pooled_player_career",
                 _fit(agg1["s"].to_numpy(float), agg1["t"].to_numpy(float))))

    out = []
    for rate, scope, f in rows:
        if f is None:
            continue
        f = dict(f)
        f.update({
            "rate_name": rate, "scope": scope,
            "identifiable": bool(f["between_player_spread_exceeds_noise"]
                                 and not f["prior_is_capped"]),
            "classification": (
                "UNSUPPORTED / DO_NOT_USE"
                if not (f["between_player_spread_exceeds_noise"]
                        and not f["prior_is_capped"]) else "REVISIT"),
            "verdict": _verdict(f),
        })
        out.append(f)
    df = pd.DataFrame(out)
    front = ["rate_name", "scope", "n_units", "total_trials", "median_trials",
             "max_trials", "observed_between_player_variance",
             "binomial_noise_variance", "excess_variance", "kappa",
             "max_reliability", "n_reaching_reliability_gate", "identifiable",
             "classification"]
    return df[front + [c for c in df.columns if c not in front]]


def two_point_attempt_distribution(p: pd.DataFrame, identity: pd.DataFrame) -> pd.DataFrame:
    safe = set(identity.loc[identity["safe_to_aggregate_career"], "player_id"])
    spec = ("two_point_pct", "two_point_goals", "two_point_attempts", "", "")
    agg = career_totals(p, spec)
    agg = agg[agg["player_id"].isin(safe) & (agg["t"] > 0)]
    t = agg["t"].to_numpy(float)
    rows = [{"scope": "pooled_player_career", "n_shooters": len(t),
             "total_attempts": float(t.sum())}]
    for q in (0, 10, 25, 50, 75, 90, 95, 99, 100):
        rows[0][f"attempts_p{q}"] = float(np.percentile(t, q))
    for thr in (5, 10, 20, 30, 50):
        rows[0][f"n_players_with_at_least_{thr}_attempts"] = int((t >= thr).sum())
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# The career table
# ---------------------------------------------------------------------------
def career_table(p: pd.DataFrame, identity: pd.DataFrame,
                 estimates: pd.DataFrame) -> pd.DataFrame:
    """One row per player. Season and career samples both stay recoverable:
    `seasons` and `teams_by_season` name the components, and every count is a
    plain sum of the season rows so the reconciliation is exact."""
    num_cols = ["games_played", "goals", "one_point_goals", "two_point_goals",
                "scoring_points", "official_assists", "shots", "shots_on_goal",
                "one_point_attempts", "two_point_attempts", "turnovers",
                "touches", "caused_turnovers", "ground_balls", "penalties",
                "faceoffs", "faceoff_wins", "faceoff_losses", "saves",
                "goals_allowed", "shots_on_goal_faced", "pll_points_allowed",
                "recorded_offensive_opportunities"]
    agg = p.groupby("player_id")[num_cols].sum()

    def joined(col):
        return p.sort_values("season").groupby("player_id")[col].apply(
            lambda s: ",".join(str(v) for v in s))

    out = agg.reset_index()
    out["player_name"] = p.groupby("player_id")["player_name"].first().values
    out["seasons"] = joined("season").values
    out["n_seasons"] = p.groupby("player_id")["season"].nunique().values
    out["teams_by_season"] = joined("team_id").values
    out["positions_by_season"] = joined("canonical_position").values
    out["value_roles_by_season"] = joined("value_role").values
    out["teams"] = p.groupby("player_id")["team_id"].apply(
        lambda s: ",".join(sorted(set(s.dropna())))).values
    out["career_position_representation"] = p.groupby("player_id").apply(
        lambda g: _position_representation(g), include_groups=False).values
    out["modal_position"] = p.groupby("player_id").apply(
        lambda g: _modal_position(g), include_groups=False).values
    out["career_position_is_single_role"] = out["value_roles_by_season"].map(
        lambda s: len(set(s.split(","))) == 1)

    # raw career rates, recomputable from the columns on the same row
    with np.errstate(invalid="ignore", divide="ignore"):
        out["shooting_pct_raw"] = out["goals"] / out["shots"].replace(0, np.nan)
        out["one_point_pct_raw"] = (out["one_point_goals"]
                                    / out["one_point_attempts"].replace(0, np.nan))
        out["two_point_pct_raw"] = (out["two_point_goals"]
                                    / out["two_point_attempts"].replace(0, np.nan))
        out["faceoff_win_pct_raw"] = out["faceoff_wins"] / out["faceoffs"].replace(0, np.nan)
        out["save_denominator"] = out["saves"] + out["goals_allowed"]
        out["save_pct_raw"] = out["saves"] / out["save_denominator"].replace(0, np.nan)
        out["turnovers_per_touch_raw"] = out["turnovers"] / out["touches"].replace(0, np.nan)
        out["shots_on_goal_pct_raw"] = out["shots_on_goal"] / out["shots"].replace(0, np.nan)

    # shrunk estimates and reliability, joined from the estimate table
    for rate in ["shooting_pct", "one_point_pct", "two_point_pct",
                 "faceoff_win_pct", "save_pct", "turnovers_per_touch"]:
        e = estimates[estimates["rate_name"] == rate].set_index("player_id")
        out[f"{rate}_shrunk"] = out["player_id"].map(e["career_rate_shrunk"])
        out[f"{rate}_reliability"] = out["player_id"].map(e["reliability"])
        out[f"{rate}_ci_lo"] = out["player_id"].map(e["posterior_ci_lo"])
        out[f"{rate}_ci_hi"] = out["player_id"].map(e["posterior_ci_hi"])

    idx = identity.set_index("player_id")
    out["career_aggregation_state"] = out["player_id"].map(idx["career_aggregation_state"])
    out["safe_to_aggregate_career"] = out["player_id"].map(idx["safe_to_aggregate_career"])
    out["changed_team"] = out["player_id"].map(idx["changed_team"])
    out["changed_position"] = out["player_id"].map(idx["changed_position"])
    out["has_season_gap"] = out["player_id"].map(idx["has_season_gap"])

    # qualification: an evidence statement, per rate, never a single verdict
    gates = []
    for _, r in out.iterrows():
        ok = [rate for rate in ["shooting_pct", "one_point_pct", "faceoff_win_pct",
                                "save_pct", "turnovers_per_touch"]
              if pd.notna(r.get(f"{rate}_reliability"))
              and r[f"{rate}_reliability"] >= RELIABILITY_GATE]
        gates.append(",".join(ok) if ok else "none")
    out["rates_reaching_reliability_gate"] = gates
    out["n_rates_reaching_reliability_gate"] = [
        0 if g == "none" else len(g.split(",")) for g in gates]
    out["qualification_state"] = np.where(
        ~out["safe_to_aggregate_career"], "NOT_AGGREGATABLE",
        np.where(out["n_rates_reaching_reliability_gate"] > 0,
                 "ABILITY_ESTIMABLE_FOR_AT_LEAST_ONE_RATE",
                 "DESCRIPTIVE_ONLY"))

    front = ["player_id", "player_name", "n_seasons", "seasons", "teams",
             "teams_by_season", "positions_by_season", "value_roles_by_season",
             "career_position_representation", "modal_position",
             "career_position_is_single_role", "games_played"]
    return out[front + [c for c in out.columns if c not in front]].sort_values(
        "player_id").reset_index(drop=True)


def _position_representation(g: pd.DataFrame) -> str:
    """'attack:3,midfield:2' -- a player who changed roles keeps both, because
    forcing one career position is exactly the error section C forbids."""
    c = g["canonical_position"].value_counts()
    return ",".join(f"{k}:{v}" for k, v in c.items())


def _modal_position(g: pd.DataFrame) -> str:
    """The most-played position, weighted by games. Reported for convenience;
    `career_position_representation` is the authoritative field."""
    w = g.groupby("canonical_position")["games_played"].sum()
    return w.idxmax() if len(w) else None


def main():
    HIST.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 250)
    p = load_pooled_players()

    ident = identity_audit(p)
    ident.to_csv(HIST / "career_identity_audit.csv", index=False)

    rel, est, cmp_ = ability_tables(p, ident)
    rel.to_csv(HIST / "career_ability_reliability.csv", index=False)
    est.to_csv(HIST / "career_rate_estimates.csv", index=False)
    cmp_.to_csv(HIST / "career_scope_comparison.csv", index=False)

    sens = season_composition_sensitivity(p, ident)
    sens.to_csv(HIST / "career_season_composition_sensitivity.csv", index=False)

    tp = two_point_identification(p, ident)
    tp.to_csv(HIST / "career_two_point_identification.csv", index=False)
    tpd = two_point_attempt_distribution(p, ident)
    tpd.to_csv(HIST / "career_two_point_attempt_distribution.csv", index=False)

    career = career_table(p, ident, est)
    career.to_csv(HIST / "player_career_2022_2026.csv", index=False)

    print("=== C. CAREER IDENTITY ===")
    print(f"players {len(ident)} | multi-season {(ident['n_seasons']>1).sum()} | "
          f"changed team {ident['changed_team'].sum()} | "
          f"changed position {ident['changed_position'].sum()} | "
          f"season gap {ident['has_season_gap'].sum()}")
    print(ident["career_aggregation_state"].value_counts().to_string())

    print("\n=== D. CAREER ABILITY, by scope ===")
    show = rel[rel["scope"].isin(["season_2026", "pooled_player_seasons",
                                  "pooled_player_career"])]
    print(show[["rate_name", "scope", "n_units", "total_trials", "median_trials",
                "kappa", "excess_variance", "n_reaching_reliability_gate",
                "pct_reaching_reliability_gate", "estimable_at_this_scope"]]
          .round(4).to_string(index=False))

    print("\n=== D. SCOPE COMPARISON ===")
    print(cmp_[["rate_name", "single_season_pct_gate", "pooled_seasons_pct_gate",
                "career_pct_gate", "career_beats_single_season",
                "pooling_seasons_beats_single_season"]].round(2).to_string(index=False))

    print("\n=== D. SENSITIVITY TO SEASON COMPOSITION (leave-one-season-out) ===")
    print(sens.groupby("rate_name")[["kappa_pct_change",
                                     "mean_abs_change_in_shrunk_rate",
                                     "spearman_rank_correlation_vs_full"]]
          .agg(["min", "max"]).round(4).to_string())

    print("\n=== E. TWO-POINT AT CAREER LEVEL ===")
    print(tp[["rate_name", "scope", "n_units", "total_trials", "median_trials",
              "max_trials", "observed_between_player_variance",
              "binomial_noise_variance", "excess_variance", "kappa",
              "max_reliability", "n_reaching_reliability_gate", "identifiable",
              "classification"]].round(6).to_string(index=False))
    print(tpd.round(2).to_string(index=False))
    return ident, rel, est, cmp_, sens, tp, career


if __name__ == "__main__":
    main()
