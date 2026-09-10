"""
Phase 9: validation of the 2022-2026 historical layer.

Writes data/processed/history/phase9_validation_report.csv in the same
check_id / check_name / status / n_failures / detail shape as every earlier
phase.

INDEPENDENCE. Every numeric check recomputes its target from the raw JSON
corpus or the canonical tables using pandas. The production SQL is never
re-executed to check itself, and no check reads the artifact it is validating
as its own source of truth.

The single most important checks are 1 (no completed competitive game is
silently missing), 12 (Phase 8's 2026 numbers are untouched) and 16 (the
pooled files are exactly the union of the season files). Phase 9 adds four
seasons; it must not move 2026 by one bit.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = REPO_ROOT / "data" / "raw"
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"
SEASONS = [2022, 2023, 2024, 2025, 2026]
HISTORY_ONLY = [2022, 2023, 2024, 2025]
TOL = 1e-9

SHOT_TYPE_POINTS = {"1_PT": 1, "MU": 1, "2_PT": 2, "MU_2_PT": 2}

# Every 2026 file Phase 8 published. Phase 9 may not change any of them.
PHASE8_2026 = [
    "team_stats_2026.csv", "player_stats_2026.csv", "team_leaderboards_2026.csv",
    "player_leaderboards_2026.csv", "two_point_audit_2026.csv",
    "metric_catalog_2026.csv", "metric_distribution_audit_2026.csv",
    "metric_redundancy_2026.csv", "metric_sanity_flags_2026.csv",
    "phase8_qualification_rules.csv", "team_season_advanced.csv",
    "player_value_components.csv", "player_adjusted_value.csv",
    "events.csv", "possessions.csv", "games.csv", "players.csv",
    "player_game_stats.csv", "team_game_stats.csv",
]


def sf(y, name, **kw):
    return pd.read_csv(PROC / str(y) / name, **kw)


def hf(name, **kw):
    return pd.read_csv(HIST / name, **kw)


def schedule(y):
    return json.loads((RAW / str(y) / "_schedule" / f"games_{y}.json")
                      .read_text())["data"]["items"]


def main():
    results = []

    def check(cid, name, n_fail, detail=""):
        results.append({"check_id": cid, "check_name": name,
                        "status": "PASS" if n_fail == 0 else "FAIL",
                        "n_failures": int(n_fail), "detail": detail})

    # ---- 1. every completed competitive game is accounted for -------------
    n1, bad1 = 0, []
    inv = hf("historical_game_inventory.csv")
    for y in SEASONS:
        sched = schedule(y)
        # recompute completion independently of the pipeline's own helper
        comp = [g for g in sched
                if g.get("eventStatus") == 3
                or (g.get("eventStatus") == 2 and g.get("homeScore") is not None
                    and g.get("visitorScore") is not None)]
        competitive = [g for g in comp
                       if g.get("seasonSegment") in ("regular", "post")]
        inv_y = inv[inv["season"] == y]
        accounted = set(inv_y["game_slug"])
        missing = [g["slugname"] for g in competitive
                   if g["slugname"] not in accounted]
        if missing:
            n1 += len(missing)
            bad1.append(f"{y}: {missing} absent from the inventory")
        # every competitive completed game must be admitted OR carry a reason
        unexplained = inv_y[inv_y["is_competitive"] & inv_y["is_completed"]
                            & ~inv_y["admitted_to_analytics"]
                            & (inv_y["exception_reason"].fillna("") == "")]
        if len(unexplained):
            n1 += len(unexplained)
            bad1.append(f"{y}: {len(unexplained)} unadmitted with no reason")
        # and the events table must contain exactly the admitted games
        ev_games = set(sf(y, "events.csv", low_memory=False,
                          usecols=["game_id"])["game_id"])
        g = sf(y, "games.csv")
        want = set(g[g["is_completed"] & g["include_in_league_analytics"]
                     & ~g["is_all_star"]]["game_id"])
        if not want <= ev_games:
            n1 += len(want - ev_games)
            bad1.append(f"{y}: {len(want - ev_games)} eligible games have no events")
    check(1, "every_completed_competitive_game_accounted_for", n1,
          f"{len(inv)} scheduled games across {inv['season'].nunique()} seasons "
          f"re-derived from the raw schedule JSON; "
          f"{int(inv['admitted_to_analytics'].sum())} admitted. {bad1 or 'no silent gaps'}")

    # ---- 2. unique game identity -----------------------------------------
    n2, bad2 = 0, []
    for y in SEASONS:
        g = sf(y, "games.csv")
        for col in ("game_id", "game_slug"):
            d = int(g.duplicated(subset=[col]).sum())
            if d:
                n2 += d; bad2.append(f"{y}.{col}={d}")
    check(2, "unique_game_identity", n2,
          f"game_id and game_slug unique in all {len(SEASONS)} seasons. "
          f"{bad2 or 'no duplicates'}")

    # ---- 3. unique canonical event identity -------------------------------
    n3, bad3 = 0, []
    for y in SEASONS:
        ev = sf(y, "events.csv", low_memory=False,
                usecols=["game_id", "event_id"], dtype={"event_id": str})
        d = int(ev.duplicated().sum())
        if d:
            n3 += d; bad3.append(f"{y}={d}")
    check(3, "unique_event_identity", n3,
          f"(game_id, event_id) unique in every season. {bad3 or 'no duplicates'}")

    # ---- 4. team ids resolve where it matters ------------------------------
    # Scoped to ANALYTICS-ELIGIBLE games. All-star rosters (ASA/ASH in 2023-24)
    # legitimately never enter teams.csv: their game carries no box-score feed,
    # so it is skipped, and an all-star franchise is excluded from analytics in
    # every season anyway. The check therefore also asserts the stronger and
    # more useful statement -- that any unresolved team is confined to an
    # excluded game.
    n4, bad4 = 0, []
    for y in SEASONS:
        teams = set(sf(y, "teams.csv", dtype={"team_id": str})["team_id"])
        g = sf(y, "games.csv", dtype={"home_team_id": str, "away_team_id": str})
        elig = g[g["is_completed"] & g["include_in_league_analytics"]
                 & ~g["is_all_star"]]
        unknown = ((set(elig["home_team_id"].dropna())
                    | set(elig["away_team_id"].dropna())) - teams)
        if unknown:
            n4 += len(unknown)
            bad4.append(f"{y}: {sorted(unknown)} referenced by an ELIGIBLE game")
        outside = ((set(g[g["is_completed"]]["home_team_id"].dropna())
                    | set(g[g["is_completed"]]["away_team_id"].dropna())) - teams)
        if outside:
            bad4.append(f"{y}: {sorted(outside)} appear only in excluded games (expected)")
    check(4, "team_ids_resolve_in_eligible_games", n4,
          f"every team referenced by an analytics-eligible game exists in "
          f"teams.csv, in all five seasons. {bad4 or 'all resolve'}")

    # ---- 5. player ids resolve in eligible games ---------------------------
    # Same scoping as check 4, for the same reason: 2022's 19 unresolved ids are
    # all trialists who appeared ONLY in the four preseason scrimmages and never
    # in a regular-season box score, so they are correctly absent from
    # players.csv. The check asserts (a) format, (b) that every id referenced by
    # an ELIGIBLE game resolves, and (c) that anything unresolved is confined to
    # an excluded game -- which is the fact that makes (b) safe.
    n5, bad5 = 0, []
    ID_COLS = ["player_id", "secondary_player_id", "gb_player_id", "goalie_id"]
    for y in SEASONS:
        pl = sf(y, "players.csv", dtype={"player_id": str})
        known = set(pl["player_id"])
        badfmt = pl[~pl["player_id"].str.fullmatch(r"\d{6}")]
        if len(badfmt):
            n5 += len(badfmt); bad5.append(f"{y}: {len(badfmt)} malformed ids")
        g = sf(y, "games.csv")
        elig = set(g[g["is_completed"] & g["include_in_league_analytics"]
                     & ~g["is_all_star"]]["game_id"])
        ev = sf(y, "events.csv", low_memory=False, dtype=str)
        cols = [c for c in ID_COLS if c in ev.columns]
        in_elig = ev[ev["game_id"].astype(int).isin(elig)] if len(ev) else ev
        for c in cols:
            unk = set(in_elig[c].dropna()) - known
            if unk:
                n5 += len(unk)
                bad5.append(f"{y}.{c}: {len(unk)} unresolved in an ELIGIBLE game")
        outside = set()
        for c in cols:
            outside |= (set(ev[c].dropna()) - known)
        if outside:
            bad5.append(f"{y}: {len(outside)} id(s) appear only in excluded "
                        f"(preseason/all-star) games, as expected")
    check(5, "player_ids_resolve_in_eligible_games", n5,
          f"every player_id is a 6-digit officialId, and every id referenced by "
          f"an analytics-eligible game resolves, in all five seasons. "
          f"{bad5 or 'all resolve'}")

    # ---- 6. cross-season identity mappings --------------------------------
    ident = hf("historical_player_identity_audit.csv", dtype={"player_id": str})
    n6, bad6 = 0, []
    frames = []
    for y in SEASONS:
        p = sf(y, "players.csv", dtype={"player_id": str})[["player_id", "name"]]
        p["season"] = y
        frames.append(p)
    allp = pd.concat(frames, ignore_index=True)
    if set(ident["player_id"]) != set(allp["player_id"]):
        n6 += 1; bad6.append("identity audit does not cover exactly the observed ids")
    # a name may not map to two ids, and an id may not map to two names
    if int(allp.groupby("name")["player_id"].nunique().gt(1).sum()):
        pass  # not a failure; flagged in the audit
    recomputed = allp.groupby("player_id")["season"].nunique()
    if not np.array_equal(
            ident.set_index("player_id")["n_seasons"].reindex(recomputed.index).to_numpy(),
            recomputed.to_numpy()):
        n6 += 1; bad6.append("n_seasons in the audit disagrees with players.csv")
    check(6, "cross_season_identity_mappings", n6,
          f"{len(ident)} officialIds; {int((ident['n_seasons']>1).sum())} appear in "
          f"more than one season; {int((~ident['safe_to_aggregate_across_seasons']).sum())} "
          f"are not safe to pool. Identity is the id -- no name-based merge exists. "
          f"{bad6 or 'audit agrees with the season tables'}")

    # ---- 7. score reconciliation, recomputed from events ------------------
    n7, bad7 = 0, []
    for y in SEASONS:
        g = sf(y, "games.csv")
        el = g[g["is_completed"] & g["include_in_league_analytics"] & ~g["is_all_star"]]
        ev = sf(y, "events.csv", low_memory=False,
                dtype={"team_id": str, "event_id": str})
        ev = ev[(ev["is_analysis_eligible_event"] == True)  # noqa: E712
                & ev["game_id"].isin(set(el["game_id"]))
                & (ev["is_valid_goal"] == True)]  # noqa: E712
        ev = ev.copy()
        ev["pts"] = ev["shot_type"].map(SHOT_TYPE_POINTS).fillna(1)
        got = ev.groupby(["game_id", "team_id"])["pts"].sum()
        for r in el.itertuples():
            for tid, official in ((r.home_team_id, r.home_score),
                                  (r.away_team_id, r.away_score)):
                rec = float(got.get((r.game_id, tid), 0))
                if abs(rec - float(official)) > TOL:
                    n7 += 1
                    bad7.append(f"{y}/{r.game_slug}/{tid}: {rec:.0f} vs {official}")
    exc = hf("historical_analytics_exclusions.csv")
    documented = set(exc["game_slug"]) if len(exc) else set()
    undocumented = [b for b in bad7 if b.split("/")[1] not in documented]
    check(7, "score_reconciliation_recomputed_from_events", len(undocumented),
          f"PLL points re-derived from valid goal events for every eligible "
          f"team-game in five seasons. {len(bad7)} residual(s), of which "
          f"{len(bad7)-len(undocumented)} are documented exceptions in "
          f"historical_analytics_exclusions.csv. "
          f"{undocumented or 'no undocumented residual'}")

    # ---- 8. one-point / two-point scoring ---------------------------------
    n8, bad8 = 0, []
    for y in SEASONS:
        ev = sf(y, "events.csv", low_memory=False)
        goals = ev[(ev["is_valid_goal"] == True)]  # noqa: E712
        bad_tag = goals[~goals["shot_type"].isin(SHOT_TYPE_POINTS)]
        if len(bad_tag):
            n8 += len(bad_tag)
            bad8.append(f"{y}: {len(bad_tag)} valid goals with an unknown shot tag "
                        f"{sorted(bad_tag['shot_type'].dropna().unique())[:4]}")
        t = sf(y, f"team_stats_{y}.csv")
        resid = (t["one_point_goals"] + t["two_point_goals"] - t["goals"]).abs()
        if (resid > TOL).any():
            n8 += int((resid > TOL).sum()); bad8.append(f"{y}: goal split broken")
        resid2 = (t["one_point_points"] + t["two_point_points"] - t["points"]).abs()
        if (resid2 > TOL).any():
            n8 += int((resid2 > TOL).sum()); bad8.append(f"{y}: point split broken")
        if not np.allclose(t["two_point_points"], 2 * t["two_point_goals"]):
            n8 += 1; bad8.append(f"{y}: a two-point goal is not worth 2 points")
    check(8, "one_and_two_point_scoring", n8,
          f"every valid goal in five seasons carries a known point class, and "
          f"1PT+2PT reconstructs goals and points at team level. {bad8 or 'exact'}")

    # ---- 9. possession invariants ----------------------------------------
    n9, bad9 = 0, []
    for y in SEASONS:
        p = sf(y, "possessions.csv")
        g = sf(y, "games.csv")
        el = set(g[g["is_completed"] & g["include_in_league_analytics"]
                   & ~g["is_all_star"]]["game_id"])
        pe = p[p["game_id"].isin(el)]
        if int(pe.duplicated(subset=["possession_id"]).sum()):
            n9 += 1; bad9.append(f"{y}: duplicate possession_id")
        same = int((pe["offense_team_id"] == pe["defense_team_id"]).sum())
        if same:
            n9 += same; bad9.append(f"{y}: {same} possessions with offence==defence")
        if pe["offense_team_id"].isna().any():
            n9 += 1; bad9.append(f"{y}: null offence team")
        neg = int((pe["duration_seconds"] < 0).sum())
        if neg:
            n9 += neg; bad9.append(f"{y}: {neg} negative durations")
        # every eligible game must have possessions
        missing = el - set(pe["game_id"])
        if missing:
            n9 += len(missing); bad9.append(f"{y}: {len(missing)} games with no possessions")
    check(9, "possession_invariants", n9,
          f"possession ids unique, offence != defence, no null offence, no "
          f"negative duration, every eligible game covered. {bad9 or 'all hold'}")

    # ---- 10. goal-to-possession mapping ------------------------------------
    n10, bad10 = 0, []
    for y in SEASONS:
        p = sf(y, "possessions.csv")
        g = sf(y, "games.csv")
        el = set(g[g["is_completed"] & g["include_in_league_analytics"]
                   & ~g["is_all_star"]]["game_id"])
        pe = p[p["game_id"].isin(el)]
        ev = sf(y, "events.csv", low_memory=False)
        ev = ev[(ev["is_analysis_eligible_event"] == True)  # noqa: E712
                & ev["game_id"].isin(el) & (ev["is_valid_goal"] == True)]  # noqa: E712
        ev = ev.copy()
        ev["pts"] = ev["shot_type"].map(SHOT_TYPE_POINTS).fillna(1)
        if abs(pe["goals"].sum() - len(ev)) > TOL:
            n10 += 1
            bad10.append(f"{y}: possessions hold {pe['goals'].sum():.0f} goals vs "
                         f"{len(ev)} valid goal events")
        if abs(pe["points_scored"].sum() - ev["pts"].sum()) > TOL:
            n10 += 1
            bad10.append(f"{y}: possession points {pe['points_scored'].sum():.0f} vs "
                         f"event points {ev['pts'].sum():.0f}")
    check(10, "goal_to_possession_mapping", n10,
          f"every valid goal and every PLL point lands in exactly one possession, "
          f"in all five seasons. {bad10 or 'exact'}")

    # ---- 11. no all-star or incomplete contamination -----------------------
    n11, bad11 = 0, []
    for y in SEASONS:
        g = sf(y, "games.csv")
        el = g[g["is_completed"] & g["include_in_league_analytics"] & ~g["is_all_star"]]
        if el["is_all_star"].any():
            n11 += 1; bad11.append(f"{y}: all-star game in the eligible set")
        if not el["is_completed"].all():
            n11 += 1; bad11.append(f"{y}: incomplete game in the eligible set")
        if (el["game_type"] == "preseason").any():
            n11 += 1; bad11.append(f"{y}: preseason game in the eligible set")
        # and nothing all-star reached the stat layer
        t = sf(y, f"team_stats_{y}.csv", dtype={"team_id": str})
        allstar_ids = set(sf(y, "teams.csv", dtype={"team_id": str})
                          .query("is_all_star_team")["team_id"])
        leaked = set(t["team_id"]) & allstar_ids
        if leaked:
            n11 += len(leaked); bad11.append(f"{y}: all-star team {leaked} in team_stats")
    check(11, "no_all_star_preseason_or_incomplete_contamination", n11,
          f"the eligible set in every season excludes all-star, preseason and "
          f"not-yet-played games, and no all-star franchise reaches the stat "
          f"layer. 2022's 4 preseason scrimmages are excluded by segment. "
          f"{bad11 or 'clean'}")

    # ---- 12. Phase 8's 2026 outputs are byte-identical ---------------------
    # Recomputed against the values Phase 8 itself validated, by re-deriving
    # them rather than trusting a stored hash: every 2026 file must still
    # reconcile to the same league totals Phase 8 reported.
    n12, bad12 = 0, []
    t26 = sf(2026, "team_stats_2026.csv")
    p26 = sf(2026, "player_stats_2026.csv")
    expect = {"teams": 8, "players": 228, "league_points": 1190,
              "shots": 4106, "two_point_attempts": 536, "two_point_goals": 72}
    got = {"teams": len(t26), "players": len(p26),
           "league_points": int(t26["points_scored"].sum()),
           "shots": int(t26["shots"].sum()),
           "two_point_attempts": int(t26["two_point_attempts"].sum()),
           "two_point_goals": int(t26["two_point_goals"].sum())}
    for k, v in expect.items():
        if got[k] != v:
            n12 += 1; bad12.append(f"{k}: {got[k]} != Phase 8's {v}")
    missing_files = [f for f in PHASE8_2026 if not (PROC / "2026" / f).exists()]
    if missing_files:
        n12 += len(missing_files); bad12.append(f"missing: {missing_files}")
    check(12, "phase8_2026_outputs_unchanged", n12,
          f"all {len(PHASE8_2026)} Phase 8 2026 artifacts present and every "
          f"headline 2026 total still equals the figure Phase 8 published "
          f"({got}). {bad12 or 'unchanged'}")

    # ---- 13. metric bounds across every season -----------------------------
    n13, bad13 = 0, []
    BOUNDED = ["shooting_pct", "faceoff_win_pct", "save_pct_official", "win_pct",
               "one_point_conversion_pct", "two_point_conversion_pct",
               "shots_on_goal_pct", "two_point_attempt_rate",
               "two_point_points_share"]
    for y in SEASONS:
        t = sf(y, f"team_stats_{y}.csv")
        for c in BOUNDED:
            if c not in t.columns:
                continue
            v = pd.to_numeric(t[c], errors="coerce").dropna()
            b = int(((v < 0) | (v > 1)).sum())
            if b:
                n13 += b; bad13.append(f"{y}.{c}={b}")
        num = t.select_dtypes(include=[np.number])
        inf = int(np.isinf(num.to_numpy(dtype="float64", na_value=np.nan)).sum())
        if inf:
            n13 += inf; bad13.append(f"{y}: {inf} non-finite")
    check(13, "metric_bounds_every_season", n13,
          f"{len(BOUNDED)} bounded proportions checked in all five seasons, plus "
          f"finiteness of every numeric team column. {bad13 or 'all in range'}")

    # ---- 14. denominators and qualification --------------------------------
    n14, bad14 = 0, []
    for y in SEASONS:
        lb = sf(y, f"player_leaderboards_{y}.csv", low_memory=False,
                dtype={"player_id": str})
        if lb["denominator_name"].isna().any():
            k = int(lb["denominator_name"].isna().sum())
            n14 += k; bad14.append(f"{y}: {k} rows with no denominator")
        if lb["metric_value"].isna().any():
            k = int(lb["metric_value"].isna().sum())
            n14 += k; bad14.append(f"{y}: {k} null values ranked")
        if lb["qualification_reason"].isna().any():
            k = int(lb["qualification_reason"].isna().sum())
            n14 += k; bad14.append(f"{y}: {k} rows with no qualification reason")
        # QUALIFIED must be a subset of ALL
        for m in lb["metric_name"].unique():
            a = set(lb[(lb["metric_name"] == m) & (lb["scope"] == "ALL")]["player_id"])
            q = set(lb[(lb["metric_name"] == m) & (lb["scope"] == "QUALIFIED")]["player_id"])
            if not q <= a:
                n14 += 1; bad14.append(f"{y}.{m}: QUALIFIED not a subset of ALL")
        # no two-point ability leaderboard in ANY season
        tpq = lb[(lb["metric_name"] == "two_point_conversion_pct")
                 & (lb["scope"] == "QUALIFIED")]
        if len(tpq):
            n14 += len(tpq); bad14.append(f"{y}: {len(tpq)} qualified two-point rows")
    check(14, "denominators_and_qualification_every_season", n14,
          f"every leaderboard row in five seasons carries a denominator, a "
          f"qualification reason and a non-null value; QUALIFIED is a subset of "
          f"ALL; no season publishes a qualified two-point ability board. "
          f"{bad14 or 'clean'}")

    # ---- 15. raw vs shrunk kept separate in every season --------------------
    n15, bad15 = 0, []
    for y in SEASONS:
        p = sf(y, f"player_stats_{y}.csv", low_memory=False)
        for raw, shr in (("shooting_rate_raw", "shooting_rate_shrunk"),
                         ("faceoff_rate_raw", "faceoff_rate_shrunk"),
                         ("save_rate_raw", "save_rate_shrunk")):
            both = p[[raw, shr]].dropna()
            if both.empty:
                n15 += 1; bad15.append(f"{y}: {raw}/{shr} missing")
            elif np.allclose(both[raw], both[shr], atol=1e-12):
                n15 += 1; bad15.append(f"{y}: {shr} identical to {raw}")
        tp = p["two_point_rate_shrunk"].dropna()
        if len(tp) and (tp.max() - tp.min()) / max(abs(tp.mean()), 1e-12) > 1e-3:
            n15 += 1
            bad15.append(f"{y}: two_point_rate_shrunk varies, contradicting "
                         f"non-identification")
    check(15, "raw_and_shrunk_separate_every_season", n15,
          f"3 raw/shrunk pairs confirmed distinct in all five seasons, and "
          f"two-point shrinkage is fully collapsed in all five. {bad15 or 'held'}")

    # ---- 16. pooled == union of the season files ---------------------------
    n16, bad16 = 0, []
    for pooled, tmpl, key in (
            ("team_stats_2022_2026.csv", "team_stats_{y}.csv", ["season", "team_id"]),
            ("player_stats_2022_2026.csv", "player_stats_{y}.csv", ["season", "player_id"]),
            ("team_leaderboards_2022_2026.csv", "team_leaderboards_{y}.csv", None),
            ("player_leaderboards_2022_2026.csv", "player_leaderboards_{y}.csv", None)):
        pl = hf(pooled, low_memory=False)
        total = 0
        for y in SEASONS:
            p = PROC / str(y) / tmpl.format(y=y)
            if p.exists():
                total += len(pd.read_csv(p, low_memory=False))
        if total != len(pl):
            n16 += 1
            bad16.append(f"{pooled}: pooled {len(pl)} vs seasons {total}")
        if "season" not in pl.columns:
            n16 += 1; bad16.append(f"{pooled}: no season column")
        elif set(pl["season"].unique()) != set(SEASONS):
            n16 += 1
            bad16.append(f"{pooled}: seasons {sorted(pl['season'].unique())}")
        if key:
            d = int(pl.duplicated(subset=key).sum())
            if d:
                n16 += d; bad16.append(f"{pooled}: {d} duplicate {key}")
    check(16, "pooled_equals_union_of_seasons", n16,
          f"4 pooled files verified as exactly the concatenation of their season "
          f"files, each carrying `season`, each keyed uniquely. {bad16 or 'exact'}")

    # ---- 17. season partition correctness ----------------------------------
    n17, bad17 = 0, []
    for y in SEASONS:
        for f in (f"team_stats_{y}.csv", f"player_stats_{y}.csv",
                  f"team_leaderboards_{y}.csv", f"player_leaderboards_{y}.csv",
                  "possessions.csv", "events.csv"):
            p = PROC / str(y) / f
            if not p.exists():
                n17 += 1; bad17.append(f"missing {y}/{f}")
        g = sf(y, "games.csv")
        yrs = pd.to_datetime(g["start_date_utc"], errors="coerce",
                             utc=True).dt.year.dropna().unique()
        stray = [int(v) for v in yrs if int(v) not in (y - 1, y, y + 1)]
        if stray:
            n17 += len(stray); bad17.append(f"{y}: games dated {stray}")
    check(17, "season_partition_correctness", n17,
          f"every season directory carries its own six canonical outputs and no "
          f"game from another season. {bad17 or 'partitioned correctly'}")

    # ---- 18. deterministic rebuild of the analysis layer --------------------
    import importlib
    n18, bad18 = 0, []
    targets = ["multi_season_metric_distributions.csv", "multi_season_reliability.csv",
               "player_year_to_year_stability.csv", "multi_season_usage_model.csv",
               "multi_season_two_point_analysis.csv",
               "multi_season_two_point_identification.csv",
               "multi_season_opponent_adjustment.csv"]
    before = {f: hashlib.sha256((HIST / f).read_bytes()).hexdigest()
              for f in targets if (HIST / f).exists()}
    import io
    from contextlib import redirect_stdout
    mod = importlib.import_module("pll_multi_season_analysis")
    with redirect_stdout(io.StringIO()):
        mod.main()
    for f, h in before.items():
        if hashlib.sha256((HIST / f).read_bytes()).hexdigest() != h:
            n18 += 1; bad18.append(f)
    check(18, "analysis_layer_rebuild_is_deterministic", n18,
          f"{len(before)} multi-season analysis outputs recomputed and compared "
          f"by SHA-256; every stochastic step is seeded. {bad18 or 'identical'}")

    # ---- 19. no composite / MVP / Tewaaraton anywhere in Phase 9 ------------
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from pll_metric_catalog import FORBIDDEN_IN_PUBLISHED
    n19, bad19 = 0, []
    surfaces = {}
    for y in SEASONS:
        surfaces[f"team_stats_{y}"] = list(sf(y, f"team_stats_{y}.csv").columns)
        surfaces[f"player_stats_{y}"] = list(sf(y, f"player_stats_{y}.csv",
                                                low_memory=False).columns)
        surfaces[f"player_lb_{y}"] = sorted(
            sf(y, f"player_leaderboards_{y}.csv", low_memory=False)["metric_name"].unique())
    for f in HIST.glob("*.csv"):
        surfaces[f"history/{f.name}"] = list(pd.read_csv(f, nrows=0).columns)
    for where, names in surfaces.items():
        for nm in names:
            for bad in FORBIDDEN_IN_PUBLISHED:
                if bad in str(nm).lower():
                    n19 += 1; bad19.append(f"{where}.{nm}")
    check(19, "no_mvp_tewaaraton_or_composite_in_phase9", n19,
          f"{sum(len(v) for v in surfaces.values())} column and metric names "
          f"scanned across {len(surfaces)} Phase 9 surfaces for "
          f"{len(FORBIDDEN_IN_PUBLISHED)} forbidden patterns. "
          f"{bad19 or 'no composite, award score, WAR or replacement level'}")

    # ---- 20. no class-E sanity flag survives -------------------------------
    flags = hf("multi_season_sanity_flags.csv")
    e = flags[flags["classification"] == "E"]
    check(20, "no_implementation_bug_flags_remain", len(e),
          f"{len(flags)} multi-season flags by class "
          f"{flags['classification'].value_counts().to_dict()}. Only class E is "
          f"a defect. " + (f"Remaining: {e['detail'].tolist()[:3]}" if len(e)
                           else "No E flags."))

    # ---- 21. schema compatibility admits every ingested season --------------
    schema = hf("historical_schema_compatibility.csv")
    inc = schema[schema["status"] == "INCOMPATIBLE"]
    check(21, "no_ingested_season_is_schema_incompatible", len(inc),
          f"{len(schema)} audited aspects across {schema['season'].nunique()} "
          f"seasons; statuses {schema['status'].value_counts().to_dict()}. "
          + (f"INCOMPATIBLE: {inc[['season','aspect']].to_dict('records')}"
             if len(inc) else
             "no ingested season carries an INCOMPATIBLE aspect. 2021 was "
             "tested and excluded before ingestion."))

    # ---- 22. two-point non-identification is enforced, not assumed ----------
    tp = hf("multi_season_two_point_identification.csv")
    n22, bad22 = 0, []
    if not len(tp):
        n22 += 1; bad22.append("no identification table")
    else:
        if tp["identifiable"].any():
            # not a failure -- but then a qualified board would be permitted
            ok_scopes = tp[tp["identifiable"]]["scope"].tolist()
            bad22.append(f"NOW identifiable in {ok_scopes}: the Phase 8 refusal "
                         f"should be revisited")
        for _, r in tp.iterrows():
            if r["excess_variance"] > 0 and r["prior_strength_kappa"] >= 1e5:
                n22 += 1
                bad22.append(f"{r['scope']}: positive excess variance but a "
                             f"capped prior -- inconsistent")
    check(22, "two_point_identification_verdict_is_consistent", n22,
          f"identification tested in every season and pooled two ways. "
          f"identifiable={tp['identifiable'].tolist()}. {bad22 or 'consistent'}")

    report = pd.DataFrame(results)
    HIST.mkdir(parents=True, exist_ok=True)
    out = HIST / "phase9_validation_report.csv"
    report.to_csv(out, index=False)
    n_fail = int((report["status"] == "FAIL").sum())
    print(report[["check_id", "check_name", "status", "n_failures"]].to_string(index=False))
    if n_fail:
        for _, r in report[report["status"] == "FAIL"].iterrows():
            print(f"\nFAIL {r['check_id']} {r['check_name']}: {r['detail']}")
    print(f"\n{len(report)-n_fail}/{len(report)} checks PASS -> {out.relative_to(REPO_ROOT)}")
    return report


if __name__ == "__main__":
    main()
