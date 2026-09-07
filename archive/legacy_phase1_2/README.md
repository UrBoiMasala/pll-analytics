# Archived Phase 1/2 legacy outputs (archived in Phase 4.25)

These files predate the Phase 3 season-wide pipeline (`pll_ingest_season.py`
+ `pll_build_tables.py`, writing to `data/processed/2026/`). They were kept
alongside the canonical outputs and had started to overlap with them, which
risked being accidentally loaded as if they were canonical. They are
preserved here for history/traceability, not deleted, and are no longer
wired into any active script.

## What's here

- `processed/2026-ev-1_play_by_play.csv`, `2026-ev-9_...`, `2026-ev-24_...`,
  `2026-ev-34_...`, `2026-ev-41_...`, `2026-quarterfinals-1_...` — the 6
  per-game CSVs produced one-at-a-time by `pll_pbp_extractor.py` during the
  Phase 1/2 proof-of-concept, before full-season ingestion existed. Fully
  superseded by `data/processed/2026/events.csv`, which contains these same
  6 games (by `game_slug`) plus all other completed games, built through
  the same normalization/cleaning code path (`pll_pbp_extractor.normalize_play_by_play`
  + `pll_pbp_clean.clean`, both still active in `scripts/`).
- `processed/validation_report.csv` — the Phase 2 validation report (this
  file used to live at `data/processed/validation_report.csv`, one level up
  from the canonical `data/processed/2026/` directory — easy to confuse
  with the canonical `data/processed/2026/validation_report.csv`). Only
  covered the 6 games above. Superseded by
  `data/processed/2026/validation_report.csv`
  (`scripts/pll_validate_season.py`), which covers every completed game
  with an explicit raw/cleaned/official schema.
- `scripts/pll_validate.py` — the Phase 2 validation script that produced
  the report above. Only consumer/producer of the 6 legacy CSVs; archived
  alongside them since it has no other purpose and is fully superseded by
  `scripts/pll_validate_season.py`. Left runnable as-is (unmodified) for
  historical reference, but it will not find its inputs unless pointed at
  this archive directory.

## What's NOT here (still active — do not archive)

- `scripts/pll_pbp_extractor.py` — still imported directly by
  `scripts/pll_build_tables.py` (`from pll_pbp_extractor import
  normalize_play_by_play`) for every game in the season builder. This is
  reused production code, not a leftover from an earlier phase, even
  though it originated in Phase 1.
- `scripts/pll_pbp_clean.py` — the cleaning/validation rules, used by both
  the archived Phase 2 script and the active Phase 3+ season builder.

## Why this matters for anyone loading data/processed/*

Nothing under `data/processed/` root (only `data/processed/2026/`) should
be treated as canonical going forward. Any future export or ingestion
pipeline should read from `data/processed/2026/` exclusively; the files in
this archive directory must never be loaded alongside
`data/processed/2026/events.csv` or `.../validation_report.csv` — the
column schemas are related but not identical (the legacy CSVs lack
`game_id`, `game_type`, `include_in_league_analytics`,
`is_analysis_eligible_event`, etc.).
