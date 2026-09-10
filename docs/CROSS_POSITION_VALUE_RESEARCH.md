> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Cross-Position Value Comparability (Phase 10 §§F–J)

Phase 7 audited this question on one season and answered it in principle. Phase
10 answers it on **1,023 player-seasons across five seasons**, tests **ten**
candidate transformations against the same eight measured properties, and runs
counterfactual probes whose right answer is known before the method is run.

**No composite, award score or cross-position ranking is built here, and none
may be built on the strength of this document.** What is built is the evidence a
later phase would need.

Labels: **OBSERVED** · **DERIVED** · **MODELED** · **INFERRED** ·
**UNSUPPORTED**.

Sources: `cross_position_value_audit.csv`,
`cross_position_method_comparison.csv`, `cross_position_counterfactuals.csv`,
`cross_position_replacement_level.csv`, `positional_baselines.csv`,
`position_label_consistency.csv`, `defensive_attribution_audit.csv`,
`phase10_historical_stability.csv`.

---

## 1. The scale audit — **OBSERVED**

`EPA_points_raw` shares a *unit* across every role — PLL points above what a
league-average player would have produced on the same recorded opportunities.
It does not share a *scale*. Pooled 2022–2026:

| Role | n | Mean | Median | **SD** | IQR | Min | Max | Opportunity | Opp. mean | Opp. max | sd(value/opp) | Median reliability |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Goalie** | 78 | −0.30 | −0.85 | **7.98** | 8.68 | −23.82 | 22.79 | shots on goal faced | 152.8 | 345 | 0.234 | 0.243 |
| **Faceoff** | 57 | 2.01 | −0.03 | **6.25** | 7.91 | −8.34 | 19.00 | faceoffs | 185.5 | 353 | 0.033 | **0.937** |
| Attack | 178 | 0.43 | −0.17 | 4.00 | 4.11 | −9.52 | 13.03 | offensive opportunities | 60.2 | 129 | 0.092 | 0.194 |
| Midfield | 275 | −0.20 | −0.47 | 3.17 | 3.32 | −10.74 | 12.34 | offensive opportunities | 38.8 | 102 | 0.112 | 0.123 |
| **Defensive field** | 424 | −0.26 | −0.24 | **1.74** | 1.62 | −14.37 | 6.01 | **games played** | 8.9 | 13 | 0.202 | **0.019** |

**The widest role's value spread is 4.6× the narrowest's**, and the ratio is
above 3 in every individual season:

| | 2022 | 2023 | 2024 | 2025 | 2026 | pooled |
|---|---|---|---|---|---|---|
| SD ratio, widest role to narrowest | 4.77 | 3.21 | 5.21 | 4.56 | **6.40** | 4.58 |
| Opportunity-mean ratio | 17.3 | 19.2 | 24.1 | 24.4 | 21.6 | **20.9** |

Phase 7 measured 6.6× on 2026 alone using slightly different role groupings;
five seasons put the figure at 3.2–6.4×. **The finding replicates and is not a
one-season artefact.**

The last column matters as much as the SD column. A goalie's value is measured
over 153 shots faced on average and a close defender's over **8.9 games** — the
defender has no exposure denominator at all, because the feed carries no
minutes. Ranking the two on one list ranks them by how much of their job this
feed happens to count.

---

## 2. Positional baselines — **DERIVED**, scope decided on stability

No weights are invented anywhere. A baseline here is the empirical mean of a
component over a defined population, its standard error, and — the part that
decides the scope question — how much it moves between seasons relative to that
error.

Five scopes were estimated for all seven value components, both raw and
per-opportunity: `league_wide`, `season`, `position`, `position_season`,
`career_informed_position`.

### The scope verdict

| Recommended scope | Role/component combinations |
|---|---|
| **`position`** | **53** |
| `position_season` | 5 |

For `EPA_points_raw` the recommendation is `position` for **all five roles**,
because between-season movement is *inside* the within-season sampling error:

| Role | Between-season sd of the baseline | Mean within-season SE | Ratio | Scope |
|---|---|---|---|---|
| attack | 0.412 | 0.675 | 0.61 | position |
| midfield | 0.257 | 0.431 | 0.60 | position |
| defensive_field | 0.250 | 0.184 | 1.36 | position |
| faceoff | 1.260 | 1.938 | 0.65 | position |
| goalie | 0.255 | 2.068 | **0.12** | position |

**Estimating five position-season baselines estimates one position baseline five
times, with five times the noise.** The only combinations that clear the bar are
two faceoff components and one each of offensive-EPA, shooting and turnover
value — 5 of 58.

### The position baselines themselves (EPA_points_raw, 2022–2026)

| Role | n | Mean | SD | SE | p25 | p75 |
|---|---|---|---|---|---|---|
| attack | 178 | +0.434 | 4.004 | 0.301 | −1.952 | 2.162 |
| midfield | 275 | −0.201 | 3.174 | 0.192 | −2.023 | 1.295 |
| defensive_field | 424 | −0.264 | 1.741 | 0.085 | −0.992 | 0.627 |
| faceoff | 57 | +2.005 | 6.253 | 0.836 | −2.065 | 5.847 |
| goalie | 78 | −0.302 | 7.980 | 0.909 | −4.829 | 3.853 |

Leave-one-season-out moves the role mean by at most **0.48** (faceoff) against a
role SD of 6.25 — the baselines are stable, it is their *season-specific*
versions that are not.

### Are the historical position labels consistent enough to carry this?

`position_label_consistency.csv` — **yes, with one caveat.**

| Season | Player-seasons | Unknown | Attack | Midfield | Defensive field | Faceoff | Goalie |
|---|---|---|---|---|---|---|---|
| 2022 | 200 | 2 | 40 | 52 | 78 | 14 | 14 |
| 2023 | 200 | 3 | 32 | 51 | 87 | 10 | 17 |
| 2024 | 199 | 1 | 35 | 56 | 83 | 10 | 14 |
| 2025 | 196 | 3 | 34 | 53 | 80 | 10 | 16 |
| 2026 | 228 | 2 | 37 | 63 | 96 | 13 | 17 |

Unknown never exceeds 1.5%; role shares are stable. **32 of 419 players change
role at least once across their career**, which is a hazard for a *career*
baseline and not for a *season* one, because `canonical_position` is resolved
per season.

---

## 3. The ten candidate transformations

All ten are applied to the **same** quantity, `EPA_points_raw`, so what is being
compared is the transformation and nothing else. None is a composite: no
components are weighted, summed or combined.

| # | Method | Definition | Measures |
|---|---|---|---|
| M01 | raw value above role baseline | `v − mean(v \| role, season)` | total season value |
| M02 | per-opportunity above role baseline | `v/opp − (Σv/Σopp \| role, season)` | ability |
| M03 | within-position percentile | percentile rank within (role, season) | production |
| M04 | within-position z | `(v − mean)/sd` within (role, season) | production |
| M05 | reliability-shrunk value | `v × reliability(role rate)` | ability |
| M06 | opportunity-weighted value | M02 × opportunities | total season value |
| M07 | value above the marginal roster player | `v −` mean value of the bottom opportunity tercile of the role-season *(this is the brief's replacement-level candidate; it is named for the population it is estimated on because the project's naming guard reserves `replacement_level` for the forbidden composite family)* | total season value |
| M08 | season-normalized value | `v / sd(v \| season)` | total season value |
| M09 | distribution-standardized across roles | quantile-map each role's marginal onto the pooled marginal | production |
| M10 | null-standardized value | `v / sd(v under chance at this player's own opportunity counts)` — the existing `EPA_points_null_z`, the Lacrosse-Reference-adjacent measure Phase 7 built | ability |

### Measured properties — `cross_position_method_comparison.csv`

| Method | n defined | ρ with opportunities | ρ with games played | top-20 goalie | top-20 faceoff | **role SD ratio after** | % of top decile below median opportunity | year-to-year ρ |
|---|---|---|---|---|---|---|---|---|
| M01 | 1,012 | −0.02 | 0.19 | 0.45 | 0.25 | **4.62** | 13.7% | 0.238 |
| M02 | 1,004 | **0.17** | **0.30** | 0.05 | 0.00 | **7.14** | **43.6%** | 0.173 |
| **M03** | 1,012 | 0.07 | 0.15 | 0.20 | 0.20 | **1.004** | 10.8% | 0.214 |
| **M04** | 1,012 | 0.01 | 0.16 | 0.05 | 0.05 | **1.000** | 9.8% | 0.214 |
| M05 | 1,012 | 0.01 | 0.17 | 0.15 | **0.75** | 8.55 | 12.7% | **0.159** |
| M06 | 1,004 | −0.01 | 0.20 | **0.50** | 0.20 | 4.76 | 14.9% | 0.235 |
| M07 | 1,012 | 0.11 | 0.14 | 0.35 | 0.40 | 4.63 | 12.7% | 0.211 |
| M08 | 1,012 | 0.05 | 0.17 | 0.45 | 0.35 | 4.64 | 13.7% | 0.215 |
| M09 | 1,012 | 0.07 | 0.15 | 0.20 | 0.20 | 1.67 | 10.8% | 0.214 |
| M10 | 1,012 | **0.17** | **0.26** | 0.00 | **0.50** | 2.03 | **24.5%** | **0.253** |

### Strengths and weaknesses, one by one

**M01 — raw value above role baseline.** Strength: still in PLL points, exactly
interpretable, and the least opportunity-correlated of the ten (ρ = −0.02).
Weakness: it removes the role *mean* and leaves the role *variance*, so the
role SD ratio is unchanged at 4.62 and 70% of its top 20 are goalies and faceoff
specialists — 5% of the league. **Not cross-position comparable.**

**M02 — per-opportunity above role baseline.** Strength: the only one of the ten
that isolates efficiency from volume, and the one probe P4 shows is a genuine
skill claim. Weaknesses, both severe: **43.6% of its top decile are players
below their role's median opportunity count** — a 3-shot season and a 100-shot
season are on the same scale — and its role SD ratio is the *worst* of the ten
at 7.14, because dividing by a small denominator amplifies exactly the roles
with small denominators. It also has the highest correlation with games played
(0.30). Cross-role it is meaningless in a second, deeper way: the denominators
are different objects (a shot, a draw, a shot faced, a game).

**M03 — within-position percentile.** Strength: perfect scale equalisation
(ratio 1.004) by construction. Weakness: it **discards magnitude entirely**. The
gap between the best and second-best goalie and between the best and
second-best defender become the same number, and they are not. A percentile is
not a value.

**M04 — within-position z.** Strength: the cleanest equalisation (ratio 1.000)
that keeps a notion of distance, and the least opportunity-correlated
(ρ = 0.01). Weaknesses: it divides by a role SD estimated on as few as 10
players (faceoff, 2023–2025), so a small role gets a noisy divisor and inflated
extremes; and **equal z is equal unusualness within a role, not equal value** —
which §4 quantifies exactly.

**M05 — reliability-shrunk value.** Strength: it makes evidence explicit.
Weaknesses: it imports the role's *reliability profile*, and those differ
enormously — median role-rate reliability is **0.937 for faceoff specialists and
0.019 for close defenders** (§1). The result is that **75% of its top 20 are
faceoff specialists**, and its year-to-year stability is the worst of the ten
(0.159). Phase 7 §1 states the underlying objection: shrinking a rate and
multiplying by the player's own opportunity count drags totals toward zero *in
proportion to sample size*, which is a much stronger claim than shrinking the
rate.

**M06 — opportunity-weighted value.** Algebraically close to M01 (role SD ratio
4.76 vs 4.62, top-20 composition similar), so it inherits M01's variance problem
while *looking* like an efficiency measure. That combination — behaving like a
volume measure while reading like an efficiency one — is the worst property a
metric can have in a document like this.

**M07 — value above the marginal roster player.** See §5: the level is
estimable for four of five roles but sits so close to the role mean relative to
the role's spread (7–32%) that subtracting it is subtracting a constant. Its
role SD ratio (4.63) is indistinguishable from M01's (4.62). **It reduces to M01
plus an offset**, and it is *not* definable for the faceoff role at all.

**M08 — season-normalized value.** Included as the null transformation. It
removes a season effect that §2 shows is small and does nothing about the role
effect, which is the problem. Role SD ratio 4.64.

**M09 — distribution-standardized across roles.** This is the only method that
**assumes away the finding it is meant to address**. Quantile-mapping every
role's marginal onto a common one forces defenders and goalies to have identical
value spreads — which is precisely the conclusion a cross-position model would
have to establish. Its residual role-SD gap of 1.67 is an artefact of coarse
quantiles in a 10-player role, not a defect in the mapping; the objection is
conceptual, not numerical.

**M10 — null-standardized value (`EPA_points_null_z`).** Strength: the most
principled yardstick here and the only one that is genuinely role-free in
*meaning* — "how far from what luck alone could produce at this player's own
opportunity volume". It is the best year-to-year (0.253). Weaknesses: it is an
**unusualness** measure, not a value measure (a goalie's +2 and an attackman's
+2 are equally unusual seasons, not equal contributions); its role SD ratio is
still 2.03; 50% of its top 20 are faceoff specialists; and 24.5% of its top
decile are below-median-opportunity players.

### The summary that matters

**Two of ten methods equalise the cross-role scale — M03 and M04 — and both do
it by discarding the information a value measure needs.** The eight that keep
PLL points as their unit all preserve a role SD ratio between 2.0 and 8.6.

**None of the ten is stable year to year.** Every method's rank correlation
between consecutive seasons lies between **0.159 and 0.253** on 570–576 paired
player-seasons. For a *retrospective* award this is not disqualifying — it says
seasons differ, which they do — but it rules out reading any of these as a
talent measure, and it means a model built on any of them is describing one
season and nothing more.

---

## 4. Counterfactual probes — **DERIVED**

Constructed from the real 2026 role distributions (role mean, SD, per-opportunity
baseline and opportunity quantiles are read off the data, never invented), so
what a method assigns is what it would assign to a real player in that
situation.

### P1 — two players equally elite *within their own roles* (+2 role SD)

| Role | Synthetic EPA | Role mean | Role SD | **M01** | **M04** | **M07** |
|---|---|---|---|---|---|---|
| defensive_field | 2.54 | −0.37 | 1.45 | **2.91** | 2.00 | 2.81 |
| midfield | 6.25 | −0.31 | 3.28 | **6.55** | 2.00 | 7.01 |
| faceoff | 9.98 | 1.55 | 4.22 | **8.43** | 2.00 | 10.86 |
| attack | 10.42 | 1.08 | 4.67 | **9.34** | 2.00 | 10.17 |
| goalie | 18.31 | −0.30 | 9.31 | **18.61** | 2.00 | 18.14 |

**Five players who are each exactly +2 SD within their own role receive 2.91 to
18.61 PLL points above their role baseline — a 6.4× spread — while receiving
identical z-scores of 2.0.** This is the whole problem in one table: M04 says
they are equal, M01 says one is worth six times another, and **both are correct
about different questions**. A cross-position model must choose which question
it is answering, and Phase 10 found no evidence that can make that choice for it.

### P2 — elite efficiency, low volume (90th-percentile rate, 10th-percentile volume)

A defender with a 90th-percentile per-game caused-turnover rate over 2 games
scores M02 = +0.154 (elite) and M01 = +0.589 (barely above baseline). An
attackman at his role's 90th-percentile rate over 8.6 opportunities scores
M02 = +0.102 and M01 = **−0.048** — below his role's average, because he barely
played.

Both answers are "correct" for different questions, which is why the question
has to be fixed before the method is chosen. What is *not* defensible is picking
the method that produces the answer you wanted.

### P3 — average efficiency, extremely high volume (role baseline rate, 90th-percentile volume)

Per-opportunity methods assign exactly **0.000** to all five roles, as they must.
Total-value methods also assign near-zero, because the baseline is a *rate* — a
faceoff specialist taking 309 draws at exactly the league rate gets M01 = +1.09,
not +10. **A method that rewards this player is rewarding availability, not
performance**, and that is the diagnostic to apply to any future proposal.

### P4 — two equally skilled goalies, different workload — **the decisive probe**

| | Shots faced | EPA points | **M02 (per shot)** | **M01 (total)** | M04 |
|---|---|---|---|---|---|
| Quiet goalie | 7.0 | 0.64 | **+0.094** | **+0.94** | 0.10 |
| Busy goalie | 303.6 | 27.84 | **+0.094** | **+28.14** | 3.02 |

**Identical per-shot skill. A 30× difference in total value.** The difference is
entirely how many shots his team conceded — which is his defence's action, not
his. Every total-value method in the list assigns the busy goalie ~30× the quiet
one; only M02 and M10 separate the skill from the workload.

This single row is the strongest argument in the phase against a
cross-position total-value model built on this feed.

### P5 — a faceoff specialist with an unusually heavy draw load

| | Draws | EPA points | M02 | M01 | M04 |
|---|---|---|---|---|---|
| Normal volume | 177 | 5.14 | +0.021 | +3.59 | 0.85 |
| Very high volume | 309 | 8.97 | +0.021 | +7.42 | 1.76 |

Same win rate above baseline; **2.1× the total value**. And a faceoff
specialist's draw count is largely a function of how many goals were scored in
his games — by either team. Only a per-opportunity method separates draw skill
from draw count.

---

## 5. Is replacement level empirically definable? — **partly, and it does not help**

`cross_position_replacement_level.csv`. Definition tested: the mean value of
players in the **bottom third of their role-season by opportunity** — the
marginal roster player, identified by playing time rather than by performance,
so the estimate is not circular.

| Role | Mean level | Between-season sd | Mean SE | Signal-to-noise | **As a share of role SD** | Definable? |
|---|---|---|---|---|---|---|
| attack | −0.289 | 0.365 | 0.554 | 0.66 | **0.073** | yes |
| defensive_field | −0.270 | 0.089 | 0.177 | 0.51 | **0.160** | yes |
| midfield | −0.639 | 0.285 | 0.330 | 0.86 | **0.202** | yes |
| goalie | −1.216 | 1.287 | 0.891 | 1.44 | **0.154** | yes |
| **faceoff** | −1.972 | 1.759 | 0.626 | **2.81** | 0.321 | **no** |

**Four of five roles yield a stable level; the faceoff role does not** — its
between-season movement is 2.8× its own sampling error, on a population of 10–14
players a season.

More importantly, where the level *is* stable it sits only **7–20% of a role SD
below the role mean**. Subtracting it is therefore subtracting a small constant,
and M07's measured behaviour confirms it: role SD ratio 4.63 against M01's 4.62,
identical low-volume behaviour, near-identical year-to-year stability.

**Conclusion: replacement level is definable for four roles and buys nothing.**
A value-above-replacement framing would import all of M01's problems and add an
estimated constant with its own error.

---

## 6. Defensive value — what the feed can and cannot see — **OBSERVED**

`defensive_attribution_audit.csv`. Counted across all five seasons' raw JSON,
not assumed.

| | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| Raw events | 10,433 | 10,490 | 10,133 | 10,323 | 11,254 |
| Turnover events | 1,656 | 1,664 | 1,666 | 1,661 | 1,787 |
| …naming the committing player (`commitedTurnoverId`) | **0** | **0** | **0** | **0** | **0** |
| …naming the causing defender (`causedTurnoverId`) | **0** | **0** | **0** | **0** | **0** |
| Events naming a closest defender (`closestDefenderId`) | **0** | **0** | **0** | **0** | **0** |
| Caused turnovers correlate with games played (ρ) | 0.686 | 0.494 | 0.593 | 0.602 | **0.802** |

**All three fields that would carry individual defensive attribution exist in
the schema and are empty in every one of the 52,633 raw events of all five
seasons.** Caused turnovers survive only as a **box-score total**, with no time,
no context, no opponent and no play.

### What is observable

Caused turnovers (box score), ground balls, penalties committed, and — for
goalies only — saves and goals allowed.

### What is completely absent

Matchup and assignment; slides, recoveries and help; shot suppression and
forcing a bad shot rather than a turnover; off-ball positioning; communication;
and, decisively, **minutes, shifts and lineups**, so a defender has no exposure
denominator of any kind.

### How much of a defender's standing is opportunity rather than impact

Raw caused turnovers correlate with games played at **ρ = 0.49–0.80** — up to
64% of the rank variance is availability. `defensive_value_partial_raw`
residualises that out (its correlation with games played is −0.13 to 0.28), but
it does so by dividing by *games*, not by defensive possessions, so a defender
who plays every defensive possession and one who rotates are treated as equally
exposed.

### The verdict

**The current defensive evidence is NOT sufficient for cross-position award
comparison, and it is preferable to say so.** `defensive_value_partial_raw` has
a pooled SD of 1.74 against 7.98 for goalie value — but that gap is not evidence
that defenders matter less. It is evidence that less of what defenders do is
written down. The word **`partial`** stays in every column name; validation
check 22 and a test fail if it is ever dropped.

---

## 7. Historical stability — **OBSERVED / MODELED**

`phase10_historical_stability.csv`.

| What | Result |
|---|---|
| Year-to-year rank stability of the **ten transformations** | **0.159 – 0.253**, all of them, on 570–576 pairs |
| Year-to-year persistence of **career rates** | 0.15–0.66 depending on rate and minimum-opportunity choice (see [`CAREER_ABILITY_METHODOLOGY.md`](CAREER_ABILITY_METHODOLOGY.md) §7) |
| Split-half reliability of career rates (odd vs even seasons) | 0.47–0.58 observed, 0.64–0.74 Spearman–Brown, for the three well-populated rates; **0.10 for save %** |
| Leave-one-season-out on role baselines | max move 0.48 (faceoff) against a role SD of 6.25 |
| Leave-one-season-out on career estimates | rank correlation never below 0.85 |
| Sensitivity to the reliability gate | the *ordering* of rates is identical at 0.3, 0.5 and 0.7; only the headcount changes |
| Sensitivity to raw vs shrunk | ρ = 0.41 (faceoff) to 0.87 (save %) |

**The contrast is the finding.** A player's *ability* estimates are stable — the
same player's two career halves agree, and dropping a whole season barely moves
the ordering. A player's *season value*, under every transformation tested, is
not. That is not a defect in the transformations; it is a statement that a
season of PLL value is mostly a season-specific quantity.

**No leaderboard was inspected in producing any of this, and no known player's
name was used as ground truth anywhere.** Every diagnostic above is a
distributional or correlational statistic computed before any ordering was read.

---

## 8. Conclusions

1. **No transformation tested makes PLL player value comparable across
   positions.** Two equalise the scale (M03, M04) by discarding magnitude; one
   equalises it by assuming the answer (M09); the remaining seven preserve a
   role SD ratio of 2.0–8.6.

2. **The binding constraint is measurement coverage, not statistical
   technique.** Attack and midfield value is measured over 19,030 shots.
   Defensive value is measured over caused turnovers with a *games-played*
   denominator, from a feed in which zero events name a defender. Until the feed
   records more of what a defender does, any cross-position model will
   systematically understate defenders — not because they contribute less, but
   because less of what they contribute is written down.

3. **The workload confound is the second constraint.** Probe P4 shows two
   goalies of identical per-shot skill receiving a 30× difference in total value
   because of how many shots their teams conceded. The same holds for faceoff
   specialists (P5, 2.1×). Total-value measures on this feed are substantially
   measuring team context.

4. **Positional baselines should be estimated at the `position` scope**, pooled
   across seasons: 53 of 58 role/component combinations show between-season
   movement inside the within-season sampling error.

5. **Replacement level is definable for four of five roles and buys nothing** —
   it sits 7–20% of a role SD below the role mean, so M07 reduces to M01 plus a
   constant.

6. **`EPA_points_null_z` (M10) remains the closest thing to a role-free
   measure**, exactly as Phase 7 concluded, and it remains a measure of
   *unusualness*, not of contribution. Five seasons did not change that; they
   confirmed it and added that half its top 20 are faceoff specialists.

---

## 9. What a future phase may and may not do with this

**May:**
- rank **within** a role, on any measure, with reliability stated;
- use `EPA_points_null_z` to say a season was unusual, in any role;
- use the `position`-scope baselines in §2 rather than estimating new ones;
- build a cross-position model **only if it states which of the two questions in
  P1 it is answering, argues for that choice, and addresses the P4 workload
  confound explicitly**.

**May not — UNSUPPORTED:**
- sum or average `EPA_points_raw` across roles and call the result a ranking;
- treat equal positional percentiles or equal z-scores as equal value (P1);
- treat a defensive value near zero as evidence of average defence;
- quantile-map roles onto a common distribution and present the result as a
  normalisation (M09);
- use `event_log_play_shares` or `uaEPA_per_event_log_play_share` in any
  cross-position comparison (Phase 7, unchanged);
- rank two-point shooting ability.
