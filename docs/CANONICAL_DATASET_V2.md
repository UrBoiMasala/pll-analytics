# Canonical dataset v2 — refocus

Version: `v2.0.0-refocus`; parent: `v1.0.0-phase11` at `b79076f`.

`CANONICAL_MANIFEST_V1.json` is byte-identical to its checkpoint. Its historical artifact bytes can be recovered from Git at that commit. `CANONICAL_MANIFEST_V2.json` hashes current retained artifacts and relevant transformation code. `refocus_source_checkpoint.json` lists hashes of all 1,224 raw files. The rebuild fails before proceeding if raw data or the parent manifest has changed.

Seven event/possession artifacts intentionally differ from v1: all five possessions files, plus 2023 and 2024 events. Events change only repair flags. Possessions change only `event_count` and `ground_balls`; per-possession IDs, boundaries, teams, durations, points and ambiguity/truncation flags are invariant.

The team SQL outputs are rebuilt because the measurable-span subset changed. Date outputs are explicitly UTC to avoid machine-local serialization differences. Corrected historical shot diagnostics use their own season metadata and explicitly select the simple shot-class baseline actually used in SQL. Player-team stint counts preserve real game-team attribution.

Legacy Phase 8–13 pooled statistics, research outputs, validation reports and value leaderboards are outside this retained v2 foundation and remain archived/reference products. Their old v1-derived duration fields must not be mixed into final v2 analytics. The next implementation phase rebuilds the final publication layer from v2.

The active rebuild is `python3 -B scripts/pll_refocus_foundation.py`. The old v1 manifest writer is historical tooling, not a way to refresh this freeze. `pll_canonical_versions.manifest_failures` verifies both declared versions against their correct locations. The current version has no generated wall-clock timestamp; identical inputs yield identical artifact bytes.
