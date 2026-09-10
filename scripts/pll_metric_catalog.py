"""
Phase 8: the canonical metric catalog -- single import point.

The catalog rows live in three sibling modules so no single file becomes
unreviewable:

    pll_phase8_catalog_core.py     schema, row constructor, shared caveat text
    pll_phase8_catalog_team.py     team-level rows
    pll_phase8_catalog_player.py   player-level rows + rejected/deferred concepts

This module assembles them, enforces the invariants that make the catalog usable
as data (unique names, closed vocabularies, no silently missing caveat), and is
the ONLY thing the build script and the tests import.

Assembly-time invariants, all of which raise rather than warn:
  * (entity_level, metric_name) is unique -- `games_played` legitimately exists
    at both team and player level and means the same thing in each, so the key
    is the pair rather than the name alone;
  * every column in CATALOG_COLUMNS is present on every row;
  * publication_status, freeze_classification, entity_level and
    higher_is_better are drawn from closed vocabularies;
  * no row is both CORE and DO_NOT_USE;
  * every UNSUPPORTED/DEFERRED row states what is missing (a non-trivial
    known_limitations string), because an unsupported metric with no reason is
    indistinguishable from an oversight;
  * a redundancy_class of IDENTICAL(x) or ALGEBRAICALLY_REDUNDANT names a
    metric that exists -- IDENTICAL(x) must point at a catalogued x.
"""
import re

from pll_phase8_catalog_core import CATALOG_COLUMNS
from pll_phase8_catalog_team import TEAM_METRICS
from pll_phase8_catalog_player import PLAYER_METRICS, REJECTED_METRICS

PUBLICATION_STATUSES = {
    "CORE", "CONTEXTUAL", "EXPERIMENTAL", "DIAGNOSTIC", "DEFERRED", "UNSUPPORTED",
}
FREEZE_CLASSIFICATIONS = {
    "FREEZE", "FREEZE_WITH_CAVEAT", "REVISE_BEFORE_HISTORICAL", "DO_NOT_USE",
}
ENTITY_LEVELS = {
    "team_season", "team_game", "player_season", "player_game", "league",
    # Rejected/deferred concepts that would have applied at both levels are
    # catalogued once rather than twice, so the reason is written once.
    "team_and_player",
}
DIRECTIONS = {"TRUE", "FALSE", "neither"}

# Substrings that must never appear in a metric_name that is published. The
# Phase 8 brief forbids the composite; the catalog documents WHY the composite
# was not built, so the forbidden names appear as UNSUPPORTED rows and nowhere
# else.
FORBIDDEN_IN_PUBLISHED = (
    "tewaaraton", "mvp", "war_", "wins_above", "replacement_level",
    "composite_score", "award_score", "overall_rating",
)

CATALOG = TEAM_METRICS + PLAYER_METRICS + REJECTED_METRICS


def _validate(rows):
    seen = {}
    for i, r in enumerate(rows):
        name = r.get("metric_name")
        where = f"row {i} ({name!r})"
        missing = [c for c in CATALOG_COLUMNS if c not in r]
        if missing:
            raise ValueError(f"{where}: missing catalog columns {missing}")
        extra = [c for c in r if c not in CATALOG_COLUMNS]
        if extra:
            raise ValueError(f"{where}: unknown catalog columns {extra}")
        key = (r["entity_level"], name)
        if key in seen:
            raise ValueError(f"duplicate metric {key} (also row {seen[key]})")
        seen[key] = i

        if r["publication_status"] not in PUBLICATION_STATUSES:
            raise ValueError(f"{where}: bad publication_status {r['publication_status']!r}")
        if r["freeze_classification"] not in FREEZE_CLASSIFICATIONS:
            raise ValueError(f"{where}: bad freeze_classification {r['freeze_classification']!r}")
        if r["entity_level"] not in ENTITY_LEVELS:
            raise ValueError(f"{where}: bad entity_level {r['entity_level']!r}")
        if str(r["higher_is_better"]) not in DIRECTIONS:
            raise ValueError(f"{where}: bad higher_is_better {r['higher_is_better']!r}")

        if r["publication_status"] == "CORE" and r["freeze_classification"] == "DO_NOT_USE":
            raise ValueError(f"{where}: CORE metric classified DO_NOT_USE")
        if r["publication_status"] in ("UNSUPPORTED", "DEFERRED") and \
                len(r["known_limitations"]) < 60:
            raise ValueError(
                f"{where}: {r['publication_status']} without a stated reason -- "
                "an unsupported metric with no reason is indistinguishable from "
                "an oversight")
        if r["publication_status"] != "UNSUPPORTED":
            low = name.lower()
            for bad in FORBIDDEN_IN_PUBLISHED:
                if bad in low:
                    raise ValueError(
                        f"{where}: name contains {bad!r} but is not UNSUPPORTED. "
                        "Phase 8 forbids composite/award/replacement-level metrics.")

    for r in rows:
        m = re.fullmatch(r"IDENTICAL\((.+)\)", r["redundancy_class"])
        if m and (r["entity_level"], m.group(1)) not in seen:
            raise ValueError(
                f"{r['metric_name']}: redundancy_class points at {m.group(1)!r}, "
                "which is not in the catalog at this entity level")
    return rows


_validate(CATALOG)


def catalog_rows():
    """The full catalog, deterministically ordered.

    Ordering is (entity_level, category, metric_name) rather than insertion
    order so the exported CSV is stable under edits to the source modules.
    """
    return sorted(CATALOG, key=lambda r: (r["entity_level"], r["category"],
                                          r["metric_name"]))


def by_status(status):
    return [r for r in CATALOG if r["publication_status"] == status]


def published_names():
    """Metric names a consumer is allowed to publish, in any form."""
    return {r["metric_name"] for r in CATALOG
            if r["publication_status"] in ("CORE", "CONTEXTUAL", "EXPERIMENTAL")}


CATALOG_BY_KEY = {(r["entity_level"], r["metric_name"]): r for r in CATALOG}
