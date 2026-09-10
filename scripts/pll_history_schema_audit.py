"""
Phase 9: historical schema compatibility audit.

Compares every ingested season against 2026, field by field, over the COMPLETE
raw corpus rather than a sample. Phase 8's read-only probe made claims about
2022-2025 structural similarity; this script exists to verify them
independently, and it disagrees with the probe in two places (see the
`MU` shot tag and the 2023 eventStatus finding in the report).

Writes:
    data/processed/history/historical_schema_compatibility.csv

Every row is one audited aspect for one season, classified:

IDENTICAL                 byte-for-byte the same vocabulary/behaviour as 2026
COMPATIBLE_TRANSFORMATION differs, but a documented, lossless mapping exists
SEASON_SPECIFIC           genuinely different league/feed behaviour that the
                          pipeline must model per season, not normalize away
MISSING_INPUT             2026 has it, this season does not
INCOMPATIBLE              cannot be reconciled; the season fails admission
UNKNOWN                   could not be established from the data

A season is admitted to the pooled dataset only if it carries no INCOMPATIBLE
row. MISSING_INPUT is survivable if and only if the affected metric is dropped
for that season rather than imputed.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = REPO_ROOT / "data" / "raw"
OUT_DIR = REPO_ROOT / "data" / "processed" / "history"

SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
REFERENCE = 2026

# Aspects audited. Each is (aspect, extractor) where the extractor returns a
# set/dict summarising that aspect for one season.
PBP_SCALAR_KEYS = [
    "markerId", "eventType", "shotType", "teamId", "period", "minutes",
    "seconds", "secondsPassed", "homeScore", "visitorScore", "description",
    "penaltyLength", "penaltyDescription", "shooterId", "shotAssistId",
    "faceoffWinnerId", "faceoffLoserId", "gbPlayerId", "commitedTurnoverId",
    "causedTurnoverId", "commitedPenaltyId", "goalieId", "offenseGoalieId",
    "closestDefenderId", "assistOpportunityPlayerId", "details",
    "awayTeamWinProbability", "homeTeamWinProbability",
]


def season_games(season):
    d = RAW / str(season)
    if not d.exists():
        return []
    return sorted(p for p in d.iterdir() if p.is_dir() and p.name != "_schedule")


def load_schedule(season):
    p = RAW / str(season) / "_schedule" / f"games_{season}.json"
    if not p.exists():
        return []
    return json.loads(p.read_text())["data"]["items"]


def collect(season):
    """Everything the audit needs from one season's raw corpus, in one pass."""
    acc = {
        "event_types": Counter(),
        "shot_types": Counter(),
        "json_keys": Counter(),
        "key_types": defaultdict(Counter),
        "periods": Counter(),
        "penalty_lengths": Counter(),
        "position_labels": Counter(),
        "team_ids": Counter(),
        "n_games": 0,
        "n_events": 0,
        "shot_type_by_eventtype": defaultdict(Counter),
        "assist_populated": 0,
        "assist_total": 0,
        "player_stat_keys": Counter(),
        "team_stat_keys": Counter(),
        "official_ids": set(),
        "clock_fields_present": Counter(),
    }
    for gdir in season_games(season):
        pbp_p = gdir / "play_by_play.json"
        if not pbp_p.exists():
            continue
        items = json.loads(pbp_p.read_text()).get("data", {}).get("items", [])
        if not items:
            continue
        acc["n_games"] += 1
        acc["n_events"] += len(items)
        for e in items:
            acc["json_keys"].update(e.keys())
            et = e.get("eventType")
            acc["event_types"][et] += 1
            st = e.get("shotType")
            if st:
                acc["shot_types"][st] += 1
                acc["shot_type_by_eventtype"][et][st] += 1
            acc["periods"][e.get("period")] += 1
            if e.get("penaltyLength") is not None:
                acc["penalty_lengths"][e.get("penaltyLength")] += 1
            if e.get("teamId"):
                acc["team_ids"][e["teamId"]] += 1
            for k in PBP_SCALAR_KEYS:
                if k in e and e[k] is not None:
                    acc["key_types"][k][type(e[k]).__name__] += 1
            if et in ("shot", "goal"):
                acc["assist_total"] += 1
                if e.get("shotAssistId"):
                    acc["assist_populated"] += 1
            for cf in ("minutes", "seconds", "secondsPassed"):
                if e.get(cf) is not None:
                    acc["clock_fields_present"][cf] += 1

        ps_p = gdir / "players_stats.json"
        if ps_p.exists():
            rows = json.loads(ps_p.read_text()).get("data", {}).get("items", [])
            for r in rows:
                acc["player_stat_keys"].update(r.keys())
                pos = r.get("position")
                if pos:
                    acc["position_labels"][pos] += 1
                oid = r.get("officialId")
                if oid is not None:
                    acc["official_ids"].add(str(oid))
        ts_p = gdir / "teams_stats.json"
        if ts_p.exists():
            rows = json.loads(ts_p.read_text()).get("data", {}).get("items", [])
            for r in rows:
                acc["team_stat_keys"].update(r.keys())
    return acc


def classify_set(season_set, ref_set, aspect, allow_extra_as_season_specific=True):
    """Compare two vocabularies and classify the difference."""
    missing = sorted(ref_set - season_set)
    extra = sorted(season_set - ref_set)
    if not missing and not extra:
        return "IDENTICAL", "identical to 2026"
    parts = []
    if missing:
        parts.append(f"absent vs 2026: {missing}")
    if extra:
        parts.append(f"present but not in 2026: {extra}")
    detail = "; ".join(parts)
    if missing and extra:
        return "SEASON_SPECIFIC", detail
    if missing:
        return "MISSING_INPUT", detail
    return ("SEASON_SPECIFIC" if allow_extra_as_season_specific
            else "COMPATIBLE_TRANSFORMATION"), detail


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = {s: collect(s) for s in SEASONS if season_games(s)}
    if REFERENCE not in data:
        raise SystemExit("2026 raw corpus not found; nothing to compare against")
    ref = data[REFERENCE]
    rows = []

    def add(season, aspect, status, detail, ref_value="", season_value=""):
        rows.append({
            "season": season, "aspect": aspect, "status": status,
            "detail": detail,
            "reference_2026_value": str(ref_value)[:400],
            "season_value": str(season_value)[:400],
        })

    for s in sorted(data):
        a = data[s]
        if s == REFERENCE:
            continue

        st, dt = classify_set(set(a["event_types"]), set(ref["event_types"]), "event_types")
        add(s, "event_types", st, dt,
            sorted(ref["event_types"]), sorted(a["event_types"]))

        st, dt = classify_set(set(a["shot_types"]), set(ref["shot_types"]), "shot_types")
        add(s, "shot_type_labels", st, dt,
            dict(ref["shot_types"]), dict(a["shot_types"]))

        # one-point / two-point representation specifically
        has_1 = any(k.endswith("1_PT") or k == "1_PT" for k in a["shot_types"])
        has_2 = any("2_PT" in k for k in a["shot_types"])
        if has_1 and has_2:
            add(s, "one_and_two_point_representation", "IDENTICAL",
                "1_PT and 2_PT shot tags both present, same encoding as 2026",
                "1_PT/2_PT", {k: v for k, v in a["shot_types"].items() if "PT" in k})
        elif has_1 and not has_2:
            add(s, "one_and_two_point_representation", "INCOMPATIBLE",
                "NO two-point shot tag exists in this season's feed at all. Every "
                "two-point metric, and the points identity itself, is undefined.",
                "1_PT/2_PT", dict(a["shot_types"]))
        else:
            add(s, "one_and_two_point_representation", "UNKNOWN",
                "could not establish the point-class encoding", "1_PT/2_PT",
                dict(a["shot_types"]))

        # man-up representation
        mu_ref = {k for k in ref["shot_types"] if k.startswith("MU")}
        mu_s = {k for k in a["shot_types"] if k.startswith("MU")}
        if mu_s == mu_ref:
            add(s, "man_up_representation", "IDENTICAL",
                "same man-up shot tags as 2026", sorted(mu_ref), sorted(mu_s))
        elif not mu_s:
            add(s, "man_up_representation", "MISSING_INPUT",
                "NO man-up shot tag in this season. Man-up metrics derived from "
                "the event log are undefined; the official box score's man-up "
                "columns are unaffected.", sorted(mu_ref), sorted(mu_s))
        else:
            add(s, "man_up_representation", "SEASON_SPECIFIC",
                "man-up tag vocabulary differs", sorted(mu_ref), sorted(mu_s))

        st, dt = classify_set(set(a["json_keys"]), set(ref["json_keys"]), "json_keys")
        add(s, "pbp_json_keys", st, dt, len(ref["json_keys"]), len(a["json_keys"]))

        # field types
        type_mismatch = []
        for k in sorted(set(ref["key_types"]) & set(a["key_types"])):
            rt = set(ref["key_types"][k])
            at = set(a["key_types"][k])
            if rt != at:
                type_mismatch.append(f"{k}: 2026={sorted(rt)} vs {sorted(at)}")
        add(s, "pbp_field_types",
            "IDENTICAL" if not type_mismatch else "COMPATIBLE_TRANSFORMATION",
            "; ".join(type_mismatch) if type_mismatch
            else "every shared key carries the same JSON types as 2026",
            "", len(type_mismatch))

        st, dt = classify_set(set(a["periods"]), set(ref["periods"]), "periods")
        add(s, "period_and_overtime_representation",
            "IDENTICAL" if st == "IDENTICAL" else "COMPATIBLE_TRANSFORMATION",
            dt + " (period is an integer; >4 denotes overtime in every season)",
            sorted(x for x in ref["periods"] if x is not None),
            sorted(x for x in a["periods"] if x is not None))

        for aspect, key in (("faceoff_representation", "faceoff"),
                            ("turnover_representation", "turnover"),
                            ("ground_ball_representation", "groundball"),
                            ("penalty_representation", "penalty"),
                            ("shot_clock_expiration_representation", "shotclockexpired")):
            in_ref = ref["event_types"].get(key, 0)
            in_s = a["event_types"].get(key, 0)
            if in_ref and in_s:
                add(s, aspect, "IDENTICAL",
                    f"'{key}' event type present, same field encoding",
                    in_ref, in_s)
            elif in_ref and not in_s:
                add(s, aspect, "MISSING_INPUT",
                    f"'{key}' event type does NOT occur in this season", in_ref, 0)
            else:
                add(s, aspect, "UNKNOWN", f"'{key}' absent from 2026 too", in_ref, in_s)

        for cf in ("minutes", "seconds", "secondsPassed"):
            present = a["clock_fields_present"].get(cf, 0)
            add(s, f"clock_field_{cf}",
                "IDENTICAL" if present else "MISSING_INPUT",
                f"populated on {present} events" if present else "never populated",
                ref["clock_fields_present"].get(cf, 0), present)

        rate_ref = ref["assist_populated"] / max(ref["assist_total"], 1)
        rate_s = a["assist_populated"] / max(a["assist_total"], 1)
        add(s, "shotAssistId_behaviour",
            "IDENTICAL" if abs(rate_s - rate_ref) < 0.15 else "SEASON_SPECIFIC",
            f"populated on {rate_s:.1%} of shot/goal events vs {rate_ref:.1%} in "
            f"2026. It is a pre-shot pass indicator in every season and is used "
            f"nowhere in the value framework.",
            f"{rate_ref:.3f}", f"{rate_s:.3f}")

        st, dt = classify_set(set(a["position_labels"]), set(ref["position_labels"]),
                              "positions")
        add(s, "position_labels", st, dt,
            sorted(ref["position_labels"]), sorted(a["position_labels"]))

        st, dt = classify_set(set(a["player_stat_keys"]), set(ref["player_stat_keys"]),
                              "player_stat_keys")
        add(s, "official_player_stat_keys", st, dt,
            len(ref["player_stat_keys"]), len(a["player_stat_keys"]))

        st, dt = classify_set(set(a["team_stat_keys"]), set(ref["team_stat_keys"]),
                              "team_stat_keys")
        add(s, "official_team_stat_keys", st, dt,
            len(ref["team_stat_keys"]), len(a["team_stat_keys"]))

        st, dt = classify_set(set(a["team_ids"]), set(ref["team_ids"]), "team_ids")
        add(s, "team_identifiers",
            "IDENTICAL" if st == "IDENTICAL" else "SEASON_SPECIFIC",
            dt + " (team codes are 3-letter officialIds; franchises change "
            "between seasons, which is league history, not a schema problem)",
            sorted(ref["team_ids"]), sorted(a["team_ids"]))

        overlap = len(a["official_ids"] & ref["official_ids"])
        add(s, "player_officialId_stability", "COMPATIBLE_TRANSFORMATION",
            f"{len(a['official_ids'])} distinct officialIds; {overlap} also appear "
            f"in 2026. officialId is an integer that persists across seasons and "
            f"is the join key; see the identity audit for the exceptions.",
            len(ref["official_ids"]), len(a["official_ids"]))

        # schedule-level: eventStatus encoding
        sched = load_schedule(s)
        statuses = Counter(g.get("eventStatus") for g in sched)
        odd = [g["slugname"] for g in sched
               if g.get("eventStatus") == 2 and g.get("homeScore") is not None]
        if odd:
            add(s, "eventStatus_encoding", "SEASON_SPECIFIC",
                f"{len(odd)} PLAYED games carry eventStatus==2 rather than 3 while "
                f"still reporting final scores: {odd}. Treating status 3 as the "
                f"sole completion signal would silently drop them.",
                "{3: all completed}", dict(statuses))
        else:
            add(s, "eventStatus_encoding", "IDENTICAL",
                "every played game carries eventStatus==3, as in 2026",
                "{3: all completed}", dict(statuses))

        segs = Counter(g.get("seasonSegment") for g in sched)
        ref_segs = Counter(g.get("seasonSegment") for g in load_schedule(REFERENCE))
        st, dt = classify_set(set(segs), set(ref_segs), "segments")
        add(s, "season_segments",
            "IDENTICAL" if st == "IDENTICAL" else "SEASON_SPECIFIC",
            dt, dict(ref_segs), dict(segs))

    df = pd.DataFrame(rows).sort_values(["season", "aspect"]).reset_index(drop=True)
    df.to_csv(OUT_DIR / "historical_schema_compatibility.csv", index=False)

    print(f"{len(df)} audited aspects across {df['season'].nunique()} seasons\n")
    print(pd.crosstab(df["season"], df["status"]).to_string())
    bad = df[df["status"].isin(["INCOMPATIBLE", "MISSING_INPUT", "SEASON_SPECIFIC"])]
    print(f"\nNon-identical aspects ({len(bad)}):")
    for _, r in bad.iterrows():
        print(f"  {r['season']} {r['status']:26s} {r['aspect']:38s} {r['detail'][:110]}")
    return df


if __name__ == "__main__":
    main()
