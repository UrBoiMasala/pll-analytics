# PLL Analytics

A five-season Premier Lacrosse League analytics pipeline that transforms play-by-play and box-score data into validated possession-based team and player advanced statistics using Python and SQL.

**35 interpretable core metrics, 2022–2026.** The 2026 data is a frozen partial-season snapshot: the latest included game starts **August 30, 2026 at 00:30 UTC**. Completed regular-season and playoff games are included; all-star, exhibition and incomplete games are excluded.

Source statistics: [Premier Lacrosse League](https://premierlacrosseleague.com/). Independent research; not affiliated with or endorsed by the PLL. The project owner reports permission to publish this personal learning project; see the [publication authorization record](docs/PUBLICATION_SAFETY.md). No general license to reuse PLL data is implied.

## Objective

Turn event feeds into reproducible, understandable analytics while making source gaps and measurement limits visible. The product covers team efficiency, pace and possession duration, shot generation, shooting, PLL two-point analytics, player usage, ball security, faceoffs, goalkeeping and descriptive defensive production.

```text
RAW DATA
    ↓
INGESTION / CLEANING
    ↓
CANONICAL V2
    ↓
POSSESSION RECONSTRUCTION
    ↓
ADVANCED METRICS / SQL VIEWS
    ↓
PUBLICATION TABLES
    ↓
DASHBOARD — next phase, not built
```

## Example metrics

- Offensive efficiency = 100 × PLL points / offensive possessions.
- Shot-producing possession rate = possessions with at least one shot / possessions.
- PLL Points per Shot = (one-point goals + 2 × two-point goals) / attempts.
- Shooting value above expectation = G1 + 2G2 − A1p1 − 2A2p2, using same-season pooled class conversion rates.
- Faceoff wins above average = wins − attempts × season league win rate.
- Saves above average = resolved saves − resolved shots faced × season league save rate.

These are descriptive rates and residuals, not talent estimates or a universal player score. Two-point shooting value is already part of total shooting value and must not be added twice.

## Reproduce and query

Python dependencies are pinned to the tested environment in `requirements.txt`.

```sh
python3 -m pip install -r requirements.txt
python3 -B scripts/pll_validate_refocus.py
python3 -B scripts/pll_build_publication.py
python3 -B scripts/pll_validate_publication.py
python3 -B -m pytest -q -p no:cacheprovider
python3 -B scripts/pll_query_publication.py
```

The final builder reads the frozen canonical data; it does not fetch new data or rerun archived value research. To create a local SQL database, add `--database /tmp/pll-publication.duckdb` to the builder. The [SQL examples](sql/publication_examples.sql) answer 16 team, player and historical questions.

```sql
SELECT team_id, offensive_efficiency, possessions
FROM team_advanced_stats
WHERE season = 2026
ORDER BY offensive_efficiency DESC NULLS LAST, team_id;
```

Player tables distinguish `SEASON` totals from actual-team `STINT` rows. Select one aggregation level; never sum both. Shares use team workload only in each player's actual appearances, including transfers.

## Repository map

- `data/raw/`: frozen source payloads; source rights remain with PLL.
- `data/processed/`: canonical v2 and preserved historical research outputs.
- `data/publication/`: final pooled and season-specific CSV tables, dictionary and validation.
- `scripts/`: ingestion, reconstruction, SQL orchestration and validation.
- `sql/`: final publication definitions/examples plus preserved historical queries.
- `tests/`: foundation, historical and publication regressions.
- `docs/`: methodology, catalog, limitations and implementation report.
- `archive/`: earlier research artifacts.

Start with the [metric catalog](docs/FINAL_METRIC_CATALOG.md), [machine-readable dictionary](data/publication/metric_dictionary.csv), [publication methodology](docs/PUBLICATION_METHODOLOGY.md), and [SQL guide](docs/SQL_GUIDE.md).

## Validation and limits

The pre-implementation checkpoint passed 424 tests and all 14 refocus checks. Final validation independently reconciles canonical possessions, scoring, shot attribution, appearance denominators, transfer totals, goalie resolution and all five seasons of SQL/CSV outputs. Negative tests exercise zero exposure, missing official values, unresolved goalie outcomes and duration boundaries. See the [implementation report](docs/FINAL_IMPLEMENTATION_REPORT.md) for final results and byte-for-byte rebuild checks.

Possession ambiguity is visible rather than silently filtered. Pace and TOP describe measurable spans, with coverage; they do not recover full game clock control. The known 2022 seven-point source gap remains flagged. Unattributed historical shots remain in league/team totals. Goalie outcomes lack shot-quality and defensive-environment controls. Defensive production lacks minutes, lineups and matchup attribution. Partial-2026 volumes need explicit labeling in historical comparisons.

## Technology and research history

Python, pandas, NumPy, DuckDB SQL, requests, pytest and Git. Published on GitHub with owner-reported permission for this personal learning project.

Earlier player-value research is preserved for reproducibility and reference. It is not the final product. No MVP, WAR, cross-position composite, faceoff point conversion, bootstrap ranking or true-talent model enters these publication tables. The dashboard is the next phase.

## Local statistics frontend

The screenshot-based **PLL Stats** frontend is available locally. Run `python3 -B frontend/scripts/build.py`, then `python3 -m http.server 4173 --bind 127.0.0.1 --directory frontend/dist`. Open http://127.0.0.1:4173/. See the [frontend guide](frontend/README.md) for routes, data contracts and tests. This does not publish the data or change the publication-safety decision.
