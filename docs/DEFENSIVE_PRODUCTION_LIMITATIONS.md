# Defensive Production — Limitations (V1)

**This file describes production, not value.** No individual defensive
value model is built, per Phase 12's `ROLE_ONLY` classification
(`docs/DEFENSIVE_VALUE_FEASIBILITY.md`), and this document exists
specifically to keep that boundary visible.

## What is published

`data/processed/2026/defensive_production_2026.csv`: `caused_turnovers`,
`ground_balls`, `penalties`, `games_played`, `caused_turnovers_per_game`,
and `defensive_value_partial_raw` (carried through for continuity with the
canonical dataset, **not used to sort or rank this table**).

## Sort order, deliberately

Sorted by `games_played` (an availability fact), never by a production
column. Section H of the Phase 13 brief and `MF6_measurable_defensive_production_leaderboard`
in Phase 12's model candidate scorecard both specify this: any single
sort by a production count risks being read as a ranking, which this table
explicitly is not.

## Why no value model — restated from Phase 12, not re-litigated

- Zero of 52,633 raw events across five canonical seasons (2022-2026) name
  a causing or closest defender.
- No minutes, shifts, or lineup data exists anywhere in the feed, so no
  defender has an exposure denominator beyond games played.
- Caused turnovers correlate with `games_played` at rho=0.49-0.80 by
  season — up to 64% of the rank variance in raw caused turnovers is
  availability, not impact.

## What is NOT inferred, per the Phase 13 brief's explicit instruction

Individual defense is **not** inferred from team defensive efficiency,
games played, team wins, position label, or ground balls alone. None of
these appears anywhere in this table as a value estimate. `ground_balls`
and `caused_turnovers` are shown as raw counts with their available context
(`games_played`, `caused_turnovers_per_game`) and nothing more.

## Data coverage statement (carried on every row)

> PARTIAL: caused_turnovers and ground_balls are box-score totals with a
> games-played denominator only (no minutes/shifts/lineups exist). Zero of
> this feed's raw events name a causing or closest defender.
> defensive_value_partial_raw residualizes caused turnovers against the
> position group's per-game rate and is shown for continuity with the
> canonical dataset, but this table is NOT sorted or ranked by it.

## What would change this

Restated from `docs/DEFENSIVE_VALUE_FEASIBILITY.md` §4: minutes/shifts,
lineups, matchup/assignment data, a shot-defender field, populated
`causedTurnoverId`/`closestDefenderId` fields, or on/off possession data.
If any of these arrive in a future feed, the existing residual-baseline
framework (`PLAYER_VALUE_ACCOUNTING.md`) extends to them directly — no new
architecture would be needed, only new inputs.
