"""
Phase 13: production role-specific player value models (v1).

Implements EXACTLY the frozen specification in
data/processed/history/player_value_model_spec_v1.csv (written by
pll_phase13_model_spec.py and not edited after this module's leaderboards
were first generated -- any change is recorded in
player_value_model_change_log.csv, never silently).

No new value formula is introduced. Every component reuses an
already-canonical 2022-2026 column (shooting_value_raw, turnover_value_raw,
faceoff_value_raw, goalie_value_raw, defensive_value_partial_raw) computed
by the Phase 6-10 SQL/Python pipeline. What Phase 13 adds:

  1. Role-specific leaderboards and component tables, one file per role,
     never combined into a cross-role ranking.
  2. An EXACT algebraic rate/volume (faceoff) and rate/workload (goalie)
     decomposition of the existing published value -- not a new estimate.
  3. Parametric binomial bootstrap uncertainty (1,000 draws, fixed seed) and
     rank-stability diagnostics (top-N inclusion frequency, pairwise P(A>B)).
  4. Qualification flags built from already-published reliability/
     eligibility columns (no new threshold invented).

Run across all five canonical seasons identically -- Section N's historical
backtest is this same code applied to each season's slice of the one
already-canonical table, not a separate model.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"
SEASONS = [2022, 2023, 2024, 2025, 2026]
N_BOOT = 1000
RNG_SEED = 20261013


def load_players() -> pd.DataFrame:
    return pd.read_csv(HIST / "player_stats_2022_2026.csv",
                       dtype={"player_id": str, "team_id": str})


def load_career() -> pd.DataFrame:
    return pd.read_csv(HIST / "player_career_2022_2026.csv", dtype={"player_id": str})


def _qualification(row, reliability_col, eligible_col) -> str:
    """Reuses already-published columns; invents no new threshold."""
    rel = row.get(reliability_col)
    elig = row.get(eligible_col)
    opp = row.get("_opportunity", np.nan)
    if pd.isna(opp) or opp == 0:
        return "INSUFFICIENT_EVIDENCE"
    if pd.notna(rel) and rel >= 0.5 and bool(elig):
        return "QUALIFIED"
    if bool(elig):
        return "SMALL_SAMPLE"
    return "DESCRIPTIVE_ONLY"


# ===========================================================================
# OFFENSE
# ===========================================================================
def _offense_bootstrap(sub: pd.DataFrame, rng) -> dict:
    """Resamples one/two-point makes at the observed rate; holds the
    expected-points baseline and turnover_value fixed (documented limitation,
    player_value_model_spec_v1.csv row offensive_value_v1/turnover_value)."""
    n = len(sub)
    opa = sub["one_point_attempts"].fillna(0).to_numpy()
    opg = sub["one_point_goals"].fillna(0).to_numpy()
    tpa = sub["two_point_attempts"].fillna(0).to_numpy()
    tpg = sub["two_point_goals"].fillna(0).to_numpy()
    obs_points = opg * 1 + tpg * 2
    shooting_value = sub["shooting_value_raw"].to_numpy()
    expected_points = obs_points - np.nan_to_num(shooting_value)
    one_rate = np.divide(opg, opa, out=np.zeros(n), where=opa > 0)
    two_rate = np.divide(tpg, tpa, out=np.zeros(n), where=tpa > 0)

    draws = np.empty((N_BOOT, n))
    for b in range(N_BOOT):
        op_sim = rng.binomial(opa.astype(int), np.clip(one_rate, 0, 1))
        tp_sim = rng.binomial(tpa.astype(int), np.clip(two_rate, 0, 1))
        shooting_sim = (op_sim * 1 + tp_sim * 2) - expected_points
        draws[b] = shooting_sim + np.nan_to_num(sub["turnover_value_raw"].to_numpy())
    return {"draws": draws}


def build_offensive_value(players: pd.DataFrame, season: int) -> tuple:
    p = players[players["season"] == season]
    sub = p[p["position_group"].isin(["attack", "midfield"])].copy()
    sub["_opportunity"] = sub["shots"].fillna(0)
    sub["offensive_value"] = (sub["shooting_value_raw"].fillna(0)
                              + sub["turnover_value_raw"].fillna(0))
    identity_gap = (sub["offensive_value"] - sub["offensive_EPA_points_raw"]).abs().max()
    assert identity_gap < 1e-6, f"offensive_value != offensive_EPA_points_raw: {identity_gap}"

    sub["qualification_state"] = sub.apply(
        lambda r: _qualification(r, "role_rate_reliability", "offensive_rate_ranking_eligible"), axis=1)

    rng = np.random.default_rng(RNG_SEED)
    boot = _offense_bootstrap(sub, rng)
    draws = boot["draws"]
    sub["value_ci_lo"] = np.percentile(draws, 2.5, axis=0)
    sub["value_ci_hi"] = np.percentile(draws, 97.5, axis=0)
    sub["value_boot_sd"] = draws.std(axis=0)

    ranks_per_draw = (-draws).argsort(axis=1).argsort(axis=1) + 1  # 1 = best
    sub = sub.reset_index(drop=True)
    sub["rank_ci_lo"] = np.percentile(ranks_per_draw, 2.5, axis=0)
    sub["rank_ci_hi"] = np.percentile(ranks_per_draw, 97.5, axis=0)
    top10_freq = (ranks_per_draw <= 10).mean(axis=0)
    sub["top10_inclusion_frequency"] = top10_freq

    # two_point_attempt_share: SELECTION (identifiable), never conflated with
    # two_point_conversion_pct (UNSUPPORTED as ability, PLAYER_VALUE_MODEL_SPEC_V1
    # row offensive_value_v1/two_point_selection). Computed directly here --
    # player_stats_2022_2026.csv carries the career-level shrunk version only
    # in career_ability_reliability.csv, not a per-season raw column.
    sub["two_point_attempt_share_raw"] = np.divide(
        sub["two_point_attempts"].fillna(0), sub["shots"].replace(0, np.nan))

    sub = sub.sort_values("offensive_value", ascending=False).reset_index(drop=True)
    sub["rank"] = np.arange(1, len(sub) + 1)

    leaderboard = sub[[
        "rank", "player_id", "player_name", "team_id", "canonical_position",
        "position_group", "games_played", "shots", "shots_on_goal",
        "one_point_attempts", "two_point_attempts", "one_point_goals",
        "two_point_goals", "scoring_points", "turnovers", "touches",
        "shooting_pct", "two_point_attempt_share_raw",
        "offensive_EPA_points_raw", "offensive_value", "value_ci_lo", "value_ci_hi",
        "value_boot_sd", "rank_ci_lo", "rank_ci_hi", "top10_inclusion_frequency",
        "role_rate_reliability", "qualification_state",
    ]].copy()
    leaderboard["publication_caveat"] = (
        "Season-total value, not ability; year-to-year rank correlation is 0.16-0.25 "
        "(CROSS_POSITION_VALUE_RESEARCH.md). Turnover count is not independently bootstrapped "
        "(see PLAYER_VALUE_UNCERTAINTY.md). two_point_attempt_share_raw is a SELECTION tendency, "
        "not a conversion-ability estimate -- two-point conversion ability remains UNSUPPORTED.")

    components = sub[[
        "player_id", "player_name", "team_id", "season", "shooting_value_raw",
        "turnover_value_raw", "offensive_value", "two_point_attempts",
        "two_point_goals", "two_point_attempt_share_raw",
    ]].copy()
    components["accounting_check"] = (
        components["shooting_value_raw"].fillna(0) + components["turnover_value_raw"].fillna(0)
        - components["offensive_value"]).abs()

    # rank-change / pairwise uncertainty for adjacent players
    pairwise = []
    for i in range(min(len(sub) - 1, 30)):
        a, b = draws[:, i], draws[:, i + 1]
        p_a_gt_b = float((a > b).mean())
        pairwise.append({
            "season": season, "rank_a": i + 1, "rank_b": i + 2,
            "player_a": sub.loc[i, "player_name"], "player_b": sub.loc[i + 1, "player_name"],
            "p_a_greater_than_b": p_a_gt_b,
        })
    pairwise_df = pd.DataFrame(pairwise)

    return leaderboard, components, pairwise_df


# ===========================================================================
# FACEOFF
# ===========================================================================
def _recover_faceoff_coefficient(sub: pd.DataFrame) -> float:
    p_win = sub["faceoff_wins"].sum() / sub["faceoffs"].sum()
    denom = sub["faceoff_wins"] - sub["faceoffs"] * p_win
    ratios = (sub["faceoff_value_raw"] / denom).replace([np.inf, -np.inf], np.nan)
    ratios = ratios[denom.abs() > 5]  # avoid near-zero-denominator instability
    return float(ratios.median()), p_win


def build_faceoff_value(players: pd.DataFrame, season: int) -> tuple:
    p = players[players["season"] == season]
    sub = p[p["position_group"] == "faceoff"].copy().reset_index(drop=True)
    sub["_opportunity"] = sub["faceoffs"].fillna(0)
    coef, p_win = _recover_faceoff_coefficient(sub)

    league_mean_faceoffs = sub.loc[sub["faceoffs"] > 0, "faceoffs"].mean()
    sub["faceoff_value_total"] = sub["faceoff_value_raw"]
    sub["faceoff_rate_value"] = sub["faceoff_value_total"] * (league_mean_faceoffs / sub["faceoffs"])
    sub["faceoff_volume_value"] = sub["faceoff_value_total"] - sub["faceoff_rate_value"]
    decomp_gap = (sub["faceoff_rate_value"] + sub["faceoff_volume_value"]
                 - sub["faceoff_value_total"]).abs().max()
    assert decomp_gap < 1e-9, f"faceoff decomposition does not sum: {decomp_gap}"

    sub["qualification_state"] = sub.apply(
        lambda r: _qualification(r, "role_rate_reliability", "future_award_input_eligible"), axis=1)

    rng = np.random.default_rng(RNG_SEED + 1)
    n = len(sub)
    faceoffs = sub["faceoffs"].fillna(0).to_numpy()
    wins = sub["faceoff_wins"].fillna(0).to_numpy()
    win_rate = np.divide(wins, faceoffs, out=np.zeros(n), where=faceoffs > 0)
    draws = np.empty((N_BOOT, n))
    for b in range(N_BOOT):
        wins_sim = rng.binomial(faceoffs.astype(int), np.clip(win_rate, 0, 1))
        draws[b] = coef * (wins_sim - faceoffs * p_win)

    sub["value_ci_lo"] = np.percentile(draws, 2.5, axis=0)
    sub["value_ci_hi"] = np.percentile(draws, 97.5, axis=0)
    sub["value_boot_sd"] = draws.std(axis=0)
    ranks_per_draw = (-draws).argsort(axis=1).argsort(axis=1) + 1
    sub["rank_ci_lo"] = np.percentile(ranks_per_draw, 2.5, axis=0)
    sub["rank_ci_hi"] = np.percentile(ranks_per_draw, 97.5, axis=0)
    sub["top10_inclusion_frequency"] = (ranks_per_draw <= 10).mean(axis=0)

    sub = sub.sort_values("faceoff_value_total", ascending=False).reset_index(drop=True)
    sub["rank"] = np.arange(1, len(sub) + 1)
    sub["workload_vs_skill"] = np.where(
        sub["faceoff_volume_value"].abs() > sub["faceoff_rate_value"].abs(),
        "VOLUME_DRIVEN", "RATE_DRIVEN")

    leaderboard = sub[[
        "rank", "player_id", "player_name", "team_id", "games_played",
        "faceoffs", "faceoff_wins", "faceoff_losses", "faceoff_win_pct",
        "faceoff_value_total", "faceoff_rate_value", "faceoff_volume_value",
        "workload_vs_skill", "value_ci_lo", "value_ci_hi", "value_boot_sd",
        "rank_ci_lo", "rank_ci_hi", "top10_inclusion_frequency",
        "role_rate_reliability", "qualification_state",
    ]].copy()
    leaderboard["baseline_faceoff_win_pct"] = p_win
    leaderboard["publication_caveat"] = (
        "faceoff_volume_value is mechanically driven by draw count, not skill (Phase 10 probe P5, "
        "Phase 12 counterfactual T4). A ranking by faceoff_value_total rewards being given more draws.")

    components = sub[[
        "player_id", "player_name", "team_id", "faceoffs", "faceoff_wins",
        "faceoff_value_total", "faceoff_rate_value", "faceoff_volume_value",
    ]].copy()
    components["season"] = season
    components["accounting_check"] = (
        components["faceoff_rate_value"] + components["faceoff_volume_value"]
        - components["faceoff_value_total"]).abs()

    return leaderboard, components, coef, p_win


# ===========================================================================
# GOALIE
# ===========================================================================
def build_goalie_value(players: pd.DataFrame, season: int) -> tuple:
    p = players[players["season"] == season]
    sub = p[p["position_group"] == "goalie"].copy().reset_index(drop=True)
    sub["_opportunity"] = sub["shots_on_goal_faced"].fillna(0)

    sub["expected_points_allowed"] = sub["pll_points_allowed"].fillna(0) + sub["goalie_value_raw"].fillna(0)
    sub["goalie_value_total"] = sub["goalie_value_raw"]

    league_mean_sog = sub.loc[sub["shots_on_goal_faced"] > 0, "shots_on_goal_faced"].mean()
    sub["goalie_rate_value"] = sub["goalie_value_total"] * (league_mean_sog / sub["shots_on_goal_faced"])
    sub["goalie_workload_value"] = sub["goalie_value_total"] - sub["goalie_rate_value"]
    decomp_gap = (sub["goalie_rate_value"] + sub["goalie_workload_value"]
                 - sub["goalie_value_total"]).abs().max()
    assert decomp_gap < 1e-9, f"goalie decomposition does not sum: {decomp_gap}"

    sub["qualification_state"] = sub.apply(
        lambda r: _qualification(r, "role_rate_reliability", "future_award_input_eligible"), axis=1)

    rng = np.random.default_rng(RNG_SEED + 2)
    n = len(sub)
    one_sog = sub["one_point_shots_on_goal_faced"].fillna(0).to_numpy()
    two_sog = sub["two_point_shots_on_goal_faced"].fillna(0).to_numpy()
    one_allowed = sub["goals_allowed"].fillna(0).to_numpy() - sub["two_point_goals_allowed"].fillna(0).to_numpy()
    two_allowed = sub["two_point_goals_allowed"].fillna(0).to_numpy()
    one_rate = np.divide(one_allowed, one_sog, out=np.zeros(n), where=one_sog > 0)
    two_rate = np.divide(two_allowed, two_sog, out=np.zeros(n), where=two_sog > 0)
    expected = sub["expected_points_allowed"].to_numpy()

    draws = np.empty((N_BOOT, n))
    for b in range(N_BOOT):
        one_sim = rng.binomial(one_sog.astype(int), np.clip(one_rate, 0, 1))
        two_sim = rng.binomial(two_sog.astype(int), np.clip(two_rate, 0, 1))
        actual_sim = one_sim * 1 + two_sim * 2
        draws[b] = expected - actual_sim

    sub["value_ci_lo"] = np.percentile(draws, 2.5, axis=0)
    sub["value_ci_hi"] = np.percentile(draws, 97.5, axis=0)
    sub["value_boot_sd"] = draws.std(axis=0)
    ranks_per_draw = (-draws).argsort(axis=1).argsort(axis=1) + 1
    sub["rank_ci_lo"] = np.percentile(ranks_per_draw, 2.5, axis=0)
    sub["rank_ci_hi"] = np.percentile(ranks_per_draw, 97.5, axis=0)
    sub["top10_inclusion_frequency"] = (ranks_per_draw <= 10).mean(axis=0)

    sub = sub.sort_values("goalie_value_total", ascending=False).reset_index(drop=True)
    sub["rank"] = np.arange(1, len(sub) + 1)
    sub["workload_vs_skill"] = np.where(
        sub["goalie_workload_value"].abs() > sub["goalie_rate_value"].abs(),
        "WORKLOAD_DRIVEN", "SKILL_DRIVEN")

    leaderboard = sub[[
        "rank", "player_id", "player_name", "team_id", "games_played",
        "shots_on_goal_faced", "saves", "goals_allowed", "save_pct",
        "expected_points_allowed", "pll_points_allowed", "goalie_value_total",
        "goalie_rate_value", "goalie_workload_value", "workload_vs_skill",
        "value_ci_lo", "value_ci_hi", "value_boot_sd", "rank_ci_lo", "rank_ci_hi",
        "top10_inclusion_frequency", "role_rate_reliability", "qualification_state",
    ]].rename(columns={"pll_points_allowed": "observed_points_allowed"})
    leaderboard["publication_caveat"] = (
        "goalie_workload_value is substantially the team's defensive shot volume, not the goalie's own action "
        "(Phase 10 probe P4, Phase 12 counterfactual T5). NOT shot-quality adjusted -- no location/distance/"
        "defender data exists in this feed.")

    components = sub[[
        "player_id", "player_name", "team_id", "shots_on_goal_faced",
        "goalie_value_total", "goalie_rate_value", "goalie_workload_value",
    ]].copy()
    components["season"] = season
    components["accounting_check"] = (
        components["goalie_rate_value"] + components["goalie_workload_value"]
        - components["goalie_value_total"]).abs()

    return leaderboard, components


# ===========================================================================
# DEFENSE
# ===========================================================================
def build_defensive_production(players: pd.DataFrame, season: int) -> pd.DataFrame:
    p = players[players["season"] == season]
    sub = p[p["position_group"] == "defensive_field"].copy()
    sub = sub.sort_values("games_played", ascending=False).reset_index(drop=True)
    out = sub[[
        "player_id", "player_name", "team_id", "canonical_position",
        "games_played", "caused_turnovers", "ground_balls", "penalties",
        "defensive_value_partial_raw",
    ]].copy()
    out["caused_turnovers_per_game"] = out["caused_turnovers"] / out["games_played"].replace(0, np.nan)
    out["data_coverage"] = (
        "PARTIAL: caused_turnovers and ground_balls are box-score totals with a games-played denominator "
        "only (no minutes/shifts/lineups exist). Zero of this feed's raw events name a causing or closest "
        "defender. defensive_value_partial_raw residualizes caused turnovers against the position group's "
        "per-game rate and is shown for continuity with the canonical dataset, but this table is NOT sorted "
        "or ranked by it -- see docs/DEFENSIVE_PRODUCTION_LIMITATIONS.md.")
    out["publication_status"] = "ROLE_ONLY -- descriptive production, NOT individual defensive value"
    return out


# ===========================================================================
# Orchestration
# ===========================================================================
def run_all_seasons():
    players = load_players()
    off_lb, off_comp, off_pair = {}, {}, {}
    fo_lb, fo_comp, fo_coef = {}, {}, {}
    go_lb, go_comp = {}, {}
    def_prod = {}

    for s in SEASONS:
        off_lb[s], off_comp[s], off_pair[s] = build_offensive_value(players, s)
        fo_lb[s], fo_comp[s], coef, p_win = build_faceoff_value(players, s)
        fo_coef[s] = {"coefficient": coef, "league_win_rate": p_win}
        go_lb[s], go_comp[s] = build_goalie_value(players, s)
        def_prod[s] = build_defensive_production(players, s)

    return {
        "offense": (off_lb, off_comp, off_pair), "faceoff": (fo_lb, fo_comp, fo_coef),
        "goalie": (go_lb, go_comp), "defense": def_prod,
    }


def main():
    results = run_all_seasons()
    off_lb, off_comp, off_pair = results["offense"]
    fo_lb, fo_comp, fo_coef = results["faceoff"]
    go_lb, go_comp = results["goalie"]
    def_prod = results["defense"]

    PROC26 = PROC / "2026"
    off_lb[2026].to_csv(PROC26 / "offensive_value_2026.csv", index=False)
    off_comp[2026].to_csv(PROC26 / "offensive_value_components.csv", index=False)
    fo_lb[2026].to_csv(PROC26 / "faceoff_value_2026.csv", index=False)
    fo_comp[2026].to_csv(PROC26 / "faceoff_value_components.csv", index=False)
    go_lb[2026].to_csv(PROC26 / "goalie_value_2026.csv", index=False)
    go_comp[2026].to_csv(PROC26 / "goalie_value_components.csv", index=False)
    def_prod[2026].to_csv(PROC26 / "defensive_production_2026.csv", index=False)

    pd.concat([off_lb[s].assign(season=s) for s in SEASONS], ignore_index=True).to_csv(
        HIST / "offensive_value_2022_2026.csv", index=False)
    pd.concat([fo_lb[s].assign(season=s) for s in SEASONS], ignore_index=True).to_csv(
        HIST / "faceoff_value_2022_2026.csv", index=False)
    pd.concat([go_lb[s].assign(season=s) for s in SEASONS], ignore_index=True).to_csv(
        HIST / "goalie_value_2022_2026.csv", index=False)
    pd.concat([def_prod[s].assign(season=s) for s in SEASONS], ignore_index=True).to_csv(
        HIST / "defensive_production_2022_2026.csv", index=False)
    pd.concat([off_pair[s] for s in SEASONS], ignore_index=True).to_csv(
        HIST / "offensive_value_pairwise_uncertainty_2022_2026.csv", index=False)
    pd.DataFrame([{"season": s, **fo_coef[s]} for s in SEASONS]).to_csv(
        HIST / "faceoff_value_recovered_coefficients.csv", index=False)

    print("2026 leaderboards:")
    print(f"  offense: {len(off_lb[2026])} players, top: {off_lb[2026].iloc[0]['player_name']} "
         f"({off_lb[2026].iloc[0]['offensive_value']:.2f})")
    print(f"  faceoff: {len(fo_lb[2026])} players, top: {fo_lb[2026].iloc[0]['player_name']} "
         f"({fo_lb[2026].iloc[0]['faceoff_value_total']:.2f})")
    print(f"  goalie: {len(go_lb[2026])} players, top: {go_lb[2026].iloc[0]['player_name']} "
         f"({go_lb[2026].iloc[0]['goalie_value_total']:.2f})")
    print(f"  defensive production: {len(def_prod[2026])} players (descriptive, unranked)")


if __name__ == "__main__":
    main()
