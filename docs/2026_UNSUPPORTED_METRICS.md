# Unsupported and Deferred Metrics — 2026

Fourteen metrics that a reader might reasonably expect, and that this project
does **not** publish. Each entry says what it would be, why it is tempting, what
specifically blocks it, and what would unblock it.

A metric absent from a statistical system with no explanation is
indistinguishable from an oversight. That is why every one of these is a row in
`metric_catalog_2026.csv` with a `publication_status` and a stated reason, and
why `pll_metric_catalog.py` refuses to import a catalog containing an
UNSUPPORTED or DEFERRED metric whose reason is shorter than a sentence.

**Two statuses:**

- **UNSUPPORTED** (8) — cannot be built from this feed, and would mislead if
  faked.
- **DEFERRED** (6) — wanted, not currently supportable; the missing input is
  named.

Validation check 18 fails if any of them ever appears as a published column or
on a leaderboard.

---

## Group 1 — The composite

### `statistical_tewaaraton_or_mvp_composite` · UNSUPPORTED · DO_NOT_USE

An overall player score: a weighted combination of the value components across
positions.

**Tempting because** every component is already in the same unit — PLL points
above expectation — and a weighted sum is one line of SQL.

**The blocker is not arithmetic; it is meaning.** The unit is shared; the scale
is not. The observed spread of `EPA_points_raw` differs by 6.6× across roles
(goalie sd 9.59, defensive field 1.46), because a goalie faces 150–330 valued
events and a defensive midfielder's only valued defensive act is a caused
turnover. The one class-A value-adjacent metric in the system
(`EPA_points_null_z`) measures *unusualness*, not contribution. Positional
percentiles remove the group effect without creating comparability of value:
being the 90th-percentile goalie and the 90th-percentile attackman are not the
same amount of anything.

A cross-position weighting is a **judgement** that has to be argued for in the
open. No metric in this system supplies one, and Phase 8 declined to invent one.

**What is published instead:** category leaders, within-role rankings, and
`position_rank` on every leaderboard row.

**What would unblock it:** an explicit, defended argument about cross-position
weights — not more data. This is a values question wearing a statistics costume.

> No composite, award score, WAR, replacement level or cross-position ranking
> exists anywhere in this repository. Validation check 19 scans five published
> surfaces for the forbidden patterns; `tests/test_phase8.py` fails if one
> appears.

---

## Group 2 — Blocked by a missing field in the feed

### `shot_quality_model` (expected goals) · UNSUPPORTED · DO_NOT_USE

**Tempting because** expected-goals models are the standard advanced shooting
metric in every comparable sport.

**Blocker:** shot events carry **no location, no distance and no defender** in
any of the 51 raw games. The only populated detail keys are `shotOnGoal`,
`shotSaved` and `saveType`. A richer model *was* fitted on what remains — shot
class plus game state — and **lost** on 5-fold cross-validated Brier score to the
simple two-class empirical rate. An earlier version appeared to win by 2.1%, and
that was **target leakage**: PLL's score columns already include the goal on the
row itself.

**Unblocked by:** shot coordinates.

### `true_possession_participation` · UNSUPPORTED · DO_NOT_USE

The share of team possessions a player was actually on the field for — the
correct denominator for almost every player rate.

**Blocker:** the PLL feed carries **no lineup, substitution, shift or minutes
data of any kind**, verified across all 51 raw games. Every usage measure in this
project is an individual action count and says so on its own row. Two validation
checks and two tests scan for a possession- or duration-denominated player column
and fail if one appears.

**Unblocked by:** lineup or shift data.

### `riding_efficiency` · UNSUPPORTED · DO_NOT_USE

**Tempting because** `rideAttempts` is published and looks like half of a rate.

**Blocker: the numerator does not exist.** The feed gives ride *attempts* and no
ride success count anywhere. This is not an unreliable rate — it is an
unformable one.

**Unblocked by:** a ride outcome field.

### `man_up_possessions` · UNSUPPORTED · DO_NOT_USE

**Tempting because** `possessions.has_man_up_shot` exists and looks like a
man-up flag.

**Blocker: it is a goal flag.** It is TRUE for exactly 90 possessions and every
one contains a man-up goal, so the column is a renamed goal count — man-up
shooting percentage computed that way is 1.000 for all eight teams. Penalty
events carry no possession linkage either, so man-up possessions cannot be
recovered from penalty timing without inventing the state.

A regression test asserts the goals-only property, so if PLL starts tagging
missed man-up shots this decision gets revisited rather than silently inherited.
**All extra-man rates are denominated on the opportunity**, never on a
possession.

**Unblocked by:** man-up tagging on shot events, or penalty-to-possession linkage.

### `clearing_efficiency` · DEFERRED · DO_NOT_USE

**Tempting because** both official counts exist and the division is trivial.

**Two independent blockers.** (1) The feed logs **no clear event**, so a clear
cannot be tied to a possession boundary — the metric would be an orphan ratio,
integrable with nothing else in the system. (2) 36.2% of possessions have an
unconfirmed start mechanism, which is exactly the field this metric would need
in order to matter.

**The raw counts are published**; the ratio is not, because a published ratio
would be read as a possession-linked statistic it is not.

**Unblocked by:** a clear/ride event type in the play-by-play.

### `possession_source_efficiency_split` · DEFERRED · DO_NOT_USE

Efficiency by how the possession started — Lacrosse Reference publishes this.

**Blocker:** 922 possessions carry `start_reason = 'other_confirmed_control'` —
the team is known, the control-gain mechanism is not. A defensive-stop vs.
ground-ball split would assign about 21% of possessions to a bucket the feed
never established.

**Only the faceoff split is published**, because faceoff-started possessions are
never ambiguous.

**Unblocked by:** a possession-start mechanism in the feed.

### `time_of_possession_reconstructed` · DEFERRED · DO_NOT_USE

**Tempting because** the possession layer has a duration on every row and
summing it looks like time of possession.

**Blocker: it is not time of possession.** The span from a possession's first
logged event to its last excludes the interval between the previous possession's
last logged event and this one's first — transition, the clear, the dead ball.
Median coverage of PLL's official figure is 0.751 with a **0.536–0.998 range and
r = 0.58**, and mean absolute error in team possession *share* is 4.9 percentage
points. A 25% shortfall that varied consistently would be rescalable; a
0.54–1.00 range at r = 0.58 is not.

The clock itself is sound — three independent checks confirm it — so this is a
**coverage** problem, not a timing problem, which is why possession-*length*
splits remain defensible. **Only the official figure is published**, alongside
`possession_span_coverage_ratio` so the gap stays visible.

**Unblocked by:** an event stream that logs possession start as well as
possession action.

---

## Group 3 — Blocked by identification, not by a missing field

### `individual_two_point_shooting_ability` · UNSUPPORTED · DO_NOT_USE

**Tempting because** the raw rate computes for 127 players and the two-point
specialist is an intuitive archetype.

**Blocker:** the observed between-player variance (0.0234) is **smaller** than
binomial noise alone predicts (0.0276). The estimated prior strength is capped
at 1e6; all 127 shrunk rates lie within 5e-6 of the league mean 0.134328, and
every reliability is below 0.001. The median two-point shooter took **2**
attempts; the maximum was 29.

**Raw two-point production is published descriptively** — goals, attempts,
conversion with its denominator, Wilson intervals in
`two_point_audit_2026.csv`. **Ability is not ranked at any sample size**, and the
`QUALIFIED` scope for two-point conversion is deliberately empty.

**Unblocked by:** more seasons. 2022–2025 are structurally identical and would
add roughly 190 games, which is what would make this *testable* rather than
foreclosed. This is the single strongest argument for the historical ingest.

---

## Group 4 — Blocked by the accounting, not by the data

### `complete_defensive_value` · UNSUPPORTED · DO_NOT_USE

**Tempting because** `defensive_value_partial_raw` looks like a defensive rating
and the word "partial" is easy to drop.

**Blocker:** the feed attributes exactly **one** defensive act — caused
turnovers, 741 league-wide, against 4,106 shots and 1,369 attributed turnovers.
The published metric measures caused turnovers above the position group's
per-game average and **nothing else**. Off-ball defence, help positioning,
matchup difficulty, forcing a bad shot instead of a turnover, shot suppression,
sliding, recovery and communication leave no trace. **A value of 0.0 does not
mean "an average defender".** The denominator is games played, because there are
no minutes.

Validation check 19 and three tests fail if the word `partial` is dropped from
any defensive column name.

**Unblocked by:** matchup, shot-location and lineup data.

### `caused_turnover_total_defensive_impact` · UNSUPPORTED · DO_NOT_USE

**Tempting because** caused turnovers reconcile perfectly and multiplying by the
turnover coefficient gives a clean-looking number.

**Blocker:** scaling one act does not make it a total. It would invite the
reader to treat a defender's zero as an average defensive season — exactly the
error the PARTIAL naming exists to prevent. The residual form *is* published, as
`defensive_value_partial_raw`; what is refused is presenting it as a defensive
**total**.

### `ground_ball_value` · DEFERRED · DO_NOT_USE

**Tempting because** ground balls are the classic lacrosse hustle statistic and
the event value (+0.124) is estimated and published.

**Three independent reasons.**
1. **No opportunity denominator.** The feed records no ground-ball *chance*, so
   the quantity cannot be expressed as a residual and is not commensurable with
   the other components.
2. **The contexts are not statistically separable at 2026 samples:** faceoff
   scrum 0.163 [0.124, 0.201], possession-gaining 0.130 [0.098, 0.162], retained
   0.082 [−0.040, 0.204].
3. **It would double-count faceoff value.** 1,095 of 3,091 ground balls
   immediately follow a faceoff, 99.7% go to the winning team and 61.5% to the
   winner himself — a per-ground-ball credit would pay the same player twice for
   one change of possession **673 times**.

The empirical event value is preserved as the
`ground_ball_event_value_descriptive` column of `player_value_components.csv`,
**outside every total**.

### `assisted_unassisted_value_split` · DEFERRED · DO_NOT_USE

**Tempting because** official assists are reliable — exact in 100 of 100
team-games — and splitting credit is standard practice in other sports.

**Blocker: this is an accounting problem, not an attribution problem.** The
points from an assisted goal are already fully priced in the shooter's
`shooting_value`, so an independent assist credit creates two players' worth of
value from one goal. Splitting credit between shooter and assister is a
*defensible alternative*, but it changes what `shooting_value` means — so the
choice belongs to the phase that needs it rather than being slipped in as a
default.

Separately, the feed's `shotAssistId` is a **pre-shot pass indicator**, not a
confirmed assist, and an unpopulated value is not a negative assertion.
Validation greps the value SQL to enforce that it is used nowhere.

---

## Group 5 — Blocked only by scope

### `opponent_adjusted_value` · DEFERRED · REVISE_BEFORE_HISTORICAL

**Tempting because** nothing in this project is opponent-adjusted and everyone
knows it should be.

**There is no evidentiary blocker — only scope.** Publishing an unadjusted
number labelled "adjusted" would be worse than publishing an unadjusted number
labelled honestly, which is what every efficiency and value metric here does. A
ridge or mixed-model adjustment over 50 games and 8 teams is feasible but would
be poorly identified at this sample; it becomes worthwhile with 2022–2025 in
hand.

This is the **only** entry classified REVISE_BEFORE_HISTORICAL rather than
DO_NOT_USE, and the only one whose missing input is "future work" rather than a
data limitation.

---

## Summary

| Metric | Status | Freeze | Missing input |
|---|---|---|---|
| statistical_tewaaraton_or_mvp_composite | UNSUPPORTED | DO_NOT_USE | an argued cross-position weighting |
| individual_two_point_shooting_ability | UNSUPPORTED | DO_NOT_USE | more seasons |
| shot_quality_model | UNSUPPORTED | DO_NOT_USE | shot coordinates |
| true_possession_participation | UNSUPPORTED | DO_NOT_USE | lineup / shift data |
| complete_defensive_value | UNSUPPORTED | DO_NOT_USE | matchup, location, lineup data |
| caused_turnover_total_defensive_impact | UNSUPPORTED | DO_NOT_USE | as above |
| riding_efficiency | UNSUPPORTED | DO_NOT_USE | a ride outcome field |
| man_up_possessions | UNSUPPORTED | DO_NOT_USE | man-up tagging on shots |
| ground_ball_value | DEFERRED | DO_NOT_USE | a ground-ball opportunity denominator |
| assisted_unassisted_value_split | DEFERRED | DO_NOT_USE | an accounting decision |
| clearing_efficiency | DEFERRED | DO_NOT_USE | a clear event type |
| possession_source_efficiency_split | DEFERRED | DO_NOT_USE | a possession-start mechanism |
| time_of_possession_reconstructed | DEFERRED | DO_NOT_USE | possession-start events |
| opponent_adjusted_value | DEFERRED | REVISE_BEFORE_HISTORICAL | none — scope only |

**Two of the fourteen would be unblocked by the historical ingest alone**
(individual two-point ability, opponent adjustment). The other twelve need the
feed to carry something it does not.
