> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Award-Model Input Readiness (Phase 10 §K)

An explicit assessment of every candidate **input** to a future PLL Statistical
Tewaaraton. **No such model exists, none is built here, and this document does
not propose weights, a formula or a ranking.** It classifies inputs and says
what the evidence supports.

Source: `mvp_input_readiness.csv`, `phase10_measurement_scope.csv`. Every
classification is derived from a number produced elsewhere in Phase 10 and read
back out of the published CSV at run time, so the table cannot drift from its
evidence. Validation check 18 fails if a row lacks a supporting statistic, a
justification, a caveat, or an evidence file that exists on disk.

---

## The five classes

| Class | Meaning |
|---|---|
| **READY** | measured, reproducible, comparable across the population it would be applied to, and stable enough to mean the same thing in two different seasons |
| **READY_WITH_CAVEAT** | the same, but carrying a limitation that must travel with the number and be stated wherever it is used |
| **EXPERIMENTAL** | defensible to compute and inspect; not defensible as a load-bearing input until a stated question is answered |
| **NOT_COMPARABLE** | real and correctly measured, but not on a scale that can be set beside another player's without a transformation Phase 10 could not justify |
| **UNSUPPORTED** | the data do not identify the quantity at all; any value produced would be an artefact of the estimator |

---

## The table

| Input | Class | Supporting statistic |
|---|---|---|
| **scoring_production** | **READY** | PLL points reconcile exactly to the official final score in every eligible team-game in all five seasons (Phase 9 check 7; one documented exception) |
| **availability_games_played** | **READY** | every candidate cross-position transformation correlates with games played at ρ 0.14–0.30 |
| **shooting_value** | READY_WITH_CAVEAT | single-season κ 70.8 shots; 13 of 192 players clear reliability 0.5; league components sum to zero to 10 decimal places |
| **turnover_value** | READY_WITH_CAVEAT | career κ 138.0 touches; **218 of 419 players (52.0%)** clear the gate — the highest count of any rate |
| **career_ability** | READY_WITH_CAVEAT | 239 of 419 players reach reliability 0.5 on at least one rate; leave-one-season-out rank correlation never below 0.84 |
| **possession_efficiency** | READY_WITH_CAVEAT | 2023 moves 96.96 → 91.39 possessions/game and 0.2520 → 0.2674 points/possession under the evidence-bounded repair; 2022, 2025, 2026 bit-identical |
| **two_point_production** | READY_WITH_CAVEAT | 2,465 career attempts across 271 shooters; the league two-point return is **+0.0004** points per attempt against the one-point shot over five seasons |
| **usage** | READY_WITH_CAVEAT | the constant model still wins cross-validation on 844 player-seasons with folds cut by player; usage/offensive-EPA correlation is negative in four of five seasons |
| **opponent_adjustment** | EXPERIMENTAL | schedule connectivity 1.00 every season, but SoS spread is 15–29% of between-team spread and the adjustment moves ranks by ≤ 2 places |
| **faceoff_value** | **NOT_COMPARABLE** | career κ 10.4 draws — 5–7× smaller than any other rate's — 54.4% of takers clear the gate, implied true sd 0.148 |
| **goalie_value** | **NOT_COMPARABLE** | career κ 495 shots on goal; 8 of 27 goalies clear the gate; pooled EPA sd 7.98 for goalies against 1.74 for close defenders (4.6×) |
| **defensive_value_partial** | **NOT_COMPARABLE** | across five seasons, 8,434 turnover events carry **0** causing-defender ids and **0** closest-defender ids; caused turnovers correlate with games played at ρ 0.64 |
| **positional_normalization** | **NOT_COMPARABLE** | role EPA sds differ by 4.6× pooled (3.2–6.4× by season) and role opportunity means by 21×; five players each +2 SD within their own role receive **2.91 to 18.61** points above their role baseline while receiving identical z-scores of 2.0 |
| **two_point_ability** | **UNSUPPORTED** | career: 271 shooters, 2,465 attempts, median 3; observed between-player variance 0.010224 is **below** binomial noise 0.013711 (excess −0.003487); prior capped at 1e6; max reliability 0.000110 |

**Counts: 2 READY · 6 READY_WITH_CAVEAT · 1 EXPERIMENTAL · 4 NOT_COMPARABLE ·
1 UNSUPPORTED.**

---

## The caveats that must travel with each input

These are not footnotes. Each one changes what the number means.

- **scoring_production** — it is production, not ability, and it is not
  comparable across roles: a goalie's scoring production is zero by job
  description.
- **shooting_value** — a single season's is dominated by conversion luck.
  Replacing the shooting component with its shrunk equivalent moves **219 of 228
  total-value ranks** (Phase 7).
- **turnover_value** — roughly **19%** of the league's turnovers name only a
  team, so every player's absolute count is understated. The ratio is internally
  consistent; the level is not the official level.
- **career_ability** — answers "how good has this player been across 2022–2026",
  not "how good is he now". Ageing, role change and team context are modelled
  nowhere. 44 players changed listed position and 97 changed team inside the
  window.
- **possession_efficiency** — the repair is published as
  `possessions_repaired.csv`; the frozen `possessions.csv` is unchanged, so any
  comparison **must state which layer it used**. 91 of 2023's goals still have
  no faceoff after them, against 39 in 2026.
- **two_point_production** — must never be presented as, or silently converted
  into, two-point *ability*.
- **usage** — it is **not** the share of team possessions a player was on the
  field for. The feed carries no lineup, shift or minutes data in any season.
- **availability_games_played** — READY as a *denominator* and as a disclosure,
  not as a value input. Every season-total measure already rewards availability
  implicitly; adding it counts durability twice.
- **faceoff_value** — NULL for roughly four players in five. A model that treats
  a NULL faceoff value as zero is asserting that not taking draws is exactly
  average at taking them.
- **goalie_value** — driven substantially by how many shots the team conceded.
  Counterfactual P4: two goalies of **identical per-shot skill** receive +0.94
  and +28.14 points above the role baseline.
- **defensive_value_partial** — `partial` must stay in the name. 0.0 means
  "caused turnovers at his group's per-game rate, everything else unmeasured",
  **not** "an average defender".
- **positional_normalization** — the baseline scope question is settled (53 of
  58 role/component combinations recommend a `position` baseline, not a
  `position-season` one), but standardisation removes the group effect without
  establishing equal value.
- **opponent_adjustment** — there is no *player-level* opponent adjustment
  anywhere: the feed carries no matchup data, so "who did this attackman score
  against" is unanswerable at the defender level.
- **two_point_ability** — `INDIVIDUAL_TWO_POINT_ABILITY = UNSUPPORTED /
  DO_NOT_USE`.

---

## What a PLL Statistical Tewaaraton could actually measure

`phase10_measurement_scope.csv`, answers `CAN_MEASURE_1` … `_4`.

1. **Production, exactly.** Every point, goal, shot, save, draw, ground ball and
   caused turnover the league recorded is attributable and reconciles to the
   official box score. Phase 9 check 7 re-derives PLL points from valid goal
   events and matches the official score in every eligible team-game of five
   seasons, with one documented exception.

2. **Value above a league-average player on the SAME recorded opportunities,
   within a role.** The residual accounting sums to exactly 0 across the league
   by construction, and no component double-counts another — each is defined
   over a disjoint opportunity set (shots, touches, draws, games, shots on goal
   faced).

3. **Underlying ability — at career scope, for six rates, for a minority of
   players.** Career reliability ≥ 0.5 is reached by 54% of faceoff takers, 52%
   on turnovers per touch, 29% of goalies, 21% on shot accuracy, 17% of shooters
   and 13% on one-point conversion. Two-point *usage* reaches 85%.

4. **Rank within a role**, with an honest statement of how much evidence stands
   behind each rank.

---

## What it could NOT measure

`phase10_measurement_scope.csv`, answers `CANNOT_MEASURE_1` … `_6`.

1. **Defence, beyond caused turnovers.** No event in any season names a causing
   defender or a closest defender — 0 of 52,633 raw events. There is no minutes,
   shift or lineup data, so a defender has no exposure denominator, and slides,
   matchups, help, shot suppression and off-ball positioning are entirely
   absent.

2. **Playing time.** Every rate in this project is denominated in countable
   events, never in seconds on the field.

3. **Creation as distinct from finishing.** Assists exist as a box-score count,
   but crediting them would value the same goal twice, so shooting value is
   finishing only. Off-ball movement, the dodge that draws a slide, and the pass
   before the assist are unrecorded.

4. **Cross-position value.** Roles are measured over opportunity counts that
   differ by 21×, and no transformation tested converts that into a common value
   scale without assuming the answer.

5. **Two-point shooting ability.** Five seasons and a career aggregation all
   return between-player variance *below* binomial noise.

6. **Anything durable about a season's total value.** All ten cross-position
   transformations have a year-to-year rank correlation between **0.159 and
   0.253** on 570–576 paired player-seasons. For a retrospective award this is
   not disqualifying — seasons differ — but it rules out reading any of them as
   a talent measure.

---

## The summary judgement

> The binding constraint on a cross-position award model is **not statistical
> technique**. It is **measurement coverage**: attack and midfield value is
> measured over 19,030 shots; defensive value is measured over caused turnovers
> with a games-played denominator, from a feed in which zero events name a
> defender.

A defensible PLL award model is buildable **within a role** today. A defensible
**cross-role** one is not, and Phase 10 found no transformation that changes
that. The honest options for a future phase are: publish per-role awards; or
publish a cross-role model that states its positional value assumption as an
assumption, in the open, and reports how much the answer moves when it changes.

---

## What Phase 10 explicitly did NOT build

No Statistical Tewaaraton. No MVP score. No MVP leaderboard. No WAR. No
replacement-level composite. No award score. No fantasy score. No cross-position
composite ranking. Nothing under another name.

Enforced by:

- `pll_validate_phase10.py` check 22 — scans every Phase 10 and pooled column
  name for eight forbidden patterns, asserts no cross-position file is keyed by
  player, asserts this readiness table carries **no numeric column at all**
  (it classifies, it never scores), and asserts the career table carries no
  summary value;
- `pll_validate_phase9.py` check 19 — unchanged, still passing;
- `tests/test_phase10.py::TestNoCompositeArtifactExists` — five tests, including
  one that fails if any per-player file ever publishes one of the ten
  cross-position transformation values, and one that greps the Phase 10 source
  for an award/composite entry point;
- `tests/test_history.py::TestNoCompositeAnywhere` — unchanged, still passing.
