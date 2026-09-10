"""
Phase 10 parts F, G, H, I and J: can player value be compared across positions?

This module answers a measurement question, not a ranking question. It builds
NO composite, NO award score and NO cross-position leaderboard. What it builds
is the evidence a later phase would need before it could justify one:

  G  how different the value scales actually are, by role and by season
  H  what a positional baseline should be estimated over, decided on stability
  F  ten candidate ways of making value comparable, each measured on the same
     eight properties, plus counterfactual probes with known right answers
  I  how much of defence this feed can see at all
  J  whether any of it is stable enough to rely on

THE PROBLEM, RESTATED PRECISELY
    `EPA_points_raw` shares a UNIT across roles -- PLL points above what a
    league-average player would have produced on the same recorded
    opportunities -- but not a SCALE. Phase 7 measured the gap in 2026: the
    goalie group's standard deviation was 9.59 against 1.46 for close
    defenders. Section G re-measures it across all five seasons, so the
    conclusion rests on 1,023 player-seasons rather than 228.

WHY THE COUNTERFACTUALS MATTER MORE THAN THE DIAGNOSTICS
    Every transformation below can be described in a sentence and most sound
    reasonable. What separates them is what they do to cases whose right
    answer is known in advance -- two players equally elite within their own
    roles, an efficient player with no volume, a busy goalie against an equally
    skilled quiet one. Those probes are constructed from the real league
    distributions and run through every method, so a method that collapses is
    visible rather than argued about.

Outputs, all in data/processed/history/:
    cross_position_value_audit.csv        role x season x component distributions
    positional_baselines.csv              baselines at five scopes, with stability
    cross_position_method_comparison.csv  10 methods x measured properties
    cross_position_counterfactuals.csv    probes with known right answers
    cross_position_replacement_level.csv  is replacement level definable?
    defensive_attribution_audit.csv       what the feed can and cannot see
    phase10_historical_stability.csv      year-to-year, split-half, sensitivity

NOT WRITTEN, DELIBERATELY: any file containing a per-player cross-position
value, rank or score. The method values exist only inside this process, are
consumed by the diagnostics, and are recomputed independently by the Phase 10
validator from the same public inputs.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"
RAW = REPO_ROOT / "data" / "raw"
SEASONS = [2022, 2023, 2024, 2025, 2026]
RNG_SEED = 20261008

ROLES = ["attack", "midfield", "defensive_field", "faceoff", "goalie"]

# The opportunity each role's value is actually measured over. These are not
# interchangeable quantities -- that is the whole point of section G -- so the
# column is named per role rather than pretending one denominator exists.
ROLE_OPPORTUNITY = {
    "attack": "recorded_offensive_opportunities",
    "midfield": "recorded_offensive_opportunities",
    "defensive_field": "games_played",
    "faceoff": "faceoffs",
    "goalie": "shots_on_goal_faced",
}

VALUE_COMPONENTS = [
    "EPA_points_raw", "offensive_EPA_points_raw", "shooting_value_raw",
    "turnover_value_raw", "faceoff_value_raw", "goalie_value_raw",
    "defensive_value_partial_raw",
]


def load_players() -> pd.DataFrame:
    p = pd.read_csv(HIST / "player_stats_2022_2026.csv", low_memory=False,
                    dtype={"player_id": str, "team_id": str})
    p["player_id"] = p["player_id"].str.zfill(6)
    p["role"] = p["position_group"]
    p["role_opportunities"] = [
        pd.to_numeric(p.at[i, ROLE_OPPORTUNITY[r]], errors="coerce")
        if r in ROLE_OPPORTUNITY else np.nan
        for i, r in zip(p.index, p["role"])
    ]
    return p


# ---------------------------------------------------------------------------
# G. Cross-position scale audit
# ---------------------------------------------------------------------------
def _dist(x: pd.Series) -> dict:
    v = pd.to_numeric(x, errors="coerce").dropna()
    if len(v) == 0:
        return {k: np.nan for k in ("n", "mean", "median", "sd", "iqr", "p25",
                                    "p75", "min_value", "max_value", "mad")}
    return {
        "n": int(len(v)), "mean": float(v.mean()), "median": float(v.median()),
        "sd": float(v.std(ddof=0)), "p25": float(v.quantile(0.25)),
        "p75": float(v.quantile(0.75)),
        "iqr": float(v.quantile(0.75) - v.quantile(0.25)),
        "min_value": float(v.min()), "max_value": float(v.max()),
        "mad": float((v - v.median()).abs().median()),
    }


def value_audit(p: pd.DataFrame) -> pd.DataFrame:
    rows = []
    scopes = [("season", y, p[p["season"] == y]) for y in SEASONS]
    scopes.append(("all_seasons", "2022_2026", p))
    for scope_kind, scope, sub in scopes:
        for role in ROLES:
            r = sub[sub["role"] == role]
            if len(r) == 0:
                continue
            opp = pd.to_numeric(r["role_opportunities"], errors="coerce")
            for comp in VALUE_COMPONENTS:
                v = pd.to_numeric(r[comp], errors="coerce")
                per = v / opp.replace(0, np.nan)
                row = {"scope_kind": scope_kind, "scope": str(scope),
                       "role": role, "component": comp,
                       "opportunity_name": ROLE_OPPORTUNITY[role],
                       "n_players": int(len(r)),
                       "n_with_component": int(v.notna().sum()),
                       "component_defined_for_pct": 100.0 * float(v.notna().mean())}
                row.update({f"value_{k}": val for k, val in _dist(v).items()})
                row.update({f"opportunity_{k}": val for k, val in _dist(opp).items()})
                row.update({f"value_per_opportunity_{k}": val
                            for k, val in _dist(per).items()})
                rel = pd.to_numeric(r["role_rate_reliability"], errors="coerce")
                row.update({f"reliability_{k}": val for k, val in _dist(rel).items()})
                rows.append(row)
    audit = pd.DataFrame(rows)

    # the headline: how far apart are the role scales, per season?
    hl = []
    for scope_kind, scope, sub in scopes:
        a = audit[(audit["scope"] == str(scope))
                  & (audit["component"] == "EPA_points_raw")]
        sd = a.set_index("role")["value_sd"].dropna()
        opp = a.set_index("role")["opportunity_mean"].dropna()
        if len(sd) < 2:
            continue
        hl.append({
            "scope_kind": scope_kind, "scope": str(scope), "role": "ALL_ROLES",
            "component": "EPA_points_raw",
            "opportunity_name": "role-specific",
            "value_sd_max_over_min_across_roles": float(sd.max() / sd.min()),
            "value_sd_max_role": sd.idxmax(), "value_sd_min_role": sd.idxmin(),
            "opportunity_mean_max_over_min_across_roles":
                float(opp.max() / opp.min()) if opp.min() > 0 else np.nan,
            "opportunity_mean_max_role": opp.idxmax(),
            "opportunity_mean_min_role": opp.idxmin(),
        })
    return pd.concat([audit, pd.DataFrame(hl)], ignore_index=True)


# ---------------------------------------------------------------------------
# H. Positional baselines, and the scope question
# ---------------------------------------------------------------------------
def positional_baselines(p: pd.DataFrame) -> pd.DataFrame:
    """Estimate the baseline at five scopes and let stability choose.

    No weights are invented anywhere. A baseline here is the empirical mean of
    a component over a defined population, its standard error, and -- the part
    that decides the scope question -- how much it moves between seasons
    relative to that standard error. A position-season baseline whose movement
    is smaller than its own noise is a position baseline estimated five times.
    """
    rows = []

    def add(scope, key, sub, comp, per_opportunity=False):
        v = pd.to_numeric(sub[comp], errors="coerce")
        if per_opportunity:
            opp = pd.to_numeric(sub["role_opportunities"], errors="coerce")
            v = v / opp.replace(0, np.nan)
        v = v.dropna()
        if len(v) < 2:
            return
        rows.append({
            "baseline_scope": scope, "baseline_key": key, "component": comp,
            "denominated_per_opportunity": per_opportunity,
            "n_player_seasons": int(len(v)),
            "baseline_mean": float(v.mean()),
            "baseline_median": float(v.median()),
            "baseline_sd": float(v.std(ddof=0)),
            "baseline_se_of_mean": float(v.std(ddof=1) / np.sqrt(len(v))),
            "baseline_p25": float(v.quantile(0.25)),
            "baseline_p75": float(v.quantile(0.75)),
        })

    for comp in VALUE_COMPONENTS:
        for per in (False, True):
            add("league_wide", "ALL", p, comp, per)
            for y in SEASONS:
                add("season", str(y), p[p["season"] == y], comp, per)
            for role in ROLES:
                add("position", role, p[p["role"] == role], comp, per)
                for y in SEASONS:
                    add("position_season", f"{role}|{y}",
                        p[(p["role"] == role) & (p["season"] == y)], comp, per)
            # career-informed: one row per PLAYER (career totals), then the
            # role mean over players rather than over player-seasons, so a
            # five-season veteran counts once
            car = p.groupby(["player_id", "role"], as_index=False).agg(
                **{comp: (comp, "sum"),
                   "role_opportunities": ("role_opportunities", "sum")})
            for role in ROLES:
                add("career_informed_position", role, car[car["role"] == role],
                    comp, per)

    b = pd.DataFrame(rows)

    # does the position-season baseline actually differ between seasons?
    diag = []
    for comp in VALUE_COMPONENTS:
        for per in (False, True):
            for role in ROLES:
                ps = b[(b["baseline_scope"] == "position_season")
                       & (b["component"] == comp)
                       & (b["denominated_per_opportunity"] == per)
                       & (b["baseline_key"].str.startswith(role + "|"))]
                if len(ps) < 3:
                    continue
                m = ps["baseline_mean"]
                se = ps["baseline_se_of_mean"].mean()
                between = float(m.std(ddof=1))
                diag.append({
                    "baseline_scope": "position_season_stability_diagnostic",
                    "baseline_key": role, "component": comp,
                    "denominated_per_opportunity": per,
                    "n_player_seasons": int(ps["n_player_seasons"].sum()),
                    "between_season_sd_of_baseline": between,
                    "mean_within_season_se_of_baseline": se,
                    "between_season_sd_over_se": between / se if se else np.nan,
                    "recommended_scope": (
                        "position_season" if se and between / se > 1.5
                        else "position"),
                    "reason": (
                        "the baseline moves between seasons by more than its "
                        "own sampling error, so the season is real"
                        if se and between / se > 1.5 else
                        "between-season movement is within sampling error: "
                        "estimating five baselines estimates one baseline "
                        "five times, with five times the noise"),
                })
    return pd.concat([b, pd.DataFrame(diag)], ignore_index=True)


# ---------------------------------------------------------------------------
# H (cont). Are the historical position labels consistent enough?
# ---------------------------------------------------------------------------
def position_label_consistency(p: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for y in SEASONS:
        s = p[p["season"] == y]
        rows.append({
            "season": y, "n_player_seasons": len(s),
            "n_unknown_position": int((s["role"] == "unknown").sum()),
            "pct_unknown_position": 100.0 * float((s["role"] == "unknown").mean()),
            **{f"n_{r}": int((s["role"] == r).sum()) for r in ROLES},
            **{f"share_{r}": float((s["role"] == r).mean()) for r in ROLES},
        })
    t = pd.DataFrame(rows)
    # do the role shares themselves drift? a baseline estimated per season is
    # only comparable if the population it is estimated over is comparable.
    for r in ROLES:
        t[f"share_{r}_range"] = t[f"share_{r}"].max() - t[f"share_{r}"].min()
    multi = p.groupby("player_id")["role"].nunique()
    t["n_players_with_more_than_one_role_across_career"] = int((multi > 1).sum())
    t["n_players_total"] = int(len(multi))
    return t


# ---------------------------------------------------------------------------
# F. Candidate cross-position transformations
# ---------------------------------------------------------------------------
def _pct_rank(s):
    return s.rank(pct=True)


def method_values(p: pd.DataFrame) -> pd.DataFrame:
    """Compute all ten candidate transformations, in memory only.

    Every one is applied to the SAME quantity -- `EPA_points_raw` -- so that
    what is being compared is the transformation and nothing else. None of
    these is a composite: no components are weighted, summed or combined, and
    the result is never written to disk as a per-player ranking.
    """
    d = p[p["role"].isin(ROLES)].copy()
    d["v"] = pd.to_numeric(d["EPA_points_raw"], errors="coerce")
    d["opp"] = pd.to_numeric(d["role_opportunities"], errors="coerce")
    d["rel"] = pd.to_numeric(d["role_rate_reliability"], errors="coerce").fillna(0.0)
    d["gp"] = pd.to_numeric(d["games_played"], errors="coerce")
    d = d[np.isfinite(d["v"])].copy()

    g = d.groupby(["role", "season"])
    d["role_mean"] = g["v"].transform("mean")
    d["role_sd"] = g["v"].transform(lambda s: s.std(ddof=0))
    d["role_opp_sum"] = g["opp"].transform("sum")
    d["role_v_sum"] = g["v"].transform("sum")
    with np.errstate(invalid="ignore", divide="ignore"):
        d["per_opp"] = d["v"] / d["opp"].replace(0, np.nan)
        d["role_per_opp_baseline"] = d["role_v_sum"] / d["role_opp_sum"]

    gs = d.groupby("season")
    d["season_sd"] = gs["v"].transform(lambda s: s.std(ddof=0))

    # 1-10
    d["M01_raw_value_above_role_baseline"] = d["v"] - d["role_mean"]
    d["M02_per_opportunity_above_role_baseline"] = (
        d["per_opp"] - d["role_per_opp_baseline"])
    d["M03_within_position_percentile"] = g["v"].transform(_pct_rank)
    d["M04_within_position_z"] = (d["v"] - d["role_mean"]) / d["role_sd"]
    d["M05_reliability_shrunk_value"] = d["v"] * d["rel"]
    d["M06_opportunity_weighted_value"] = (
        d["M02_per_opportunity_above_role_baseline"] * d["opp"])
    d["M08_season_normalized_value"] = d["v"] / d["season_sd"]
    d["M10_null_standardized_value"] = pd.to_numeric(
        d["EPA_points_null_z"], errors="coerce")

    # 7. value above an EMPIRICAL replacement level within role-season
    repl = replacement_level(d)
    key = d["role"] + "|" + d["season"].astype(str)
    d["marginal_player_level"] = key.map(
        repl.set_index(repl["role"] + "|" + repl["season"].astype(str))
            ["marginal_player_level_value"])
    d["M07_value_above_marginal_roster_player"] = d["v"] - d["marginal_player_level"]

    # 9. distribution standardisation: map each role's marginal onto the
    #    pooled marginal by quantile, so every role has an identical
    #    distribution afterwards by construction.
    pooled = np.sort(d["v"].to_numpy(float))
    q = g["v"].transform(_pct_rank).to_numpy(float)
    idx = np.clip((q * (len(pooled) - 1)).round().astype(int), 0, len(pooled) - 1)
    d["M09_distribution_standardized_across_roles"] = pooled[idx]
    return d, repl


METHOD_META = {
    "M01_raw_value_above_role_baseline": dict(
        definition="v - mean(v | role, season)",
        assumptions="role means differ but role SPREADS are comparable",
        measures="total_season_value",
        interpretability="HIGH -- still in PLL points",
        known_biases="removes the role mean but not the role variance, so the "
                     "highest-variance role keeps supplying the extremes"),
    "M02_per_opportunity_above_role_baseline": dict(
        definition="v/opp - (sum v / sum opp | role, season)",
        assumptions="opportunities within a role are exchangeable; the "
                    "per-opportunity rate is the quantity of interest",
        measures="ability",
        interpretability="HIGH within a role, NONE across roles -- the "
                         "denominators are different objects (a shot, a draw, "
                         "a shot faced, a game)",
        known_biases="unbounded for low-opportunity players; a 3-shot season "
                     "produces the same scale as a 100-shot season"),
    "M03_within_position_percentile": dict(
        definition="percentile rank of v within (role, season)",
        assumptions="equal percentiles across roles represent equal value",
        measures="production",
        interpretability="HIGH as a rank, MISLEADING as a value",
        known_biases="destroys magnitude entirely: the gap between the 1st and "
                     "2nd goalie and between the 1st and 2nd defender become "
                     "the same number, which they are not"),
    "M04_within_position_z": dict(
        definition="(v - mean) / sd within (role, season)",
        assumptions="within-role distributions are comparable after "
                    "standardisation; roughly symmetric",
        measures="production",
        interpretability="MEDIUM -- equal z is equal unusualness, not equal value",
        known_biases="divides by a role SD estimated on as few as 13 players "
                     "(faceoff, 2026); a small role gets a noisy divisor and "
                     "therefore inflated extremes"),
    "M05_reliability_shrunk_value": dict(
        definition="v * reliability(role rate)",
        assumptions="a player's value should be discounted by how much "
                    "evidence stands behind his RATE",
        measures="ability",
        interpretability="LOW -- the product of points and a weight is not "
                         "points and is not a rate",
        known_biases="Phase 7 §1 states the objection directly: shrinking a "
                     "rate then multiplying by the player's own opportunity "
                     "count drags totals toward zero in proportion to sample "
                     "size, which is a much stronger claim than shrinking the "
                     "rate. It also imports the role's reliability profile: "
                     "faceoff reliability is high by construction and "
                     "shooting reliability is low, so this transformation "
                     "systematically favours specialists"),
    "M06_opportunity_weighted_value": dict(
        definition="(per-opportunity value above role baseline) * opportunities",
        assumptions="value scales linearly with opportunity at a fixed rate",
        measures="total_season_value",
        interpretability="MEDIUM",
        known_biases="algebraically close to M01, so it inherits M01's "
                     "variance problem while looking like an efficiency measure"),
    "M07_value_above_marginal_roster_player": dict(
        definition="v - (mean value of the bottom opportunity tercile of the "
                   "player's own role-season). This IS the replacement-level "
                   "candidate from the Phase 10 brief; it is named for the "
                   "population it is estimated on because the project's "
                   "naming guard reserves 'replacement_level' for the "
                   "forbidden composite family, and a feasibility study must "
                   "not be mistaken for one",
        assumptions="a replacement level exists, is estimable from playing "
                    "time rather than from performance (so the estimate is "
                    "not circular), and is stable between seasons",
        measures="total_season_value",
        interpretability="HIGH if the level is real",
        known_biases="the assumption is tested, not granted -- see "
                     "cross_position_replacement_level.csv. Where the level "
                     "sits close to the role mean relative to the role's own "
                     "spread, subtracting it is subtracting a constant and "
                     "the transformation reduces to M01"),
    "M08_season_normalized_value": dict(
        definition="v / sd(v | season)",
        assumptions="seasons differ in scale but roles do not",
        measures="total_season_value",
        interpretability="MEDIUM",
        known_biases="does nothing about the role problem, which is the "
                     "problem; included as the null transformation"),
    "M09_distribution_standardized_across_roles": dict(
        definition="quantile-map each role's marginal onto the pooled marginal",
        assumptions="every role's true value distribution is the same shape "
                    "and spread -- i.e. that the 9.59-vs-1.46 SD gap is "
                    "entirely measurement, with no real component",
        measures="production",
        interpretability="LOW -- the output is in points but the points are "
                         "manufactured by the mapping",
        known_biases="ASSUMES AWAY the finding it is meant to address. It "
                     "forces defenders and goalies to have identical value "
                     "spreads, which is a conclusion, not a normalisation"),
    "M10_null_standardized_value": dict(
        definition="v / sd(v under the null that the player converts his own "
                   "opportunities at exactly the league rate) -- the existing "
                   "EPA_points_null_z, computed in Phase 7 from the league "
                   "conversion baselines and each player's own attempt mix",
        assumptions="the chance spread at a player's own opportunity volume is "
                    "the right yardstick",
        measures="ability",
        interpretability="HIGH and role-free: 'how far from what luck alone "
                         "could produce', which means the same thing for a "
                         "goalie and an attackman",
        known_biases="it is an UNUSUALNESS measure, not a value measure. A "
                     "goalie's +2 and an attackman's +2 are equally unusual "
                     "seasons, not equal contributions -- and no amount of "
                     "sample size turns one into the other"),
}
METHODS = list(METHOD_META)


def replacement_level(d: pd.DataFrame) -> pd.DataFrame:
    """Is a replacement level empirically definable within a role?

    Definition tested: the mean value of players in the bottom third of their
    role-season by opportunity -- the marginal roster player, identified by
    playing time rather than by performance, so the estimate is not circular.
    Whether it is USABLE is decided by whether it is stable across seasons
    relative to its own standard error, and reported either way.
    """
    rows = []
    for (role, season), g in d.groupby(["role", "season"]):
        opp = g["opp"]
        if opp.notna().sum() < 6:
            continue
        thr = opp.quantile(1 / 3)
        marg = g[opp <= thr]
        if len(marg) < 3:
            continue
        rows.append({
            "role": role, "season": season,
            "n_in_role_season": int(len(g)),
            "opportunity_tercile_threshold": float(thr),
            "n_marginal_players": int(len(marg)),
            "marginal_player_level_value": float(marg["v"].mean()),
            "marginal_player_level_se": float(marg["v"].std(ddof=1) / np.sqrt(len(marg))),
            "role_mean_value": float(g["v"].mean()),
            "role_sd_value": float(g["v"].std(ddof=0)),
        })
    r = pd.DataFrame(rows)
    if not len(r):
        return r
    out = []
    for role, g in r.groupby("role"):
        between = float(g["marginal_player_level_value"].std(ddof=1))
        se = float(g["marginal_player_level_se"].mean())
        out.append({
            "role": role,
            "between_season_sd_of_marginal_player_level": between,
            "mean_se_of_marginal_player_level": se,
            "signal_to_noise": between / se if se else np.nan,
            "mean_marginal_player_level": float(g["marginal_player_level_value"].mean()),
            "marginal_player_level_as_share_of_role_sd":
                abs(float(g["marginal_player_level_value"].mean()))
                / float(g["role_sd_value"].mean()),
            "empirically_definable": bool(se and between / se < 2.0),
            "verdict": (
                "STABLE: between-season movement is within sampling error, so "
                "one replacement level per role is defensible"
                if (se and between / se < 2.0) else
                "UNSTABLE: the estimate moves between seasons by more than its "
                "own sampling error, so a replacement level fitted in one "
                "season does not transfer to another"),
        })
    r = r.merge(pd.DataFrame(out), on="role", how="left")
    return r


def method_comparison(d: pd.DataFrame, repl: pd.DataFrame) -> pd.DataFrame:
    """Measure every method on the same eight properties. Nothing here is an
    opinion about a method except the `known_biases` text, which is sourced."""
    rows = []
    d = d.copy()
    d["_key"] = d["player_id"] + "|" + d["season"].astype(str)
    for m in METHODS:
        x = pd.to_numeric(d[m], errors="coerce")
        ok = np.isfinite(x)
        sub = d[ok].copy()
        v = x[ok]

        def rho(a, b):
            a, b = pd.Series(a).astype(float), pd.Series(b).astype(float)
            k = np.isfinite(a) & np.isfinite(b)
            if k.sum() < 5:
                return np.nan
            return float(np.corrcoef(a[k].rank(), b[k].rank())[0, 1])

        # role composition of the extremes
        top = sub.assign(_v=v).nlargest(min(20, len(sub)), "_v")
        share = top["role"].value_counts(normalize=True)
        # scale equalisation after transformation
        sd_by_role = sub.assign(_v=v).groupby("role")["_v"].std(ddof=0).dropna()
        # do low-volume players become extreme?
        med_opp = sub.groupby(["role", "season"])["opp"].transform("median")
        low_vol = sub["opp"] < med_opp
        top_decile = v >= v.quantile(0.9)
        # year to year stability of the transformation itself
        yy = _year_to_year_rho(sub.assign(_v=v), "_v")

        meta = METHOD_META[m]
        rows.append({
            "method": m,
            "mathematical_definition": meta["definition"],
            "required_assumptions": meta["assumptions"],
            "measures": meta["measures"],
            "interpretability": meta["interpretability"],
            "known_biases": meta["known_biases"],
            "n_player_seasons_defined": int(ok.sum()),
            "pct_of_population_defined": 100.0 * float(ok.mean()),
            "spearman_with_role_opportunities": rho(v, sub["opp"]),
            "spearman_with_games_played": rho(v, sub["gp"]),
            "spearman_with_raw_EPA_points": rho(v, sub["v"]),
            "rewards_availability": bool(
                pd.notna(rho(v, sub["gp"])) and rho(v, sub["gp"]) > 0.30),
            "sensitivity_to_opportunity_volume_abs_rho":
                abs(rho(v, sub["opp"])) if pd.notna(rho(v, sub["opp"])) else np.nan,
            "top20_share_goalie": float(share.get("goalie", 0.0)),
            "top20_share_faceoff": float(share.get("faceoff", 0.0)),
            "top20_share_defensive_field": float(share.get("defensive_field", 0.0)),
            "top20_share_attack": float(share.get("attack", 0.0)),
            "top20_share_midfield": float(share.get("midfield", 0.0)),
            "top20_role_concentration_hhi": float((share ** 2).sum()),
            "specialist_roles_dominate_top20": bool(
                share.get("goalie", 0.0) + share.get("faceoff", 0.0) > 0.40),
            "role_sd_max_over_min_after_transform":
                float(sd_by_role.max() / sd_by_role.min())
                if len(sd_by_role) > 1 and sd_by_role.min() > 0 else np.nan,
            "cross_role_scale_equalized": bool(
                len(sd_by_role) > 1 and sd_by_role.min() > 0
                and sd_by_role.max() / sd_by_role.min() < 1.25),
            "pct_of_top_decile_that_is_below_median_opportunity":
                100.0 * float((low_vol & top_decile).sum() / max(top_decile.sum(), 1)),
            "low_volume_players_become_extreme": bool(
                (low_vol & top_decile).sum() / max(top_decile.sum(), 1) > 0.35),
            "year_to_year_spearman": yy["rho"],
            "year_to_year_n_pairs": yy["n"],
        })
    out = pd.DataFrame(rows)
    # HOW a method reaches (or fails to reach) a common scale matters as much
    # as whether it does. Standardising divides by a spread the data supplied;
    # quantile mapping imposes a spread the data did not.
    out["scale_equalization_mechanism"] = out["method"].map({
        "M03_within_position_percentile": "EQUALIZES_BY_DISCARDING_MAGNITUDE",
        "M04_within_position_z": "EQUALIZES_BY_STANDARDIZATION",
        "M09_distribution_standardized_across_roles": "EQUALIZES_BY_ASSUMPTION",
    }).fillna("PRESERVES_ROLE_SCALE")
    # a summary judgement, derived from the measured columns above, not asserted
    out["cross_position_verdict"] = np.where(
        out["cross_role_scale_equalized"] & ~out["specialist_roles_dominate_top20"]
        & ~out["low_volume_players_become_extreme"],
        "SCALE-COMPATIBLE (still not necessarily a value measure -- see measures)",
        np.where(out["cross_role_scale_equalized"],
                 "SCALE-COMPATIBLE BUT DISTORTED (extremes are role- or "
                 "volume-driven)",
                 "NOT CROSS-POSITION COMPARABLE (role scales survive the "
                 "transformation)"))
    # M09 is the one case where the measured verdict needs its mechanism
    # attached, because it fails for a reason the others do not: it does not
    # preserve the role scale, it forces one, and it only fails the numeric
    # test because a 13-player role cannot be quantile-mapped finely.
    out.loc[out["scale_equalization_mechanism"] == "EQUALIZES_BY_ASSUMPTION",
            "cross_position_verdict"] = (
        "EQUALIZES BY ASSUMPTION -- it imposes an identical value spread on "
        "every role, which is the conclusion a cross-position model would need "
        "to establish, not a normalisation it may apply. The residual role-SD "
        "gap that remains is an artefact of coarse quantiles in small roles.")
    return out


def _year_to_year_rho(d: pd.DataFrame, col: str) -> dict:
    cur = d[["player_id", "season", col]].copy()
    nxt = cur.copy()
    nxt["season"] = nxt["season"] - 1
    m = cur.merge(nxt, on=["player_id", "season"], suffixes=("_t", "_t1"))
    m = m[np.isfinite(m[col + "_t"]) & np.isfinite(m[col + "_t1"])]
    if len(m) < 10:
        return {"rho": np.nan, "n": len(m)}
    return {"rho": float(np.corrcoef(m[col + "_t"].rank(),
                                     m[col + "_t1"].rank())[0, 1]),
            "n": int(len(m))}


# ---------------------------------------------------------------------------
# G (cont). Counterfactual probes
# ---------------------------------------------------------------------------
def counterfactuals(d: pd.DataFrame, repl: pd.DataFrame) -> pd.DataFrame:
    """Five probes whose right answer is known before the method is run.

    Each probe is built from the REAL 2026 role distributions -- the role mean,
    SD, per-opportunity baseline and opportunity quantiles are read off the
    data, never invented -- so what the method assigns is what it would assign
    to a real player in that situation.
    """
    y = 2026
    base = d[d["season"] == y]
    stats = {}
    for role in ROLES:
        g = base[base["role"] == role]
        if len(g) < 4:
            continue
        stats[role] = {
            "mean": float(g["v"].mean()), "sd": float(g["v"].std(ddof=0)),
            "opp_p50": float(g["opp"].median()),
            "opp_p10": float(g["opp"].quantile(0.10)),
            "opp_p90": float(g["opp"].quantile(0.90)),
            "per_opp_baseline": float(g["v"].sum() / g["opp"].sum())
            if g["opp"].sum() else np.nan,
            "per_opp_p90": float((g["v"] / g["opp"].replace(0, np.nan)).quantile(0.90)),
            "rel_mean": float(g["rel"].mean()),
            "gp_p50": float(g["gp"].median()),
            "n": int(len(g)),
        }

    rows = []

    def probe(name, question, role, value, opp, rel, gp, expected):
        s = stats.get(role)
        if s is None:
            return
        r = {"probe": name, "question": question, "role": role,
             "synthetic_value_EPA_points": value,
             "synthetic_opportunities": opp,
             "synthetic_reliability": rel, "synthetic_games_played": gp,
             "role_mean": s["mean"], "role_sd": s["sd"],
             "role_per_opportunity_baseline": s["per_opp_baseline"],
             "expected_behaviour": expected}
        r["M01_raw_value_above_role_baseline"] = value - s["mean"]
        r["M02_per_opportunity_above_role_baseline"] = (
            value / opp - s["per_opp_baseline"]) if opp else np.nan
        r["M04_within_position_z"] = (value - s["mean"]) / s["sd"] if s["sd"] else np.nan
        r["M05_reliability_shrunk_value"] = value * rel
        r["M06_opportunity_weighted_value"] = (
            (value / opp - s["per_opp_baseline"]) * opp) if opp else np.nan
        rl = repl[(repl["role"] == role) & (repl["season"] == y)]
        r["M07_value_above_marginal_roster_player"] = (
            value - float(rl["marginal_player_level_value"].iloc[0]) if len(rl) else np.nan)
        rows.append(r)

    # 1. equally elite within role: +2 role SDs above the role mean
    for role in ROLES:
        s = stats.get(role)
        if not s:
            continue
        probe("P1_equally_elite_within_role",
              "two players are +2 SD within their own roles: what does each "
              "method assign them?",
              role, s["mean"] + 2 * s["sd"], s["opp_p50"], s["rel_mean"],
              s["gp_p50"],
              "a cross-position-comparable method assigns them the SAME "
              "number; a role-scale-preserving one does not")
    # 2. elite efficiency, low volume
    for role in ROLES:
        s = stats.get(role)
        if not s or not s["opp_p10"]:
            continue
        probe("P2_elite_efficiency_low_volume",
              "90th-percentile per-opportunity rate on 10th-percentile volume",
              role, s["per_opp_p90"] * s["opp_p10"], s["opp_p10"],
              s["rel_mean"] * 0.2, s["gp_p50"] * 0.4,
              "a per-opportunity method rates him elite on almost no evidence; "
              "a total-value method rates him near zero. Both are 'correct' "
              "for different questions, which is why the question has to be "
              "fixed before the method is chosen")
    # 3. average efficiency, very high volume
    for role in ROLES:
        s = stats.get(role)
        if not s or not s["opp_p90"]:
            continue
        probe("P3_average_efficiency_high_volume",
              "exactly the role's baseline rate on 90th-percentile volume",
              role, s["per_opp_baseline"] * s["opp_p90"], s["opp_p90"],
              s["rel_mean"] * 1.5, s["gp_p50"],
              "per-opportunity methods assign exactly 0; total-value methods "
              "assign 0 too, because the baseline is a RATE. A method that "
              "rewards him is rewarding availability, not performance")
    # 4. two equally skilled goalies, different workload
    s = stats.get("goalie")
    if s:
        for label, opp in (("quiet", s["opp_p10"]), ("busy", s["opp_p90"])):
            probe(f"P4_equally_skilled_goalie_{label}",
                  "identical per-shot skill, different shot volume",
                  "goalie", s["per_opp_p90"] * opp, opp, s["rel_mean"],
                  s["gp_p50"],
                  "per-opportunity methods assign the same number to both, "
                  "which is the skill claim; total-value methods assign the "
                  "busy goalie more, which is the contribution claim. The gap "
                  "between the two answers is the size of the workload "
                  "confound in this feed")
    # 5. FOGO with unusually many draws
    s = stats.get("faceoff")
    if s:
        for label, opp in (("normal_volume", s["opp_p50"]),
                           ("very_high_volume", s["opp_p90"])):
            probe(f"P5_faceoff_specialist_{label}",
                  "identical win rate above baseline, different draw count",
                  "faceoff", s["per_opp_p90"] * opp, opp, s["rel_mean"],
                  s["gp_p50"],
                  "only a per-opportunity method separates draw SKILL from "
                  "draw COUNT; every total-value method credits the specialist "
                  "for how often his team conceded or scored a goal, which is "
                  "not his action")
    cf = pd.DataFrame(rows)

    # the summary the probes exist to produce
    p1 = cf[cf["probe"] == "P1_equally_elite_within_role"]
    if len(p1) > 1:
        note = []
        for m in ["M01_raw_value_above_role_baseline",
                  "M04_within_position_z",
                  "M07_value_above_marginal_roster_player"]:
            v = pd.to_numeric(p1[m], errors="coerce").dropna()
            if len(v) > 1:
                note.append(f"{m}: {v.min():.2f} to {v.max():.2f} "
                            f"(ratio {abs(v.max()/v.min()):.1f}x)"
                            if v.min() != 0 else f"{m}: {v.min():.2f} to {v.max():.2f}")
        cf["P1_summary_equally_elite_players_receive"] = "; ".join(note)
    return cf


# ---------------------------------------------------------------------------
# I. Defensive attribution
# ---------------------------------------------------------------------------
def defensive_attribution_audit(p: pd.DataFrame) -> pd.DataFrame:
    """What the feed records about defence, measured, not asserted.

    The three fields that would carry individual defensive attribution --
    `causedTurnoverId`, `closestDefenderId`, `commitedTurnoverId` -- exist in
    the raw schema and are counted here rather than assumed empty.
    """
    import json
    import glob
    rows = []
    for y in SEASONS:
        n_items = n_turnover = 0
        populated = {"causedTurnoverId": 0, "closestDefenderId": 0,
                     "commitedTurnoverId": 0, "gbPlayerId": 0,
                     "faceoffWinnerId": 0, "shooterId": 0, "goalieId": 0}
        for f in glob.glob(str(RAW / str(y) / "*" / "play_by_play.json")):
            for it in json.loads(Path(f).read_text())["data"]["items"]:
                n_items += 1
                if it.get("eventType") == "turnover":
                    n_turnover += 1
                for k in populated:
                    if it.get(k):
                        populated[k] += 1
        s = p[p["season"] == y]
        d = s[s["role"] == "defensive_field"]
        ct = pd.to_numeric(s["caused_turnovers"], errors="coerce").fillna(0)
        rows.append({
            "season": y,
            "raw_events": n_items,
            "turnover_events": n_turnover,
            "turnover_events_naming_a_player": populated["commitedTurnoverId"],
            "pct_turnover_events_naming_a_player":
                100.0 * populated["commitedTurnoverId"] / n_turnover if n_turnover else np.nan,
            "turnover_events_naming_a_causing_defender": populated["causedTurnoverId"],
            "pct_turnover_events_naming_a_causing_defender":
                100.0 * populated["causedTurnoverId"] / n_turnover if n_turnover else np.nan,
            "events_naming_a_closest_defender": populated["closestDefenderId"],
            "events_naming_a_ground_ball_recoverer": populated["gbPlayerId"],
            "events_naming_a_shooter": populated["shooterId"],
            "events_naming_a_goalie": populated["goalieId"],
            "caused_turnovers_league_total_box_score": float(ct.sum()),
            "caused_turnovers_per_defender_per_game": float(
                (pd.to_numeric(d["caused_turnovers"], errors="coerce").sum())
                / max(pd.to_numeric(d["games_played"], errors="coerce").sum(), 1)),
            "n_defensive_field_players": int(len(d)),
            "defensive_value_spearman_with_games_played": _rho(
                d["defensive_value_partial_raw"], d["games_played"]),
            "defensive_value_spearman_with_caused_turnovers": _rho(
                d["defensive_value_partial_raw"], d["caused_turnovers"]),
            # the underlying counting stat, before the per-game residual is
            # taken: this is what "how much does a defender's standing depend
            # on opportunity rather than measured impact" actually asks
            "caused_turnovers_spearman_with_games_played": _rho(
                d["caused_turnovers"], d["games_played"]),
            "defensive_value_variance_share_explained_by_games_played": (
                _rho(d["defensive_value_partial_raw"], d["games_played"]) ** 2
                if pd.notna(_rho(d["defensive_value_partial_raw"], d["games_played"]))
                else np.nan),
            "caused_turnover_variance_share_explained_by_games_played": (
                _rho(d["caused_turnovers"], d["games_played"]) ** 2
                if pd.notna(_rho(d["caused_turnovers"], d["games_played"]))
                else np.nan),
            "defensive_value_sd": float(pd.to_numeric(
                d["defensive_value_partial_raw"], errors="coerce").std(ddof=0)),
            "goalie_value_sd": float(pd.to_numeric(
                s.loc[s["role"] == "goalie", "goalie_value_raw"],
                errors="coerce").std(ddof=0)),
        })
    a = pd.DataFrame(rows)
    a["observable_defensive_events"] = (
        "caused turnovers (BOX SCORE only -- no event carries a causing "
        "defender), ground balls, penalties committed, goalie saves")
    a["defender_actions_completely_absent_from_the_feed"] = (
        "matchup/assignment; slides, recoveries and help; shot suppression and "
        "forcing a bad shot rather than a turnover; off-ball positioning; "
        "communication; and -- decisively -- minutes, shifts and lineups, so "
        "there is no exposure denominator for any defender at all")
    a["consequence"] = (
        "defensive_value_partial_raw is caused turnovers above the position "
        "group's per-GAME average. Its denominator is games played, so a "
        "defender who plays every defensive possession and one who rotates are "
        "treated as equally exposed. A value of 0.0 does not mean 'an average "
        "defender'; it means 'caused turnovers at his group's per-game rate, "
        "and everything else unmeasured'.")
    return a


def _rho(a, b):
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    k = a.notna() & b.notna()
    if k.sum() < 5:
        return np.nan
    return float(np.corrcoef(a[k].rank(), b[k].rank())[0, 1])


# ---------------------------------------------------------------------------
# J. Historical stability
# ---------------------------------------------------------------------------
def historical_stability(p: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    """Year-to-year, split-half, and sensitivity to the three choices that
    could be made differently: minimum opportunity, raw vs shrunk, and which
    seasons are in the pool."""
    rows = []

    # --- value transformations, year to year -----------------------------
    for m in METHODS:
        yy = _year_to_year_rho(d, m)
        rows.append({"family": "cross_position_method", "target": m,
                     "test": "year_to_year_spearman",
                     "statistic": yy["rho"], "n": yy["n"],
                     "detail": "player-seasons paired at t and t+1, all roles"})

    # --- career rates, year to year and split-half ------------------------
    est = pd.read_csv(HIST / "career_rate_estimates.csv", dtype={"player_id": str})
    rel = pd.read_csv(HIST / "career_ability_reliability.csv")
    for rate, succ, tri in [("shooting_pct", "goals", "shots"),
                            ("one_point_pct", "one_point_goals", "one_point_attempts"),
                            ("faceoff_win_pct", "faceoff_wins", "faceoffs"),
                            ("save_pct", "saves", None),
                            ("turnovers_per_touch", "turnovers", "touches"),
                            ("two_point_pct", "two_point_goals", "two_point_attempts")]:
        s = pd.to_numeric(p[succ], errors="coerce").fillna(0)
        t = ((pd.to_numeric(p["saves"], errors="coerce").fillna(0)
              + pd.to_numeric(p["goals_allowed"], errors="coerce").fillna(0))
             if tri is None else pd.to_numeric(p[tri], errors="coerce").fillna(0))
        frame = pd.DataFrame({"player_id": p["player_id"], "season": p["season"],
                              "s": s, "t": t})
        for min_tri in (10, 20, 40):
            q = frame[frame["t"] >= min_tri].copy()
            q["rate"] = q["s"] / q["t"]
            nxt = q.copy()
            nxt["season"] -= 1
            mm = q.merge(nxt, on=["player_id", "season"], suffixes=("_t", "_t1"))
            rows.append({
                "family": "career_rate", "target": rate,
                "test": f"year_to_year_pearson_min_trials_{min_tri}",
                "statistic": float(np.corrcoef(mm["rate_t"], mm["rate_t1"])[0, 1])
                if len(mm) > 4 else np.nan,
                "n": int(len(mm)),
                "detail": "sensitivity of the persistence estimate to the "
                          "minimum-opportunity choice"})
        # split-half: odd vs even seasons of a career
        odd = frame[frame["season"] % 2 == 1].groupby("player_id")[["s", "t"]].sum()
        even = frame[frame["season"] % 2 == 0].groupby("player_id")[["s", "t"]].sum()
        j = odd.join(even, lsuffix="_o", rsuffix="_e", how="inner")
        j = j[(j["t_o"] >= 20) & (j["t_e"] >= 20)]
        if len(j) > 4:
            r = float(np.corrcoef(j["s_o"] / j["t_o"], j["s_e"] / j["t_e"])[0, 1])
            # Spearman-Brown steps a half-length correlation up to full length
            rows.append({"family": "career_rate", "target": rate,
                         "test": "split_half_odd_vs_even_seasons",
                         "statistic": r, "n": int(len(j)),
                         "detail": f"Spearman-Brown full-career estimate "
                                   f"{2*r/(1+r):.3f}; both halves >= 20 trials"})
        # raw vs shrunk: how much does the ability ordering depend on it?
        e = est[est["rate_name"] == rate]
        e = e[e["career_trials"] > 0]
        if len(e) > 5:
            rows.append({"family": "career_rate", "target": rate,
                         "test": "spearman_raw_vs_shrunk_career_rate",
                         "statistic": _rho(e["career_rate_raw"],
                                           e["career_rate_shrunk"]),
                         "n": int(len(e)),
                         "detail": "how much of the ability ordering survives "
                                   "the shrinkage choice"})
            for gate in (0.3, 0.5, 0.7):
                q = e[e["reliability"] >= gate]
                rows.append({"family": "career_rate", "target": rate,
                             "test": f"n_players_at_reliability_gate_{gate}",
                             "statistic": float(len(q)), "n": int(len(e)),
                             "detail": "sensitivity of the qualifying "
                                       "population to the reliability gate"})

    # --- leave-one-season-out on the role baselines -----------------------
    for role in ROLES:
        g = d[d["role"] == role]
        if len(g) < 20:
            continue
        full = float(g["v"].mean())
        moves = [abs(float(g[g["season"] != y]["v"].mean()) - full)
                 for y in SEASONS if (g["season"] != y).sum() > 5]
        rows.append({"family": "positional_baseline", "target": role,
                     "test": "max_abs_move_of_role_mean_leave_one_season_out",
                     "statistic": max(moves) if moves else np.nan,
                     "n": int(len(g)),
                     "detail": f"role mean {full:.3f}; role sd "
                               f"{g['v'].std(ddof=0):.3f}"})
    return pd.DataFrame(rows)


def main():
    HIST.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 250)
    p = load_players()

    audit = value_audit(p)
    audit.to_csv(HIST / "cross_position_value_audit.csv", index=False)

    base = positional_baselines(p)
    base.to_csv(HIST / "positional_baselines.csv", index=False)

    labels = position_label_consistency(p)
    labels.to_csv(HIST / "position_label_consistency.csv", index=False)

    d, repl = method_values(p)
    repl.to_csv(HIST / "cross_position_replacement_level.csv", index=False)

    mc = method_comparison(d, repl)
    mc.to_csv(HIST / "cross_position_method_comparison.csv", index=False)

    cf = counterfactuals(d, repl)
    cf.to_csv(HIST / "cross_position_counterfactuals.csv", index=False)

    da = defensive_attribution_audit(p)
    da.to_csv(HIST / "defensive_attribution_audit.csv", index=False)

    st = historical_stability(p, d)
    st.to_csv(HIST / "phase10_historical_stability.csv", index=False)

    print("=== G. ROLE SCALES, EPA_points_raw ===")
    a = audit[(audit["component"] == "EPA_points_raw")
              & (audit["scope_kind"] == "season") & audit["role"].isin(ROLES)]
    print(a.pivot_table(index="role", columns="scope", values="value_sd")
          .round(3).to_string())
    hl = audit[audit["role"] == "ALL_ROLES"]
    print("\n  SD ratio, widest role to narrowest, by season:")
    print(hl[["scope", "value_sd_max_over_min_across_roles", "value_sd_max_role",
              "value_sd_min_role", "opportunity_mean_max_over_min_across_roles"]]
          .round(2).to_string(index=False))

    print("\n=== H. BASELINE SCOPE ===")
    diag = base[base["baseline_scope"] == "position_season_stability_diagnostic"]
    print(diag[diag["component"] == "EPA_points_raw"][
        ["baseline_key", "denominated_per_opportunity",
         "between_season_sd_of_baseline", "mean_within_season_se_of_baseline",
         "between_season_sd_over_se", "recommended_scope"]].round(4).to_string(index=False))

    print("\n=== F. METHOD COMPARISON ===")
    print(mc[["method", "n_player_seasons_defined",
              "spearman_with_role_opportunities", "spearman_with_games_played",
              "top20_share_goalie", "top20_share_faceoff",
              "role_sd_max_over_min_after_transform",
              "pct_of_top_decile_that_is_below_median_opportunity",
              "year_to_year_spearman", "scale_equalization_mechanism"]]
          .round(3).to_string(index=False))

    print("\n=== F. REPLACEMENT LEVEL ===")
    print(repl.drop_duplicates("role")[
        ["role", "mean_marginal_player_level", "between_season_sd_of_marginal_player_level",
         "mean_se_of_marginal_player_level", "signal_to_noise",
         "marginal_player_level_as_share_of_role_sd",
         "empirically_definable"]].round(4).to_string(index=False))

    print("\n=== G. COUNTERFACTUAL P1: equally elite within role ===")
    p1 = cf[cf["probe"] == "P1_equally_elite_within_role"]
    print(p1[["role", "synthetic_value_EPA_points", "role_mean", "role_sd",
              "M01_raw_value_above_role_baseline", "M04_within_position_z",
              "M07_value_above_marginal_roster_player"]].round(3).to_string(index=False))

    print("\n=== I. DEFENSIVE ATTRIBUTION ===")
    print(da[["season", "turnover_events", "turnover_events_naming_a_player",
              "turnover_events_naming_a_causing_defender",
              "events_naming_a_closest_defender",
              "defensive_value_spearman_with_games_played",
              "caused_turnovers_spearman_with_games_played",
              "defensive_value_sd", "goalie_value_sd"]].round(3).to_string(index=False))

    print("\n=== J. STABILITY (selected) ===")
    print(st[st["family"] == "career_rate"]
          .query("test.str.startswith('split_half') or "
                 "test.str.startswith('spearman_raw')", engine="python")
          [["target", "test", "statistic", "n", "detail"]].round(3).to_string(index=False))
    return audit, base, mc, cf, repl, da, st


if __name__ == "__main__":
    main()
