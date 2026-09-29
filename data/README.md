# Data

The included files make the frozen analysis reproducible without a fresh API request.
Start with **publication** outputs for current statistics.

| Directory | Contents | Use |
| --- | --- | --- |
| `raw/` | Original PLL JSON, schedules, and metadata | Source audit and ingestion research |
| `processed/2022/` through `processed/2026/` | Canonical games, events, possessions, and box scores alongside older research outputs | Reproducibility and input inspection |
| `processed/history/` | Cross-season inputs, manifests, and historical model outputs | Provenance and research; not a second publication layer |
| `publication/` | 13 current tables, per-season exports, dictionary, and validation | Main analysis interface |

## Choose a publication table

- [Team statistics](publication/team_advanced_stats.csv)
- [Player season summary](publication/player_season_summary.csv)
- [Goalie statistics](publication/goalie_advanced.csv)
- [Faceoff statistics](publication/faceoff_advanced.csv)
- [Coverage](publication/publication_coverage.csv)
- [Metric dictionary](publication/metric_dictionary.csv)

Pooled files already include every season-specific row. Do not concatenate pooled
files with their per-season copies. For players, choose `SEASON` or `STINT`, never both.
Preserve leading zeros in IDs and distinguish empty values from observed zeros.

The 2026 snapshot is partial through the game starting August 30, 2026 at 00:30 UTC.
Source rights remain with the PLL; the repository's
[publication record](../docs/PUBLICATION_SAFETY.md) is not a general redistribution license.

Do not edit frozen inputs to force an expected result. Investigate discrepancies and
record evidence. See [validation](../docs/DATA_VALIDATION.md) and
[SQL usage](../docs/SQL_GUIDE.md).
