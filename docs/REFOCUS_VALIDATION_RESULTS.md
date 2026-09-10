# Refocus validation results

- Full suite: **424 passed, zero failed, zero deselected**. This includes the seven ingestion refresh tests that were not executed during the earlier read-only audit.
- Retained foundation validator: **14/14 PASS**, verified from inputs and live SQL queries.
- Deterministic rebuild: **68/68 byte-identical**, covering 67 v2 artifact files plus the v2 manifest across two successive final rebuilds.
- All **1,224 raw files** retain their checkpoint byte hashes; the v1 manifest is unchanged. All 36 v1 artifacts verify at the original commit.
- Legacy Phase 12/13 validators also pass with explicit version-aware hash checks. This is regression evidence only; it does not rehabilitate the retired statistical features.
- Git whitespace check passed after excluding unnecessary legacy definition-table churn. No raw payloads, caches or scratch files belong in this commit.

Commands:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest tests/ -q -p no:cacheprovider --capture=sys
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/pll_validate_refocus.py
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/pll_refocus_foundation.py
```

The full suite emits existing urllib3/LibreSSL and pandas compatibility warnings (11 warnings in the recorded run). They do not change these offline test results. Dependency versions are recorded in refocus_environment.csv; no dependencies were upgraded in this phase.

## Before/after findings

| Season | Possession ground balls before → after | Measurable spans before → after | Mean span seconds before → after |
|---|---|---|---|
| 2022 | 1519 → 2791 | 1949 → 2196 | 28.850 → 29.093 |
| 2023 | 1685 → 3132 | 2066 → 2296 | 26.533 → 26.746 |
| 2024 | 1583 → 2882 | 2023 → 2215 | 25.477 → 26.085 |
| 2025 | 1557 → 2759 | 1913 → 2100 | 26.328 → 26.847 |
| 2026 | 1734 → 3091 | 2096 → 2306 | 25.761 → 25.936 |

Possession counts and boundaries are unchanged. Chronology flags increase from 256 to 455 in 2023 and from one to two in 2024; the ordering itself is unchanged. Team duration aggregates/splits change; scoring, possession counts and other retained team rate numerators do not. Team-game timestamps are now explicitly serialized in UTC, representing the same instants.

Historical rich-shot-model Brier scores change from .198474/.192590/.187929/.191734 to .202282/.196303/.191169/.195403 in 2022–2025 after eliminating mismatched game metadata. The simple season shot-class baseline is the explicitly selected policy. These diagnostics remain experimental and are not forward predictions.

See refocus_foundation_impact.csv, refocus_statistic_impact.csv and refocus_shot_diagnostic_impact.csv for exact values. The final 29-metric publication layer is proposed and must be independently implemented/validated next; it is not included in this pass claim.
