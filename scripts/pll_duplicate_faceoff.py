"""
Phase 11 part C: the in-stream duplicate-faceoff defect Phase 10 found and
reported but did not repair (`docs/2023_POSSESSION_REPAIR.md` Section 9).

THE DEFECT
    The feed occasionally logs the SAME faceoff twice: once mis-stamped with
    the PRECEDING goal's own clock and placed before that goal in array order
    (exactly the shape of a Phase 10 chronology-order defect -- markerId
    contradicts array order), and once correctly, after the goal, immediately
    followed by its own companion ground-ball recovery. Both copies agree on
    winner (player_id), loser (secondary_player_id), ground-ball recoverer
    (gb_player_id) and team_id.

    This is NOT the same defect as `pll_chronology_repair.py`: that module
    repairs a single real faceoff whose position/timestamp is wrong. Here
    TWO faceoff records exist for what the surrounding evidence (companion
    ground ball, winner/loser identity) shows was ONE real draw. The correct
    action is therefore de-duplication of the phantom copy, not reordering.

WHY THE EXISTING PHASE 3.5 RULE MISSES IT
    `pll_pbp_clean._flag_duplicate_same_type` (the general Phase 3.5
    duplicate detector) requires (a) the two candidate rows to be the
    IMMEDIATELY PRECEDING event of the same type in raw array order -- a
    differently-typed event between them (here, the goal) resets its
    tracking entirely -- and (b) a clock difference of at most 1 second.
    Both conditions are true of the duplicate pairs Phase 3.5 was built to
    catch (turnover/groundball/penalty/faceoff pairs with nothing between
    them), and both are false of this pattern: a goal always intervenes, and
    the two copies' clocks differ by however long the real play between the
    goal and the true faceoff took (observed up to several seconds). Fixing
    this generically means detecting duplicate CONTENT across an intervening
    event, not loosening the clock tolerance or the adjacency rule for every
    event type -- which would risk sweeping in unrelated same-clock events
    elsewhere (see tests/test_duplicate_faceoff.py for the false-positive
    check against every event type, all seasons).

THE RULE (generic; not keyed to any specific game or event ID)
    A faceoff at array index i is the PHANTOM copy of a later faceoff at
    index k (same game) when ALL of:
      1. et[i] == et[k] == "faceoff", i < k
      2. identical team_id, player_id (winner), secondary_player_id (loser)
         and gb_player_id (ground-ball recoverer) -- exact content match,
         nothing merely proximate
      3. the very next event after i is a valid goal at i's own clock
         (goal_next) -- i.e. i carries the goal's timestamp, not its own
      4. markerId(i) > markerId(goal), i.e. the feed's own monotone sequence
         number puts i AFTER the goal even though array order puts it
         before -- the same "marker contradicts array order" signal
         `pll_chronology_repair.py` uses for a genuine reorder, but here the
         thing out of place is a whole extra event, not the real one
      5. k is the faceoff immediately following the goal, k's own companion
         ground ball (matching gb_player_id) sits at k's own clock (k is a
         real, correctly-timed draw with real evidence behind it)

    This is exactly the DUPLICATE_FACEOFF_EVENT branch of
    `pll_phase10_possession_repair.detect_faceoff_order_defects` (imported,
    not reimplemented, for the same reason `pll_chronology_repair.py` imports
    the same function: one classification, read twice for two different
    actions). Condition 3+4 alone would also match a genuine DIRECT reorder
    candidate; what makes it a duplicate specifically is a second faceoff
    with IDENTICAL content sitting between i and its own would-be companion
    ground ball -- a real reorder candidate never has that.

WHAT THIS MODULE DOES
    Flags the phantom copy `is_duplicate_event`/`is_duplicate_faceoff = True`
    (OR-merged into whatever `pll_pbp_clean._flag_duplicate_events` already
    set -- never unset a True, never drop a row). The row remains in
    events.csv, fully preserved, simply excluded from
    `is_analysis_eligible_event` exactly like every other confirmed
    duplicate. `duplicate_faceoff_pair_id` links the phantom copy to the
    authoritative one it duplicates, for audit.

RUN ACROSS ALL SEASONS, NOT JUST 2024
    `detect_faceoff_order_defects` already scans 2022-2026; Phase 10's own
    audit (`data/processed/history/possession_repair_evidence_2022_2026.csv`)
    found 33 DUPLICATE_FACEOFF_EVENT rows, all confined to 2024
    (2024_game_10, 2024_game_12, 2024_game_31) -- 3 games, not the 4 stated in
    `2023_POSSESSION_REPAIR.md` Section 9, and zero in 2023. That prose claim
    is corrected in docs/PHASE11_DUPLICATE_FACEOFF.md alongside the
    independent raw-JSON re-verification backing this rule.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pll_phase10_possession_repair import detect_faceoff_order_defects  # noqa: E402

RULE_VERSION = "phase11_duplicate_faceoff_v1"


def flag_duplicate_faceoffs(df: pd.DataFrame) -> pd.DataFrame:
    """Flag phantom duplicate faceoffs in one game's cleaned event frame.

    `df` must already have gone through `pll_pbp_clean.clean()` (needs
    is_duplicate_event, is_duplicate_faceoff present) and, if
    `pll_chronology_repair.repair_game_chronology` also runs on this game,
    should be called BEFORE it -- duplicate detection looks for the classic
    order-inversion shape (condition 3+4 above) among UNREPAIRED positions;
    running after chronology repair has already transposed events would move
    the very index this rule keys on.
    """
    df = df.reset_index(drop=True).copy()
    if "duplicate_faceoff_pair_id" not in df.columns:
        df["duplicate_faceoff_pair_id"] = pd.array([None] * len(df), dtype="object")

    det = detect_faceoff_order_defects(df)
    if len(det) == 0:
        return df
    dup = det[det["evidence_class"] == "DUPLICATE_FACEOFF_EVENT"]
    if len(dup) == 0:
        return df

    et = df["event_type"].to_numpy()
    pid = df["player_id"].astype(str).to_numpy()
    gbid = df["gb_player_id"].astype(str).to_numpy()
    secid = df["secondary_player_id"].astype(str).to_numpy()

    for r in dup.itertuples():
        i = int(r.faceoff_array_index)
        j = int(r.goal_array_index)
        # The authoritative copy k: the first matching-content faceoff after
        # the goal (mirrors detect_faceoff_order_defects's own search window).
        k = None
        for cand in range(j + 1, min(j + 1 + 8, len(df))):
            if (et[cand] == "faceoff" and pid[cand] == pid[i]
                    and gbid[cand] == gbid[i] and secid[cand] == secid[i]):
                k = cand
                break
        df.at[i, "is_duplicate_event"] = True
        df.at[i, "is_duplicate_faceoff"] = True
        if k is not None:
            df.at[i, "duplicate_faceoff_pair_id"] = df.at[k, "event_id"]

    return df
