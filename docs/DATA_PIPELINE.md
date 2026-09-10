# Data pipeline

Raw PLL JSON → normalized games, teams, players and box scores → cleaned eligible events → duplicate-faceoff flags and supported chronology repairs → reconstructed possessions → SQL team analytics.

The current refocus entry point is `scripts/pll_refocus_foundation.py`. It reads local raw files only, rebuilds event/possession data, team analytics, corrected season-specific shot diagnostics and player-team stint counts. It writes canonical v2 and a before/after report. It deliberately does not rebuild the archived research layers.

Source payloads are preserved and byte-hashed. `refocus_source_checkpoint.json` covers every raw file, including schedules and metadata. `CANONICAL_MANIFEST_V1.json` is preserved; its files are verified at the checkpoint commit. `CANONICAL_MANIFEST_V2.json` describes current retained derived files. Never run the old v1 manifest writer to relabel changed data as the same freeze.

The final player metric layer is proposed, not implemented. Its source keys are `(season, game_id, player_id, team_id)` and `(season, player_id, team_id)` for stints. IDs must be VARCHAR, preserving leading zeroes. Names are labels, never keys. Player-season totals combine stints without assigning all production to a modal team.

No raw payload deletion, network refresh, dashboard work or Phase 14 implementation occurs in refocus.
