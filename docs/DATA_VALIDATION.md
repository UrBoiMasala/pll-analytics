# Data validation

Run `python3 -B scripts/pll_validate_refocus.py`. It reads real input tables and checks raw byte hashes, both canonical versions, unique keys, competitive completed scope, possession boundary resolution, initiating ground-ball accounting, repair flags, event/possession point agreement, the exact known scoring exception, actual-team stint totals, season shot metadata, SQL/CSV agreement, shot-class residual accounting and catalog scope.

The known 2022 scoring discrepancy is an explicit seven-point exception for one named game, not a broad tolerance. Unexpected discrepancies fail. Numeric SQL comparisons use 1e-9 tolerances and normalize date representations to UTC.

Regression tests cover opening goals counted once, closing turnovers and redundant companion events, ground-ball changes, transferred-player team attribution, duplicate player-games, historical home-goal pre-shot scores and rejection of mismatched season metadata. Existing chronology tests now require both swapped rows to be flagged; the changed expected counts are documented, not loosened.

The first post-repair full run produced 420 passes and four failures because archived Phase 12/13 validators required current files to match v1. The validators now check v1 at its original Git commit and v2 on disk, preserving both version guarantees. Their remaining legacy research checks are regression checks, not scientific validity claims. Their test-count check is labeled as collection coverage rather than proof that tests were never weakened.

See `REFOCUS_VALIDATION_RESULTS.md` for the final run and deterministic rebuild evidence. Do not infer statistical calibration from a passing suite.
