# PLL Analytics

A multi-season PLL analytics project that transforms play-by-play and box-score data into validated team and player advanced statistics, including PLL-specific metrics that are not readily available in standard league statistics.

The project combines real 2022–2026 data, Python cleaning and validation, a reproducible possession model, and SQL analytics. The proposed final product has **29 interpretable core statistics** covering team pace and efficiency, shooting, two-point selection and production, ball security, faceoffs, goalkeeping, and descriptive defense.

**Current stage:** foundational audit repairs and final metric specification completed; the final publication views and dashboard are not built yet. The 2026 data is a frozen partial-season snapshot (last included game starts 2026-08-30 00:30 UTC). Scheduled or incomplete later games are excluded.

Start here:

- [Final metric catalog](docs/FINAL_METRIC_CATALOG.md): formulas, units, sources and scope.
- [Data pipeline](docs/DATA_PIPELINE.md) and [validation](docs/DATA_VALIDATION.md).
- [Possession methodology](docs/POSSESSION_METHODOLOGY.md).
- [Metric limitations](docs/METRIC_LIMITATIONS.md).
- [SQL guide and proposed schema](docs/SQL_GUIDE.md).
- [Refocus decisions](docs/PROJECT_REFOCUS.md) and [audit remediation](docs/AUDIT_REMEDIATION.md).

## Reproduce the retained foundation

Use a Python environment with pandas, numpy, DuckDB, requests and pytest. The recorded validation environment is in `data/processed/history/refocus_environment.csv`. Run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/pll_refocus_foundation.py
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/pll_refocus_catalog.py
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/pll_validate_refocus.py
PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest tests/ -q -p no:cacheprovider
```

The foundation rebuild writes derived files, verifies all raw byte hashes, preserves the v1 manifest, and produces canonical v2. It does not fetch new data. The validator is read-only unless `--write-report` is supplied. Full legacy tests can regenerate archived reports; those reports are not endorsements of the archived models.

## Why no universal player score?

The project investigated comprehensive player valuation. The feed supports much better measurement of shooting, draws and saves than of individual defense. We therefore chose role-specific, interpretable statistics. There is no final MVP, WAR, cross-position rating, or defensive-impact composite. Letting the data constrain the conclusions is part of the project.

Earlier research remains in place for reference, with lifecycle classifications in `data/processed/history/artifact_lifecycle.csv`. Its old “production” labels are superseded by the final catalog.
