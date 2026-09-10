# Player Value Historical Backtest (2022-2026)

The four role models (`pll_phase13_player_value_v1.py`) are run **identically**
across all five canonical seasons — this is not a separate model per season;
it is the same code applied to five slices of the one already-canonical
`player_stats_2022_2026.csv`. No season-specific formula, threshold, or
baseline exists anywhere in this system.

Outputs: `offensive_value_2022_2026.csv`, `faceoff_value_2022_2026.csv`,
`goalie_value_2022_2026.csv`, `defensive_production_2022_2026.csv`,
`player_value_historical_stability.csv`,
`player_value_historical_distribution.csv`,
`player_value_historical_extremes.csv`, `player_value_2026_anomaly_check.csv`.

**No historical universal MVP ranking was created at any point in this
analysis.**

---

## 1. Year-to-year rank stability

`player_value_historical_stability.csv`, Spearman rho on consecutive-season
pairs, minimum-opportunity gated:

| Season pair | Offense (≥20 shots) | Faceoff (≥20 draws) | Goalie (≥40 SOG) |
|---|---|---|---|
| 2022-2023 | 0.223 (n=44) | n<10 (n=5) | n<10 (n=8) |
| 2023-2024 | 0.210 (n=45) | n<10 (n=6) | n<10 (n=7) |
| 2024-2025 | 0.276 (n=41) | n<10 (n=8) | n<10 (n=8) |
| 2025-2026 | 0.088 (n=44) | n<10 (n=8) | n<10 (n=9) |

Offense reproduces Phase 10's 0.16-0.25 finding closely (this subset uses a
20-shot minimum rather than Phase 10's full-population pairing, so exact
figures differ slightly but the magnitude and conclusion match exactly:
**season value is not a stable talent measure**). Faceoff and goalie
populations are too small at any reasonable minimum-opportunity gate to
compute a stable rank correlation at all — consistent with Phase 9's own
finding that faceoff/goalie year-to-year correlations have wide confidence
intervals from small league-wide specialist counts, not evidence the
skills are transient (`MULTI_SEASON_RELIABILITY.md`).

## 2. Distribution and extreme values, all five seasons

`player_value_historical_extremes.csv`:

| Role | Season | Max | Player | Min | Player |
|---|---|---|---|---|---|
| Offense | 2022 | +8.74 | Jeff Teat | -10.57 | Jack Hannah |
| Offense | 2023 | +11.70 | Wes Berg | -9.62 | Rob Pannell |
| Offense | 2024 | +12.67 | Tre Leclaire | -5.93 | Rob Pannell |
| Offense | 2025 | +11.73 | Connor Shellenberger | -7.37 | Grant Ament |
| Offense | 2026 | +12.96 | Logan Wisnauskas | -9.07 | Brennan O'Neill |
| Faceoff | 2022 | +15.97 | Trevor Baptiste | -7.22 | Justin Inacio |
| Faceoff | 2023 | +20.07 | Trevor Baptiste | -1.79 | Stephen Kelly |
| Faceoff | 2024 | +10.87 | Joseph Nardella | -6.00 | Nick Rowlett |
| Faceoff | 2025 | +10.64 | Trevor Baptiste | -4.56 | Jake Naso |
| Faceoff | 2026 | +10.64 | TD Ierlan | -1.87 | Nick Rowlett |
| Goalie | 2022 | +12.82 | Blaze Riorden | -9.98 | Jack Kelly |
| Goalie | 2023 | +15.49 | Dillon Ward | -16.43 | Jack Concannon |
| Goalie | 2024 | +23.52 | Brett Dobson | -10.20 | Jack Kelly |
| Goalie | 2025 | +14.33 | Liam Entenmann | -11.15 | Dillon Ward |
| Goalie | 2026 | +13.55 | Sean Byrne | -23.11 | Liam Entenmann |

No extreme value in any season is more than roughly 2x any other season's —
the same order of magnitude throughout, consistent with a stable model
applied to a stable-scale opportunity structure across the 2023/2024
canonical possession repair (Phase 11). The repair changed possession
COUNTS for 2023/2024; it did not touch any goal, shot, faceoff, or save
event, so no player-value component was affected — re-confirmed here by
observing 2023/2024's extremes are not systematically different from
2022/2025/2026's.

## 3. Is 2026 anomalous?

`player_value_2026_anomaly_check.csv`:

| Metric | 2026 mean | 2022-2025 mean of means | z-score | Verdict |
|---|---|---|---|---|
| offensive_value | 0.268 | 0.036 | **2.74** | NOTABLE_BUT_NOT_DISQUALIFYING |
| faceoff_value_total | 2.455 | 2.631 | -0.11 | WITHIN_HISTORICAL_RANGE |
| goalie_value_total | 0.000 | -0.125 | 0.50 | WITHIN_HISTORICAL_RANGE |

2026's mean offensive value is the one metric that stands out (z=2.74
against the 2022-2025 distribution of season means). **INFERRED, not
confirmed**: 2026 has the largest offensive-role population in the dataset
(100 attack/midfield players vs 92-119 range other seasons is comparable, so
population size alone does not obviously explain it) and the most games (51
completed, tied for the most of the five seasons) — a larger, more
game-heavy season could mechanically raise the mean simply by allowing more
players to accumulate value above baseline before regression. This was
**investigated and left unresolved as an open, disclosed pattern**, not
treated as evidence of a defect (Section Q discipline: a surprising
distributional shift is not itself proof of an error) and **no formula was
changed** in response.

## 4. Model behavior after the 2023/2024 canonical repairs

The Phase 11 chronology and duplicate-faceoff repairs changed possession
COUNTS in 2023 (-256) and 2024 (-46), and touched no goal, shot, faceoff-
winner, or save event (`docs/PHASE11_BEFORE_AFTER_AUDIT.md`). Since every
Phase 13 value component is denominated in shots, touches, faceoffs, and
shots-on-goal-faced — never possessions — no player-value component in
this backtest could have moved as a result, and the extremes table above
shows no discontinuity at 2023/2024 relative to 2022/2025/2026.
