# Metric limitations

- **Frozen scope:** The updated 2026 publication includes 53 competitive games through September 20; it is still a retrieved snapshot, not a live feed. 2022 offers regular-season and playoff filters; other years remain combined. Historical comparisons are retrospective descriptions, not predictive backtests.
- **Possessions:** roughly 32–36% have ambiguous boundary mechanisms. Team attribution and scoreboard reconciliation do not prove exact possession boundaries. Length statistics are observed spans between distinct, unambiguous, nontruncated boundary events, not complete possession durations. Show eligible-span counts and ambiguity shares.
- **Known source anomalies:** the 2022 Archers–Cannons June 18 game has a seven-PLL-point aggregate event/official scoring gap. Keep it flagged; do not impute goals. The 2023 playoff quarterfinal feed lacks faceoffs that reordering cannot recover. The 2024 duplicate faceoffs are excluded with provenance. Do not infer missing events from expected totals.
- **Touch counts:** the feed's touches are an exposure proxy, not a verified ball-control or passing definition. Player turnover counts omit team-only turnovers (about 19% in the audited 2026 data). Turnovers below expected measure recorded event counts only; no causal point conversion or playmaking claim.
- **Shooting:** the class-average baseline controls only 1PT versus 2PT attempts. Shot location, defender pressure and shot quality are unavailable. Two-point production and selection can be reported; persistent individual two-point conversion ability is not reliably identified here.
- **Goalies:** the published advanced save rate uses attributed, resolved event outcomes. Traditional frontend save rates use official box-score counts. Event `on_goal_no_save` is not silently called a save or a goal. Optional class rates require attributed resolved events plus coverage counts. No pure-goalie-skill claim; shot quality and defensive environment are not controlled.
- **Defense:** caused turnovers, ground balls and penalties measure attributable production. Missing lineups, minutes, matchups and off-ball actions prevent comprehensive individual defensive attribution. Per-game rates do not adjust for role or exposure.
- **Transfers:** modal team is a display label only in archived season tables. Team aggregation must use actual player-game team and season keys. Per-appearance team shares are not season availability shares.
- **Uncertainty:** simple rates do not eliminate sampling noise. Show denominators and explicit user filters. No rank probabilities or true-talent estimates are retained. Old bootstrap intervals omitted major uncertainty and included identified implementation defects.

## Corrections to earlier research claims

Unequal role variance and workload do not prove incompatible units. The reason to avoid a universal score is incomplete attribution and the lack of a defensible shared counterfactual accounting system in this feed. Equal units alone would also not establish additivity.

Algebraic reconciliation establishes an identity, not absence of double counting. A residual rate is not automatically skill. Squared rank correlation is not causal attribution. Empirical-Bayes reliability is not automatically calibrated certainty. Retrospective random-fold cross-validation is not forward prediction. Season totals reflect both workload and observed results; weak adjacent-season rank correlation alone cannot diagnose a broken model.

Pooled or career estimates can be legitimate retrospective research if labeled accordingly. They are not used in the final descriptive surplus metrics, whose baselines use the same season only. Earlier claims contrary to this document are superseded for presentation; earlier research is retained as historical evidence.

## Measured source coverage for final-layer implementation

Resolved saved/goal events all have goalie attribution in the current five-season snapshots. Unresolved on-goal events still number 144, 127, 156, 159 and 154 in 2022–2026 respectively, so class save rates must exclude and disclose them. Four 2022 shot events and one 2024 shot event lack a shooter; the other three seasons have none. Keep these events in league baselines and an unattributed reconciliation bucket, never assign them to a player. Final SQL must not silently lose them by summing only player rows. The audited snapshots have no recorded turnovers on zero-touch player-game rows, but the final denominator guard remains necessary for future refreshes.
