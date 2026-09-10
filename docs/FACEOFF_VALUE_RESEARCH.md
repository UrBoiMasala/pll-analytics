# Faceoff Value Research (Phase 12 §G)

Faceoff is the cleanest identified skill in this project and simultaneously
the clearest example of a workload confound in a total-value metric. Both
findings are quantified here, reusing Phase 6/7/10 evidence and adding one
new counterfactual test.

Labels: **OBSERVED** · **DERIVED** · **MODELED** · **INFERRED** ·
**UNSUPPORTED**.

---

## 1. Every component, validated

**Is a faceoff win equivalent to creating one possession?** No —
`PLAYER_VALUE_ACCOUNTING.md` §4F states the counterfactual precisely: the
alternative to this player winning is a *league-average faceoff man* winning
at 49.656%, not the team forfeiting the ball. `faceoff_value_raw = (wins -
faceoffs × 0.49656) × coefficient`, so a specialist winning exactly at the
league rate scores exactly zero. This is the correct baseline — a faceoff
win is a win **above expectation**, not a possession created from nothing.

**What happens after faceoff losses?** They start the opponent's possession;
this is already fully reflected in the win-rate-above-expectation framing
(a loss is the complement of a win, and both sides of the league-wide
ledger are the same players' own faceoffs).

**Does possession value depend materially on team/context?**
`OPPONENT_ADJUSTMENT_FEASIBILITY.md` found the schedule effectively
balanced (connectivity 1.00 every season, SoS spread 14-29% of team spread)
— team-level context is a minor factor for faceoff value specifically, more
so than for offense or defense generally.

**Should ground-ball recovery be separately credited?** **No —
already decided, and the reason is a double-counting finding**: 1,095 of the
season's 3,091 ground balls (2026) immediately follow a faceoff, and 99.7% go
to the faceoff-winning team, **61.5% to the faceoff winner himself**. A
per-ground-ball credit would pay the specialist a second time for the same
draw. `player_value_signal_inventory.csv` flags `ground_balls`
`double_counting_with: faceoff_value_raw (OVERLAPPING_OPPORTUNITY_DEFERRED)`.

**Are FOGO opportunities measured sufficiently well?** Yes as a count
(`faceoffs`), but the count itself is confounded with team context — see §2.

**Is faceoff value additive with offensive value?** Yes, exactly — both are
components of `EPA_points_raw`, on disjoint opportunity sets (a faceoff is
never also a shot). Verified in `player_value_metric_dependency.csv`
(`ACCOUNTING_IDENTITY` rows).

## 2. The decisive workload confound

Counterfactual `T4_same_faceoff_rate_different_draw_volume`
(`player_value_counterfactual_tests.csv`), constructed from the real 2026
faceoff-role distribution: two specialists at the **identical** win rate
above baseline (+0.05), at 10th- vs 90th-percentile draw volume, differ in
total `faceoff_value_raw` by construction (mechanically expected, and
confirmed) — reproducing Phase 10's counterfactual P5 (2.1x total-value swing
at equal rate) on the canonical dataset. And a specialist's draw count is
largely a function of how many goals were scored in his games, by either
team — not his own skill.

## 3. Career reliability — the cleanest in the project

`career_ability_reliability.csv`: κ = 10.42 draws (against 77-495 for every
other identifiable rate), implied true between-player sd **0.148** — three
to seven times any other conversion rate's. 54.4% of career takers (56 of
103) clear reliability 0.5, the highest-clearing contest-outcome rate.

## 4. Can faceoff value share a common expected-points scale with offense?

**Mathematically yes** (both are PLL-point residuals against a league
baseline, disjoint opportunity sets, verified additive). **Practically no**
as a cross-role RANKING basis: `cross_position_value_audit.csv` puts faceoff
value's SD at 6.25, offense's at 3.17-4.00, with opportunity means 20x apart.
Counterfactual P1 (Phase 10, reused): a faceoff specialist and an attackman
each exactly +2 SD within their own role receive 9.98 and 10.42 raw PLL
points respectively (similar magnitude in this particular pairing, but the
z-to-magnitude mapping the *method* implies is not consistent across roles
in general — see the full P1 table in `CROSS_POSITION_VALUE_RESEARCH.md`).

## 5. Verdict

**MF3_faceoff_above_baseline is VIABLE_WITH_CAVEAT.** Within-role ranking on
`faceoff_value_raw`, gated by reliability, is defensible — this is the
single best-identified skill in the project. The workload confound (§2) must
be disclosed alongside any ranking: a specialist given more draws (by his
coaches, or by how many goals were scored in his games) accrues more total
value at an identical rate, and a reader must be told this is what
`faceoff_value_raw`'s total measures. `MF6_statistical_fogo_of_the_year` is
**VIABLE_WITH_CAVEAT** for the same reason.
