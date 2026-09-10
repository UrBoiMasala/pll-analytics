# Project refocus

The final product is a validated PLL advanced-statistics database with a small, explainable metric catalog. It demonstrates ingestion, cleaning, reproducibility, Python, SQL, sports analysis and honest communication. A dashboard is a later phase.

## Scope decisions

Keep the data foundation, identity links and team/event/possession analytics. Propose 29 core metrics (4 STANDARD, 23 DERIVED_ADVANCED, 2 ORIGINAL_PLL_METRIC), with ordinary box-score context shown separately. The catalog is a contract for the next analytics-layer implementation, not a claim that all new views exist.

Shooting value measures PLL scoring points relative to season league conversion by shot class. Ball security stays in turnover events. They are not added together. Faceoff surplus stays in wins. Goalie surplus stays in saves. Defense is descriptive production only.

Retire universal valuation, role value composites, point-converted faceoffs/turnovers, rank simulations, pairwise probabilities, shrinkage sensitivity, career ability leaderboards, positional percentiles as value, opponent adjustments and dominance diagnostics from the final product. Preserve their code and reports as reference; do not delete history or raw data.

The final documentation hierarchy is README → DATA_PIPELINE, DATA_VALIDATION, POSSESSION_METHODOLOGY, ADVANCED_METRICS, METRIC_LIMITATIONS, SQL_GUIDE. FINAL_METRIC_CATALOG is the exact specification; FINAL_METRIC_INVENTORY records every named catalog decision. Audit and canonical-version documents are supporting detail. No mass moves are necessary.

## Safety checkpoint

The user identified the relocated checkout at `/Users/siddharthalluri/CPFA_email_detector`. Its main branch began at `b79076f` (Phase 13). The sole dirty file differed only in test collection time, 0.30s versus 0.29s. That verified churn was removed before work. No legitimate prior change was discarded. The existing commit is the clean checkpoint; no redundant checkpoint commit was needed.

All 1,224 raw files were byte-hashed into `refocus_source_checkpoint.json`. All 36 v1 artifact hashes matched before work. The original v1 manifest remains byte-identical. The v1 artifacts remain recoverable at the checkpoint commit; canonical v2 intentionally replaces seven event/possession files in the working tree.

## Lifecycle contract

ACTIVE means retained canonical foundation or current refocus documentation/specification. EXPERIMENTAL means reference code or diagnostic that must not be imported wholesale into a public query. ARCHIVED means prior outputs/documents superseded for presentation. The lifecycle CSV and the final catalog override old CORE, production and qualification labels. No final query may use an archived season-to-modal-team assignment.

## One-minute explanation

“I built a five-season Premier Lacrosse League analytics project that turns play-by-play and box scores into validated team and player statistics. Python handles the cleaning and possession reconstruction, and SQL makes the results easy to explore. The metrics cover pace, efficiency, shooting, ball security, faceoffs and goalkeeping, with special attention to the PLL’s two-point line. One metric measures shooting points above league expectation on the same mix of one- and two-point attempts. I also document feed gaps and avoid claiming that the data measures individual defense or a universal best player.”

## Next phase

Implement only the specified final metric layer and eight SQL views. Include class coverage, denominators, actual-team stint keys, NULL behavior, game-scope metadata and independent formula tests. Produce final historical descriptive tables and example queries. Validate them before building a dashboard. No new valuation research is required.
