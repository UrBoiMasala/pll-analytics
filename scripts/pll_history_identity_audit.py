"""
Phase 9: cross-season player identity and data-integrity audits.

Two audits, both deliberately conservative.

IDENTITY. A player's canonical identity across 2022-2026 is his `officialId`,
which the feed carries on every player-game row and which is stable across
seasons. NOTHING here merges two ids on the strength of a name. Name evidence is
used ONLY in the opposite direction -- to FLAG a pair of ids that might be the
same human, or one id whose name changed -- and every such case is reported for
a person to adjudicate, never silently resolved. A statistic may aggregate
across seasons only where identity is `confirmed`.

INTEGRITY. Duplicates are separated into three kinds that must not be conflated:
  SOURCE_DUPLICATE_EVENT  the feed itself repeats an event. Phase 2's existing
                          duplicate logic handles these; this audit only counts
                          what that logic found, per season, so a historical
                          season with an anomalous rate is visible.
  LOCAL_DUPLICATE_FILE    two identical raw files on disk (a stray copy).
  PIPELINE_DUPLICATION    the same logical row emitted twice by our own code.
                          This is the only kind that is a bug.

Legitimate repeated game actions -- two ground balls by the same player in the
same second, a genuine second faceoff after a violation -- are NOT duplicates
and are not touched.

Writes:
    data/processed/history/historical_player_identity_audit.csv
    data/processed/history/historical_duplicate_audit.csv
"""
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "processed" / "history"
SEASONS = [2022, 2023, 2024, 2025, 2026]


def norm_name(n):
    """Aggressive normalisation, used ONLY to raise a flag for review."""
    if not isinstance(n, str):
        return ""
    n = n.lower().strip()
    n = re.sub(r"[.\-']", "", n)
    n = re.sub(r"\s+(jr|sr|ii|iii|iv)$", "", n)
    return re.sub(r"\s+", " ", n)


def load(year, name, **kw):
    return pd.read_csv(REPO_ROOT / "data" / "processed" / str(year) / name, **kw)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
def identity_audit():
    frames = []
    for y in SEASONS:
        pl = load(y, "players.csv", dtype={"player_id": str, "team_id": str})
        pl["season"] = y
        frames.append(pl)
    allp = pd.concat(frames, ignore_index=True)

    rows = []
    for pid, sub in allp.groupby("player_id"):
        seasons = sorted(sub["season"].unique())
        names = sorted({n for n in sub["name"].dropna().unique()})
        teams = sorted({t for t in sub["team_id"].dropna().unique()})
        positions = sorted({p for p in sub["position"].dropna().unique()})
        gaps = [b for a, b in zip(seasons, seasons[1:]) if b - a > 1]
        rows.append({
            "player_id": pid,
            "canonical_name": sub["name"].dropna().iloc[-1] if sub["name"].notna().any() else None,
            "n_seasons": len(seasons),
            "seasons": ",".join(str(s) for s in seasons),
            "first_season": seasons[0], "last_season": seasons[-1],
            "n_distinct_names": len(names),
            "all_names": " | ".join(names),
            "n_teams": len(teams), "teams": ",".join(teams),
            "changed_team": len(teams) > 1,
            "n_positions": len(positions), "positions": ",".join(positions),
            "changed_position": len(positions) > 1,
            "has_season_gap": bool(gaps),
            "gap_after": ",".join(str(g - 1) for g in gaps),
            "identity_status": "confirmed",
            "identity_note": "single stable officialId across every season it appears in",
            "safe_to_aggregate_across_seasons": True,
        })
    ident = pd.DataFrame(rows)

    # --- flags. None of these change identity; they mark cases for review. ---
    ident["norm_name"] = ident["canonical_name"].map(norm_name)

    # (a) one normalised name, several officialIds -> POSSIBLE split identity
    dup_name = ident[ident["norm_name"] != ""].groupby("norm_name")["player_id"].agg(list)
    split = {n: ids for n, ids in dup_name.items() if len(ids) > 1}
    for n, ids in split.items():
        sub = ident[ident["player_id"].isin(ids)]
        overlap = sub["seasons"].str.split(",").explode()
        concurrent = overlap.duplicated().any()
        for pid in ids:
            i = ident.index[ident["player_id"] == pid][0]
            others = [x for x in ids if x != pid]
            ident.at[i, "identity_status"] = "review_shared_name"
            ident.at[i, "identity_note"] = (
                f"normalised name '{n}' is also carried by officialId(s) {others}. "
                + ("They appear in the SAME season(s), so they are almost certainly "
                   "two different people who share a name -- NOT merged."
                   if concurrent else
                   "They never appear in the same season, so a re-registration "
                   "under a new id is possible. NOT merged on name evidence; "
                   "flagged for adjudication.")
            )
            # a same-season name clash is two people; aggregation stays safe
            ident.at[i, "safe_to_aggregate_across_seasons"] = bool(concurrent)

    # (b) one officialId, several name spellings -> benign, but recorded
    multi = ident["n_distinct_names"] > 1
    ident.loc[multi & (ident["identity_status"] == "confirmed"), "identity_status"] = \
        "confirmed_name_variant"
    ident.loc[multi & (ident["identity_status"] == "confirmed_name_variant"), "identity_note"] = (
        "same officialId carries more than one name spelling across seasons "
        "(formatting, suffix or nickname). Identity is the id, so this is "
        "recorded rather than resolved.")

    ident = ident.drop(columns=["norm_name"])
    return ident.sort_values(["last_season", "player_id"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Integrity
# ---------------------------------------------------------------------------
def duplicate_audit():
    rows = []

    # --- LOCAL_DUPLICATE_FILE: identical raw payloads on disk ---------------
    for y in SEASONS:
        seen = defaultdict(list)
        raw = REPO_ROOT / "data" / "raw" / str(y)
        for p in sorted(raw.rglob("*.json")):
            if "_snapshots" in p.parts:
                continue
            seen[hashlib.sha256(p.read_bytes()).hexdigest()].append(
                str(p.relative_to(REPO_ROOT)))
        dups = {h: v for h, v in seen.items() if len(v) > 1}
        # identical game_meta between two different games is possible and benign
        # only if the payload is genuinely the same file copied; report either way
        rows.append({
            "season": y, "duplicate_class": "LOCAL_DUPLICATE_FILE",
            "scope": "data/raw", "n_found": len(dups),
            "is_defect": bool(dups),
            "detail": ("no two raw files share a payload hash" if not dups
                       else "; ".join(f"{v}" for v in list(dups.values())[:3])),
        })

    for y in SEASONS:
        ev = load(y, "events.csv", low_memory=False,
                  dtype={"event_id": str, "player_id": str, "team_id": str})
        g = load(y, "games.csv")

        # --- SOURCE_DUPLICATE_EVENT: what Phase 2's rules already found -----
        flags = [c for c in ev.columns if c.startswith("is_duplicate_")]
        dup_flags = ev[flags].astype("boolean").fillna(False).astype(bool) if flags else None
        total_flagged = int(dup_flags.any(axis=1).sum()) if flags else 0
        per_kind = {c: int(dup_flags[c].sum()) for c in flags}
        rows.append({
            "season": y, "duplicate_class": "SOURCE_DUPLICATE_EVENT",
            "scope": "events.csv", "n_found": total_flagged,
            "is_defect": False,
            "detail": (f"{total_flagged} of {len(ev)} events "
                       f"({100*total_flagged/max(len(ev),1):.2f}%) flagged by the "
                       f"EXISTING Phase 2 duplicate rules, unchanged: {per_kind}. "
                       f"These are repetitions in the feed, not pipeline errors, "
                       f"and they are flagged rather than deleted."),
        })

        # --- PIPELINE_DUPLICATION: our own code emitting a row twice --------
        dup_ev = int(ev.duplicated(subset=["game_id", "event_id"]).sum())
        rows.append({
            "season": y, "duplicate_class": "PIPELINE_DUPLICATION",
            "scope": "events.csv (game_id,event_id)", "n_found": dup_ev,
            "is_defect": dup_ev > 0,
            "detail": "each source event appears exactly once" if not dup_ev
                      else f"{dup_ev} repeated (game_id,event_id) rows",
        })
        dup_g = int(g.duplicated(subset=["game_id"]).sum())
        dup_slug = int(g.duplicated(subset=["game_slug"]).sum())
        rows.append({
            "season": y, "duplicate_class": "PIPELINE_DUPLICATION",
            "scope": "games.csv (game_id / game_slug)",
            "n_found": dup_g + dup_slug, "is_defect": (dup_g + dup_slug) > 0,
            "detail": "every game appears once" if not (dup_g + dup_slug)
                      else f"{dup_g} duplicate game_id, {dup_slug} duplicate game_slug",
        })
        pgs = load(y, "player_game_stats.csv")
        dup_p = int(pgs.duplicated(subset=["game_id", "officialId"]).sum())
        rows.append({
            "season": y, "duplicate_class": "PIPELINE_DUPLICATION",
            "scope": "player_game_stats.csv (game_id,officialId)",
            "n_found": dup_p, "is_defect": dup_p > 0,
            "detail": "one row per player per game" if not dup_p
                      else f"{dup_p} repeated player-game rows",
        })
        poss = load(y, "possessions.csv")
        dup_ps = int(poss.duplicated(subset=["possession_id"]).sum())
        rows.append({
            "season": y, "duplicate_class": "PIPELINE_DUPLICATION",
            "scope": "possessions.csv (possession_id)",
            "n_found": dup_ps, "is_defect": dup_ps > 0,
            "detail": "possession ids unique" if not dup_ps
                      else f"{dup_ps} repeated possession_id",
        })

        # --- conflicting versions of the same game --------------------------
        snaps = list((REPO_ROOT / "data" / "raw" / str(y)).rglob("_snapshots/*.json"))
        rows.append({
            "season": y, "duplicate_class": "SOURCE_VERSION_CONFLICT",
            "scope": "raw snapshots", "n_found": len(snaps),
            "is_defect": False,
            "detail": ("no endpoint was ever re-fetched with different content"
                       if not snaps else
                       f"{len(snaps)} superseded raw payloads preserved as snapshots"),
        })
    return pd.DataFrame(rows)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ident = identity_audit()
    ident.to_csv(OUT_DIR / "historical_player_identity_audit.csv", index=False)
    dup = duplicate_audit()
    dup.to_csv(OUT_DIR / "historical_duplicate_audit.csv", index=False)

    print(f"PLAYER IDENTITY: {len(ident)} distinct officialIds across 2022-2026")
    print(ident["identity_status"].value_counts().to_string())
    print(f"\n  appear in >1 season : {int((ident['n_seasons'] > 1).sum())}")
    print(f"  changed team        : {int(ident['changed_team'].sum())}")
    print(f"  changed position    : {int(ident['changed_position'].sum())}")
    print(f"  season gap          : {int(ident['has_season_gap'].sum())}")
    print(f"  NOT safe to pool    : {int((~ident['safe_to_aggregate_across_seasons']).sum())}")
    flagged = ident[ident["identity_status"] == "review_shared_name"]
    if len(flagged):
        print("\n  shared-name flags (never auto-merged):")
        for _, r in flagged.iterrows():
            print(f"    {r['player_id']} {r['canonical_name']:26s} seasons={r['seasons']}")
            print(f"      {r['identity_note'][:150]}")

    print("\nDUPLICATE / INTEGRITY AUDIT")
    piv = dup.pivot_table(index="duplicate_class", columns="season",
                          values="n_found", aggfunc="sum")
    print(piv.to_string())
    defects = dup[dup["is_defect"]]
    print(f"\n  rows classed as a DEFECT: {len(defects)}")
    if len(defects):
        print(defects[["season", "duplicate_class", "scope", "n_found", "detail"]]
              .to_string(index=False))
    return ident, dup


if __name__ == "__main__":
    main()
