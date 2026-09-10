# Possession methodology

The existing state machine remains: faceoff wins establish control; goals, turnovers and shot-clock expirations close possessions; ground-ball team changes switch control; unexplained shots/control changes are flagged; periods and games never carry open possessions forward. See the root historical `POSSESSION_METHODOLOGY.md` for the full rule set.

Canonical v2 changes bookkeeping, not these transitions:

1. Each participating event number contributes at most once to a possession's event count. This counts state-machine events and boundaries, not every intervening log row; interior penalties and other no-effect rows remain excluded.
2. The closing boundary event is included. A control-switch event may bound both adjacent possessions, so summing possession event counts is not a league event count.
3. An initiating ground ball counts for its recovering team's new possession. The closing opponent boundary does not receive ground-ball production.
4. Duration eligibility directly requires distinct boundary event IDs plus unambiguous, nontruncated status.
5. Both rows of a chronology transpose carry `chronology_repair_applied`; original numbers/times remain recoverable. The ordering-rule version stays unchanged because ordering rules did not change; the corrected provenance bookkeeping is versioned by canonical v2.

Possession IDs, counts, offense/defense teams, boundaries, duration values, scoring and ambiguity/truncation flags are unchanged versus v1 across all five seasons. Only the counts and eligibility-dependent aggregates change. The before/after CSV contains exact season totals.

Duration is an observed event span. It is not estimated time of actual ball control, and incomplete feeds cannot support individual on/off metrics.
