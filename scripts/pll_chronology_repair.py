"""
Phase 11 part B: canonicalizing the Phase 10 faceoff-chronology repair.

Phase 10 (`pll_phase10_possession_repair.py`, `docs/2023_POSSESSION_REPAIR.md`)
found that in 2023 (and, to a much smaller degree, 2024) the raw feed emits
the faceoff that FOLLOWS a goal BEFORE that goal in `items` array order, and
stamps it with the goal's own clock. It classified every candidate sequence
into an evidence scale (DIRECT / DIRECT_TIMING / STRONGLY_INFERRED /
DUPLICATE_FACEOFF_EVENT / WEAKLY_INFERRED / UNRESOLVED) and published a
REPAIRED possession layer alongside the frozen one (`possessions_repaired.csv`)
without touching canonical `events.csv`/`possessions.csv`, deliberately
leaving adoption to a later phase (`2023_POSSESSION_REPAIR.md` Section 8,
"Recommendation: adopt V2_direct_and_timing into the canonical layer in
Phase 11").

This module IS that adoption. It does not re-derive the classification rule
-- `detect_faceoff_order_defects` is imported from
`pll_phase10_possession_repair.py` unchanged, exactly as that module itself
imports (rather than reimplements) the Phase 4 possession state machine. Only
DIRECT and DIRECT_TIMING are applied here, matching Phase 10's own primary
variant (V2_direct_and_timing) and its stated reasoning: those two classes are
OBSERVED (uniquely implied by the feed's own markerId + companion-ground-ball
fields), while STRONGLY_INFERRED is INFERRED (direction argued, not proven)
and is deliberately left unrepaired in the canonical layer.

WHERE THIS RUNS
    `pll_build_tables.build_events_table` calls `repair_game_chronology` on
    each game's own cleaned event frame (`clean(df)` output), before that
    game's `is_analysis_eligible_event` is computed -- this is the earliest
    point in the canonical pipeline that has everything the classification
    needs (`is_valid_goal`, `gb_player_id`, ...) and it is upstream of every
    consumer (possession reconstruction, Phase 5-10 stat layers), so they all
    receive the corrected order/timestamps without needing to know a repair
    happened. All classification is single-game -- no faceoff/goal pairing
    ever spans a game boundary -- so per-game application is not a narrowing
    of the original multi-game detector, only a restriction to how it is
    invoked.

PROVENANCE (never silently overwrite; the original is always recoverable)
    event_number_raw, seconds_passed_raw   the feed's own values, untouched
    chronology_evidence_class              DIRECT / DIRECT_TIMING /
                                            STRONGLY_INFERRED / WEAKLY_INFERRED
                                            / DUPLICATE_FACEOFF_EVENT /
                                            UNRESOLVED / null (not a candidate)
    chronology_repair_applied              True only for DIRECT/DIRECT_TIMING
                                            rows whose event_number/
                                            seconds_passed were changed
    chronology_repair_rule_version         RULE_VERSION below

    `event_number`/`seconds_passed` themselves become the corrected values on
    applied rows; every other row is untouched, so a season with zero
    candidates (2022, 2025, and all but one sequence of 2026) is byte-for-byte
    identical to its Phase 1-9 output except for the five new all-null/
    all-False provenance columns.

    A DUPLICATE_FACEOFF_EVENT row (the mis-stamped extra copy Phase 10 found
    dominates 2024, see `pll_duplicate_faceoff.py`) is never touched by this
    module -- deduplication is a distinct canonical-event-layer change, kept
    in its own module with its own validated rule and audit trail.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The evidence classification is imported, never reimplemented -- see module
# docstring. Only DIRECT/DIRECT_TIMING are applied here; the function itself
# still reports every other class so they remain visible in the audit trail.
from pll_phase10_possession_repair import detect_faceoff_order_defects  # noqa: E402

RULE_VERSION = "phase11_chronology_v1"
REPAIR_CLASSES = frozenset({"DIRECT", "DIRECT_TIMING"})

PROVENANCE_COLUMNS = [
    "event_number_raw", "seconds_passed_raw",
    "chronology_evidence_class", "chronology_repair_applied",
    "chronology_repair_rule_version",
]


def repair_game_chronology(df: pd.DataFrame) -> pd.DataFrame:
    """Classify and repair one game's cleaned event frame.

    `df` must be a single game's output of `pll_pbp_clean.clean()` (it needs
    game_id, game_slug, event_id, event_type, event_number, seconds_passed,
    period, team_id, player_id, secondary_player_id, gb_player_id,
    is_valid_goal). Returns a copy with the columns documented above added,
    and event_number/seconds_passed corrected on DIRECT/DIRECT_TIMING rows.
    """
    df = df.reset_index(drop=True).copy()
    df["event_number_raw"] = df["event_number"]
    df["seconds_passed_raw"] = df["seconds_passed"]
    df["chronology_evidence_class"] = pd.array([None] * len(df), dtype="object")
    df["chronology_repair_applied"] = False
    df["chronology_repair_rule_version"] = RULE_VERSION

    det = detect_faceoff_order_defects(df)
    if len(det) == 0:
        return df

    for r in det.itertuples():
        df.at[int(r.faceoff_array_index), "chronology_evidence_class"] = r.evidence_class

    # Transpose/retime, applied in array-index order exactly as
    # `pll_phase10_possession_repair.apply_repair` does. Reimplemented inline
    # (rather than calling apply_repair and merging its output back) only
    # because apply_repair re-sorts its return frame by event_number, which
    # would discard the positional alignment this function needs to also
    # stamp chronology_repair_applied; the two transpose/retime operations
    # themselves are copied verbatim.
    numbers = df["event_number"].to_numpy(dtype=float).copy()
    secs = df["seconds_passed"].to_numpy(dtype=float).copy()
    for r in det.itertuples():
        if r.evidence_class not in REPAIR_CLASSES:
            continue
        i = int(r.faceoff_array_index)
        if r.repair_action in ("transpose_and_retime", "transpose_only"):
            j = int(r.goal_array_index)
            numbers[i], numbers[j] = numbers[j], numbers[i]
        if r.repair_action in ("transpose_and_retime", "retime_only"):
            secs[i] = float(r.companion_gb_seconds_passed)
        df.at[i, "chronology_repair_applied"] = True
    df["event_number"] = numbers.astype(df["event_number_raw"].dtype)
    df["seconds_passed"] = secs.astype(df["seconds_passed_raw"].dtype)

    # A repaired game is re-sorted into its corrected processing order. No
    # repair may ever produce two events sharing an event_number (the
    # transpose is a pure swap of two existing values) or a negative
    # possession later on -- both are asserted in tests/test_chronology_repair.py
    # and in pll_validate_phase11.py, not silently trusted here.
    return df.sort_values("event_number").reset_index(drop=True)
