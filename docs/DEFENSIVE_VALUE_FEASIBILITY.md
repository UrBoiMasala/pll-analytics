> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Defensive Value: An Adversarial Feasibility Investigation (Phase 12 §I)

This document is written to try to rescue individual defensive value
measurement, and to say plainly if it cannot be rescued. **It cannot, beyond
what Phases 6, 7 and 10 already published**, and this document explains
exactly why, tests every defensible signal available, and states precisely
what additional data would be needed.

Labels: **OBSERVED** · **DERIVED** · **MODELED** · **INFERRED** ·
**UNSUPPORTED**.

---

## 1. What the raw feed contains — re-verified on the canonical 2022-2026 corpus

`defensive_attribution_audit.csv`, re-verified in the Phase 12 dependency
analysis rather than merely cited:

| | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| Raw events | 10,433 | 10,490 | 10,133 | 10,323 | 11,254 |
| Turnover events naming the causing defender | **0** | **0** | **0** | **0** | **0** |
| Events naming a closest defender | **0** | **0** | **0** | **0** | **0** |
| Caused turnovers vs games_played (rho) | 0.686 | 0.494 | 0.593 | 0.602 | 0.802 |

**Zero of 52,633 raw events across five seasons name a causing or closest
defender.** This is not a sampling artifact or a column that happens to be
sparsely populated — the field is absent from the schema's populated data
in every single event, every season, independent of the canonical Phase 11
possession-chronology repair (which touches only `event_number` and
`seconds_passed`, never event content — see `PHASE11_BEFORE_AFTER_AUDIT.md`).

## 2. Every defensible signal, tested

**Caused turnovers.** A box-score total, correctly countable, but confounded
with availability at rho=0.49-0.80 by season (re-verified above on the
canonical player table) — up to **64%** of the rank variance in raw caused
turnovers is games played, not defensive impact.

**Ground balls.** Countable, but not separable from faceoff-scrum recovery
context (61.5% of post-faceoff ground balls go to the faceoff winner) and
carries no defensive-possession denominator of its own.

**Penalties committed.** Countable (`caused_turnover_team_share`-adjacent
context in `player_stats_2022_2026.penalties`), but this project has never
built a defensive-value component from it — a penalty coefficient was
estimated in Phase 6 (-0.417) as a Lacrosse-Reference-reproduction exercise,
never added to any published player value.

**Team defensive efficiency, with attributable exposure.** **Cannot be
computed for any individual.** Team `defensive_efficiency` exists at the
team-season level (`team_stats_2022_2026.csv`) but there is no per-player
denominator — no minutes, no shifts, no lineups — to convert it into an
individual defender's exposure-adjusted rate.

**`defensive_value_partial_raw` itself.** The existing published component —
caused turnovers residualized against the position group's per-game rate.
Re-verified: `EPA_points_raw = defensive_value_partial_raw` exactly for a
pure defender (other components null/zero), and the games-played
denominator only **partially** removes the availability confound (dividing
by games, not by defensive possessions, treats a defender who plays every
defensive possession and one who rotates as equally exposed).

## 3. "We know defenders matter" vs "we can measure how much this defender contributed"

These are explicitly different claims, and this document does not conflate
them. **We know defenders matter** — lacrosse's structure and every domain
expert's account of the game say so, and nothing here disputes it. **We
cannot measure how much any individual defender contributed** beyond a
partial, availability-confounded, box-score total, because:

1. No event names a causing or closest defender (§1).
2. No exposure denominator (minutes, shifts, on-field possessions) exists
   for anyone, so a defender's caused-turnover rate cannot be divided by
   "opportunities to cause a turnover" — only by games played, which is a
   crude proxy that mixes starters, rotational players, and specialists on
   one scale.
3. Shot suppression, help defense, matchup difficulty, sliding, and forcing
   a bad shot instead of a turnover are entirely unrecorded — a defender who
   forces four difficult, missed shots and zero turnovers is
   indistinguishable in this feed from a defender who did nothing.

`player_value_signal_inventory.csv` and `player_value_model_candidates.csv`
both encode this distinction directly: `defensive_value_partial_raw` is
classified `ROLE_ONLY` (not `REJECTED`, because the countable part — caused
turnovers, correctly residualized — is real and usable within-role) and not
`UNSUPPORTED` (because it is not zero information, just partial).

## 4. What additional data this would require

Stated exactly, per the Phase 12 brief:

- **Minutes or shifts.** The single highest-value addition — without it, no
  defender has an exposure denominator, full stop.
- **Lineups.** Needed to know which defenders were on the field for a given
  defensive possession at all.
- **Matchup/assignment information.** Needed to know who a defender was
  covering, and therefore whether a shot allowed against that assignment is
  attributable.
- **Shot defender.** A field naming the primary defender on a given shot
  attempt — analogous to a "closest defender" tag — would let shot
  suppression be measured directly (comparing shooting percentage allowed
  by defender to a league baseline, the same residual-baseline logic already
  used offensively).
- **Caused-turnover attribution.** The `causedTurnoverId` /
  `closestDefenderId` fields already exist in the schema and are simply
  never populated — if a future feed populates them, no new pipeline
  architecture is needed; the existing residual-baseline framework
  (`PLAYER_VALUE_ACCOUNTING.md`) would extend to it directly.
- **On/off possession data.** Needed for any possession-level defensive
  value (Model Family 2) to become possible at all.

## 5. Verdict

**Individual defensive value remains unmeasurable beyond a partial,
availability-confounded production count.** This document changes nothing
about that verdict — it re-tests every angle the Phase 12 brief names and
finds the same binding constraint Phase 10 already identified: measurement
coverage, not statistical technique. The correct response is the one this
project has already taken and this document reaffirms: publish the partial
signal with `partial` in every column name and a stated caveat, never
manufacture a fabricated exposure denominator, and never present
`defensive_value_partial_raw` at or near zero as "an average defender."
