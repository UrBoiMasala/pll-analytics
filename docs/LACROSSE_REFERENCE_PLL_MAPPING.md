> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Lacrosse Reference → PLL Metric Mapping

Lacrosse Reference is the reference public lacrosse analytics work, and its
concepts are the vocabulary most readers of this project will arrive with. This
document is the **single lookup table** from an LR concept to what exists here,
under what name, and with what status.

It consolidates the two per-phase reference studies —
[`EGA_REFERENCE_RESEARCH.md`](EGA_REFERENCE_RESEARCH.md) (Phase 6) and
[`USAGE_ADJUSTMENT_REFERENCE_RESEARCH.md`](USAGE_ADJUSTMENT_REFERENCE_RESEARCH.md)
(Phase 7) — into one metric-by-metric map against the Phase 8 catalog. Those two
documents remain the evidence; this is the index.

**Adaptation categories used below:**

| | |
|---|---|
| **REPRODUCED** | LR's method, applied unchanged. |
| **ADAPTED** | LR's concept, PLL-specific formula, with the reason. |
| **INDEPENDENT** | LR does not document it; built here. |
| **REJECTED** | Tested against this feed and rejected, with evidence. |
| **REFUSED** | Constructible, deliberately not built. |
| **UNSUPPORTED** | Cannot be built from this feed. |

---

## 1. The one divergence that governs everything else

**This project's `EPA_points` is not Lacrosse Reference's EGA, and is
deliberately not named EGA.**

| | LR EGA | This project (`EPA_points`) |
|---|---|---|
| Estimand | net goal margin in the 60 s *after* each event | points produced *minus* points expected on the same opportunities |
| Does a goal score highly? | **No** — +0.02, the goal is outside the window | **Yes** — a one-point goal is `1 − 0.293 = +0.707` |
| Baseline | implicit (zero net margin) | explicit league-average conversion for the opportunity class |
| League aggregate | not zero | **exactly zero, by construction** |
| Volume behaviour | cumulative | residual — more events help only if converted above average |

They are not rescalings of one another. Calling this EGA would assert an
equivalence that is demonstrably false: under EGA the league's best finisher
gains almost nothing for finishing. Every name in this system is chosen so it
cannot be mistaken for LR's quantity.

---

## 2. The forward-window estimator: REPRODUCED, and it validates

LR's forward-window event valuation *was* reproduced exactly
(`pll_player_value_models.py::estimate_event_values`), in PLL points rather than
goals, and is used to derive the turnover, faceoff and ground-ball coefficients
empirically rather than inventing them.

| Play type | LR (NCAA, goals) | PLL 2026 (points) | n |
|---|---|---|---|
| Faceoff win | +0.18 | **+0.188** | 1,301 |
| Turnover | −0.17 | **−0.185** | 1,721 |
| Penalty | −0.31 to −0.36 | **−0.402** | 281 |
| Ground ball | +0.19 | +0.139 | 3,091 |
| Missed shot | +0.19 | +0.097 | 1,539 |
| Saved shot | +0.03 | −0.086 | 1,295 |
| Unassisted goal | +0.02 | −0.027 (1-pt goal) | 1,046 |

Faceoff wins, turnovers and penalties land almost exactly on the published NCAA
values — strong evidence the estimator was reproduced correctly. Ground balls and
shots are lower and saved shots are negative rather than positive, plausibly
because the PLL's 32/52-second shot clocks and higher pace shorten the window's
reach. **This project does not claim to have established that cause.**

One thing LR does not document was added: a **neutral reference**. The same
statistic over all team-attributed events is +0.0151, so every PLL coefficient
is reported net of it. Without that adjustment a coefficient of zero would not
mean "neutral".

**The table above is the GROSS estimate**, because that is what compares to LR's
published figures. The coefficients the value framework actually uses are the
net ones in `player_value_baselines.csv`: faceoff win **+0.173**, ground ball
**+0.124**, turnover **−0.200**, penalty **−0.417**. Each is the gross value
minus 0.0151. Do not quote the two sets interchangeably.

---

## 3. The full map

### 3.1 Value framework

| LR concept | Adaptation | Metric here | Status |
|---|---|---|---|
| Forward-window event valuation | **REPRODUCED** | the `event_value__*` rows of `player_value_baselines.csv`; the per-player ground-ball total survives as the `ground_ball_event_value_descriptive` column of `player_value_components.csv`, outside every total | DIAGNOSTIC |
| EGA (overall) | **ADAPTED** — different estimand (§1) | `EPA_points_raw` | CONTEXTUAL |
| Offensive EGA | **ADAPTED** — rebuilt as an opportunity-baseline residual with explicit PLL two-point handling, which has no NCAA analogue | `offensive_EPA_points_raw` | CORE |
| Faceoff EGA | **ADAPTED** — LR gives an event value, not a marginal one. Here: `(wins − expected wins) × 2v`, so a league-average specialist scores exactly zero | `faceoff_value_raw` | CORE |
| Defensive EGA | **ADAPTED, and explicitly PARTIAL** — only caused turnovers are supported; blocked shots do not exist in this feed | `defensive_value_partial_raw` | CONTEXTUAL |
| Goalie value | **INDEPENDENT** — LR does not document one. Built from expected points allowed on shots on goal faced, with separate one- and two-point baselines | `goalie_value_raw` | CORE |
| Penalty value | **REPRODUCED but not used** — the coefficient (−0.402) is estimated and published in the baselines table; no penalty component is added to player value | — | DIAGNOSTIC |
| Assisted / unassisted split | **UNSUPPORTED** | — | DEFERRED |
| Blocked shots, pipe shots | **UNSUPPORTED** — neither event type exists in the PLL feed | — | — |

### 3.2 Usage

| LR concept | Adaptation | Metric here | Status |
|---|---|---|---|
| Play shares (appearance count) | **REPRODUCED** exactly, then audited and **not adopted** as the usage measure | `event_log_play_shares`, `event_log_play_share` | DIAGNOSTIC |
| uaEGA = EGA ÷ play shares | **REPRODUCED** on this project's estimand, named so it cannot be mistaken for LR's metric | `uaEPA_per_event_log_play_share` | DIAGNOSTIC |
| — | **INDEPENDENT** replacement: a usage measure with a stated numerator and denominator, `(shots + turnovers) / the same summed over the team in the games played` | `offensive_play_share` | CORE |
| 1% team play-share minimum | **REPRODUCED** verbatim | `future_award_input_eligible` | CONTEXTUAL |
| Usage adjustment of the *mean* | **REJECTED by cross-validation** — the constant model beat linear and quadratic (CV MSE 8.767 / 8.803 / 8.847); usage does not predict the mean of measured value in 2026 (r = +0.072) | `expected_EPA_given_usage` (a single number, 0.086932) | EXPERIMENTAL |
| — | **INDEPENDENT**: usage moves the *variance*, not the mean — sd of offensive EPA rises 0.50 → 4.73 across usage quintiles, so the adjustment that works divides by the chance sd at the player's own volume | `EPA_vs_usage_expectation_z` | EXPERIMENTAL |

**Why dividing by play shares was not adopted:** it does not survive an audit of
what a play share is. It is a count of *appearances in the event log*, which is
role-determined before it is player-determined; dividing by it turns a
cross-position incomparability into a ratio that hides it. Both LR forms are
still published, as DIAGNOSTIC, so the comparison can be made.

### 3.3 Roles and pools

| LR concept | Adaptation | Metric here | Status |
|---|---|---|---|
| Player classification into roles | **ADAPTED** | `value_role`, `canonical_position`, `position_group` | CORE |
| FOGO threshold at 50% | **ADAPTED — denominator independently chosen.** LR's 50% applies to a share of VALUE; `EPA_points` is a signed residual, so "50% of a possibly-negative sum" is undefined. Applied to the player's share of his **team's faceoffs** instead. In 2026 the threshold lands in an empty band between 0.158 and 0.812, so no classification depends on the choice | `faceoff_team_share` | CORE |
| Defensive threshold at 30% | **REJECTED — tested, and it fails.** Applying 30% to opportunity shares put **24 of 96 rostered defenders (21 of 42 SSDMs) in the offensive class**, because the feed attributes one defensive act (741 caused turnovers) against 4,106 shots. The roster label is used instead, and `mapping_reason` records that on every row | `canonical_position` | CORE |
| Percentile within an offensive pool | **ADAPTED** — LR's pool definitions are not published, so this project defines its own and publishes both partitions | `EPA_position_percentile`, `usage_position_percentile`, `efficiency_position_percentile` | CORE / CONTEXTUAL |
| Positional baselines | **INDEPENDENT** — not documented by LR. Built with sample sizes, standard errors and an explicit ≥9-player suppression rule | `player_positional_baselines.csv`, `position_EPA_sd`, `position_n_players` | CORE |
| Goalie usage / goalie uaEGA | **INDEPENDENT** — goalies are normalized only against goalies; a goalie usage share exists but is never compared to a field player's | — | — |

### 3.4 Reliability and inference

| LR concept | Adaptation | Metric here | Status |
|---|---|---|---|
| Shrinkage of rates | **INDEPENDENT** — acknowledged by LR, not documented. Empirical-Bayes `n/(n+κ)` with exact beta-posterior intervals | `*_reliability`, `*_rate_shrunk`, `*_posterior_ci_width` | CORE / CONTEXTUAL |
| — | **INDEPENDENT**: a closed-form sampling variance for every value component, so "unusual given this player's own volume" is answerable without resampling | `EPA_points_null_sd`, `EPA_points_null_z` | CORE |
| — | **INDEPENDENT**: an explicit cross-position comparability audit, which LR's published material does not attempt | [`CROSS_POSITION_COMPARABILITY.md`](CROSS_POSITION_COMPARABILITY.md) | — |

### 3.5 Team metrics

| LR concept | Adaptation | Metric here | Status |
|---|---|---|---|
| Possession-based efficiency | **REPRODUCED in form, ADAPTED in unit** — points per possession, not goals per possession, because a two-point goal is one goal worth two points | `offensive_efficiency`, `defensive_efficiency` | CORE |
| Goals per possession | **REPRODUCED** — kept explicitly for NCAA comparison | `goals_per_possession` | CORE |
| Efficiency by possession source | **UNSUPPORTED beyond faceoffs** — 922 possessions (21%) have an unconfirmed start mechanism | `faceoff_start_possession_share` only | CORE |
| Clearing / riding efficiency | **UNSUPPORTED** — no clear event; no ride success count | raw counts only | CONTEXTUAL |
| Opponent adjustment | **REFUSED by scope** — LR states EGA is not opponent-adjusted either | — | DEFERRED |

### 3.6 The composite

| LR concept | Adaptation | Metric here | Status |
|---|---|---|---|
| Statistical Tewaaraton | **REFUSED** — explicitly out of scope in Phases 6, 7 **and** 8; a validation check and a test fail if one appears | — | UNSUPPORTED / DO_NOT_USE |

---

## 4. What this project does that Lacrosse Reference does not

1. **PLL two-point scoring, throughout.** Every expectation is in points and a
   two-point attempt carries `P(goal) × 2`. There is no NCAA equivalent, and it
   is the single largest structural difference between the two systems.
2. **Explicit opportunity baselines** with sample sizes and standard errors.
3. **A neutral reference** for the forward-window event values (§2).
4. **Empirical-Bayes identification diagnostics**, which surfaced that 2026
   two-point shooting shows *no measurable between-player skill spread at all*
   — a finding that a point-estimate-only system cannot produce.
5. **A league-sum-to-zero identity** every component satisfies exactly.
6. **A cross-position comparability audit**, and a refusal to publish a
   composite on the strength of it.
7. **A metric catalog** in which every rejected concept is a row with a reason,
   rather than an absence.
8. **Denominators and sample sizes as data on every leaderboard row**, not as
   documentation a chart can be built without reading.

## 5. Where a reader coming from Lacrosse Reference will be surprised

| Expectation | What they will find |
|---|---|
| "EGA" | `EPA_points`, a different estimand (§1). A goal scores highly here. |
| "uaEGA is the player ranking" | Published only as DIAGNOSTIC. The usage adjustment that survives cross-validation adjusts the *variance*, not the mean. |
| "Points = goals + assists" | `scoring_points` is `1PG + 2×2PG` and sums to the final score. Assists are published separately and deliberately unvalued. |
| "Defensive EGA rates defenders" | `defensive_value_partial_raw` — PARTIAL, and 0.0 does not mean average. |
| "There's a Statistical Tewaaraton" | There is not, and the catalog says why. |
| "Two-point shooters can be ranked" | They cannot, from 2026 alone. Production is published; ability is not. |

## Sources

Lacrosse Reference's public methodology posts, as catalogued in
[`EGA_REFERENCE_RESEARCH.md`](EGA_REFERENCE_RESEARCH.md) §Sources and
[`USAGE_ADJUSTMENT_REFERENCE_RESEARCH.md`](USAGE_ADJUSTMENT_REFERENCE_RESEARCH.md)
§Sources. No LR data was used; only their published method descriptions.
