# PLL 2026 Player Value Methodology (Phase 6)

An empirically estimated player-value framework for the Premier Lacrosse
League, built on the validated Phase 1–5 event, possession and team layers.
Phase 6 builds the **value engine**. It does not build a Statistical
Tewaaraton, an MVP model, or any cross-position composite ranking — those are
later phases and none of them was attempted here.

Written to be readable by someone who knows sports analytics but has never seen
this repository.

---

## 1. What this measures

> How much scoring value did a player's statistical production add or remove,
> relative to what a league-average player would have produced on the **same
> opportunities**?

Every component has the same shape:

```
component = observed outcome on the player's own recorded opportunities
          − expected outcome for a league-average player on those same opportunities
```

The unit is **`EPA_points` — Expected PLL Points Added**. A value of **+3.2**
means: *this player's recorded actions produced roughly 3.2 PLL points more
than league-average outcomes on the same opportunities.*

### Why "EPA_points" and not "EGA"

The conceptual inspiration is Lacrosse Reference's Expected Goals Added, but
this metric is **not** EGA and does not claim to be. EGA estimates the net goal
margin in the 60 seconds *after* each event; under it a goal is worth about
+0.02 because the goal itself falls outside the window. This metric estimates
production versus expectation on the opportunity itself, so a one-point goal is
worth +0.707. They are different estimands, not different scalings. Full
side-by-side comparison in [`docs/EGA_REFERENCE_RESEARCH.md`](../EGA_REFERENCE_RESEARCH.md).

### Why points and not goals

The PLL has a two-point arc. A goal from behind it is **one goal worth two
points**. A goals-based value unit would discard 12.1% of all PLL scoring and
would misprice every long-range shooter. Every expectation in this framework is
therefore denominated in points, and a two-point attempt is valued at
`P(goal) × 2`.

### What the baseline is — and is not

The counterfactual is **league-average expected opportunity outcome**. It is
**not** replacement level: replacement level has not been estimated anywhere in
this project, and no WAR-style language is used. A test enforces this.

## 2. Source tables

Reads, unmodified: `events.csv`, `possessions.csv`, `player_game_stats.csv`,
`team_game_stats.csv`, `games.csv`, `players.csv`, `teams.csv`.

Scope is the 50 league-analytics-eligible completed games. **The all-star game
and the ASE/ASW squads are excluded**, inherited from the Phase 5
`eligible_games` definition; 38 all-star player-game rows are dropped from
every opportunity count.

**Official player statistics are exceptionally reliable here.** Player sums
reconcile *exactly* with official team totals in all 100 team-games for goals,
one-point goals, two-point goals, assists, shots, shots on goal, two-point
shots, saves, caused turnovers, faceoff wins, faceoff losses, goals against,
two-point goals against and penalties. Two exceptions matter and are handled
explicitly:

- **Turnovers do not reconcile.** Player sums total 1,369 against a team total
  of 1,699 — roughly 19% of turnovers are credited to no player, because the
  feed's turnover descriptions carry only a team name.
- **`player_game_stats.points` is not PLL points.** It is
  `onePointGoals + 2×twoPointGoals + assists` (verified on all 1,824 rows).
  It is never used as a scoring quantity; `pll_points` is computed explicitly
  and sums to the official final score exactly.

## 3. League baselines

All in `data/processed/2026/player_value_baselines.csv` with numerator,
denominator, sample size, source, eligibility filter and standard error.

### Conversion baselines

| Baseline | Value | n | SE |
|---|---|---|---|
| Expected points per **one-point attempt** | **0.29300** | 3,570 | 0.0076 |
| Expected points per **two-point attempt** | **0.26866** | 536 | 0.0295 |
| Expected points allowed per **one-point shot on goal** | **0.46120** | 2,268 | 0.0105 |
| Expected points allowed per **two-point shot on goal** | **0.48161** | 299 | 0.0495 |
| Faceoff win probability | **0.49656** | 2,618 | 0.0098 |
| Turnovers per touch — offensive field | 0.05321 | 18,605 | 0.0017 |
| Turnovers per touch — defensive field | 0.04855 | 5,211 | 0.0030 |
| Turnovers per touch — faceoff | 0.10852 | 728 | 0.0115 |
| Turnovers per touch — goalie | 0.02688 | 1,674 | 0.0040 |
| Caused turnovers per game — defensive field | 0.71040 | 808 | 0.0160 |
| Caused turnovers per game — offensive field | 0.15443 | 790 | 0.0129 |
| League points per possession | 0.27119 | 4,388 | — |
| Points per faceoff-started possession | 0.24520 | 1,301 | — |

Two of these deserve comment.

**The faceoff win probability is 0.49656, not 0.5.** Every draw credits a
faceoff to both participants and a win to one, so the ratio would be exactly
0.5 except that 18 of the season's draws have no recorded winner (violations
and redraws — the Phase 5 finding that `faceoffsWon + faceoffsLost` falls short
of `faceoffs` in 8 games). Using the empirical rate is what makes faceoff value
sum to exactly zero league-wide; an assumed 0.5 leaves a residual.

**A two-point attempt is worth *less* than a one-point attempt** (0.269 vs
0.293). The long shot converts at 13.4% against 29.3%, and doubling it does not
quite close the gap. On shots *on goal* the ordering reverses (0.482 vs 0.461),
because two-point shots that reach the cage are relatively more valuable — which
is why the goalie baselines are split the same way.

### Event-value coefficients

Estimated by the forward-window method Lacrosse Reference documents (net PLL
points in the 60 seconds after an event), reported **net of a measured neutral
reference of +0.01512** so that a coefficient of zero means "leaves the scoring
outlook where an average moment of play would". Bootstrap SEs, 2,000 resamples.

| Event | Value vs neutral | n | SE |
|---|---|---|---|
| Faceoff win | **+0.17321** | 1,301 | 0.0182 |
| Ground ball | +0.12401 | 3,091 | 0.0124 |
| Missed shot | +0.08171 | 1,539 | 0.0176 |
| Two-point goal | +0.01268 | 72 | 0.0593 |
| Shot on goal, no save | −0.00212 | 154 | 0.0611 |
| One-point goal | −0.04187 | 1,046 | 0.0201 |
| Saved shot | −0.10082 | 1,295 | 0.0179 |
| **Turnover** | **−0.20046** | 1,721 | 0.0143 |
| Shot-clock expiration | −0.27416 | 359 | 0.0322 |
| Penalty | −0.41724 | 281 | 0.0436 |

Faceoff wins (+0.173 vs LR's +0.18), turnovers (−0.200 vs −0.17) and penalties
(−0.417 vs −0.31/−0.36) land close to Lacrosse Reference's published NCAA
figures, which is good evidence the estimator was reproduced faithfully.

**Position groups**, used for the turnover and caused-turnover baselines:

| PLL label | Position | Baseline group |
|---|---|---|
| A | Attack | offensive_field |
| M | Midfield | offensive_field |
| SSDM | Defensive midfield | defensive_field |
| LSM | Long-stick midfield | defensive_field |
| D | Defense | defensive_field |
| FO | Faceoff | faceoff |
| G | Goalie | goalie |

PLL labels are already role-specific; no NCAA convention is assumed. Position
is resolved **once per player** (modal non-null label, ties broken
alphabetically) rather than per game — four player-game rows carry a null
label for players labelled normally elsewhere, and resolving per row would
break the residual identity. The two players with no label in any game are
grouped `unknown` rather than guessed. Deliberately coarse: four groups, not
seven, so no baseline rests on a tiny sample.

## 4. Shooting value

```
shooting_value = (one_point_goals + 2 × two_point_goals)
               − (one_point_attempts × 0.29300 + two_point_attempts × 0.26866)
```

This values **finishing only**. It carries no credit for generating the shot or
for having the possession — those are not separable in this feed, and crediting
them here is what would double-count possession value.

### Shot-model selection, and a leak that was caught

A richer expected-shot model was fitted and **rejected on evidence**. Candidate
features were limited by the feed: verified across all 51 raw games, shot
events carry **no location, no distance and no defender** — the only populated
`details` keys are `shotOnGoal`, `shotSaved`, `saveType`. PLL's man-up tags
(`MU`, `MU_2_PT`) appear on **goal events only** (all 90 of them), so man-up
state is not observable at attempt time either. That leaves the shot's point
class and game state.

| Model | Features | Brier (in-sample) | **Brier (5-fold CV)** |
|---|---|---|---|
| Intercept only | — | 0.198146 | 0.198225 |
| **Shot class (selected)** | one- vs two-point | 0.195288 | **0.195476** |
| Shot class + game state | + score margin, period, game progress | 0.195156 | 0.195675 |

The richer model is **worse out of sample**. The simple two-class empirical rate
is used.

An earlier version of the game-state model appeared to win by 2.1%. It was
**target leakage**: the feed's `home_score`/`away_score` columns already include
the goal on the row itself (verified — the first goal of 2026-ev-1 carries
`away_score` 1), so every goal arrived pre-labelled with a score swing a miss
at the same instant did not have. The score is now lagged by subtracting the
row's own points, and the advantage disappears entirely. This is recorded
because it is exactly the failure mode that makes an unvalidated "expected
goals" model look impressive.

## 5. Turnover value

```
turnover_value = −(turnovers − touches × group turnover-per-touch rate) × 0.20046
```

A **residual**, not a raw charge. A raw `−turnovers × cost` punishes volume: an
attackman with 400 touches would always look worse than a close defender with
80, which measures role rather than performance. Charging only turnovers *above*
what an average player of that role commits on the same touches puts the
component on the same footing as the others.

Position-group rates are used because the rate is genuinely role-dependent —
faceoff specialists turn the ball over roughly twice as often per touch
(0.109 vs 0.053), because their touches are overwhelmingly contested scrum
recoveries. Charging a FOGO against an attackman's rate would penalise the role.

**Opportunity cost without double-counting.** The temptation is to charge a
turnover both the possession's expected value (0.271) *and* the transition cost
(0.200). That would price the same lost opportunity twice. It cannot happen
here because `shooting_value` never contains a possession-value term for the
turnover charge to duplicate. See
[`docs/PLAYER_VALUE_ACCOUNTING.md`](../PLAYER_VALUE_ACCOUNTING.md) scenario D.

## 6. Faceoff value

```
faceoff_value = (faceoff_wins − faceoffs × 0.49656) × 0.34643
```

**The counterfactual is explicit**, which is what stops this from being "full
possession value for every win". The alternative to this player winning is a
*league-average faceoff man* winning at 49.656% — not the team forfeiting the
ball. A specialist who wins exactly at the league rate scores exactly zero.

The coefficient is **twice** the faceoff event value (`2 × 0.17321`): winning
gives the value to your team, losing gives the same value to the opponent, so
converting a loss into a win is worth twice one event's worth.

NULL, not zero, for players who never took a draw.

## 7. Ground balls — deferred, with evidence

Ground-ball value is **not computed**. `ground_ball_value` is NULL for every
player. Three independent reasons:

**1. There is no opportunity denominator.** The feed records no "ground-ball
chance", so the quantity cannot be expressed as a residual and is not
commensurable with the other components.

**2. The distinguishable contexts are not statistically separable.** The three
contexts the feed supports:

| Context | n | Net points | 95% CI |
|---|---|---|---|
| Faceoff scrum | 1,095 | 0.163 | [0.124, 0.201] |
| Possession-gaining | 1,838 | 0.130 | [0.098, 0.162] |
| Retained possession | 158 | 0.082 | [−0.040, 0.204] |

The intervals overlap substantially. At 2026 sample sizes a context-specific
model is not supportable.

**3. It would double-count faceoff value.** 1,095 of 3,091 ground balls
immediately follow a faceoff. **99.7% go to the faceoff-winning team and 61.5%
to the faceoff winner himself.** Faceoff specialists average 7.11 ground balls
per game, more than double any other position, almost entirely through this
mechanism. A per-ground-ball credit would pay the same player twice for one
change of possession, 673 times.

The empirical per-ground-ball event value is preserved as
`ground_ball_event_value_descriptive`, **outside every total**, for a later
phase.

## 8. Defensive value — partial, and labelled as such

```
caused_turnover_value = (caused_turnovers − games_played × group rate) × 0.20046
```

Caused turnovers come from the **official player box score**, which reconciles
exactly with official team totals in all 100 team-games (741 season-wide). They
are **not** inferred from turnover events: Phase 4.25 established that the
event-level caused-turnover field is null in every event of the season, and
nothing here works around that.

**This is one countable act wide.** Positioning, matchup difficulty, forcing a
bad shot instead of a turnover, sliding, communication — none of it leaves a
trace in this feed, and none of it is in this number. The column is named and
documented as partial for that reason. It is not a defensive EGA.

**Games played is the weakest denominator in the framework.** The feed has no
minutes, shifts or lineups, so a defender who plays every defensive possession
and one who rotates are treated as having equal opportunity.

## 9. Goalkeeper value

```
goalie_value = (one_point_SOG_faced × 0.46120 + two_point_SOG_faced × 0.48161)
             − actual PLL points allowed
```

Positive means fewer points conceded than a league-average keeper would have on
the same shots. The sign is flipped relative to shooting so that "more is
better" holds everywhere.

Goalies are valued on **shots on goal faced**, not attempts — a keeper is not
responsible for a shot that missed the cage.

**Two-point handling.** Separate baselines are estimated because the conversion
rates differ sharply (46.1% vs 24.1% on shots on goal), but each two-point goal
costs two points, so the expected *points* per shot on goal are nearly equal
(0.461 vs 0.482). A goalie facing more long-range shots is therefore neither
rewarded nor punished for the shot mix. The one-point/two-point split of shots
faced does not exist in the official player box score and is recovered from the
event log, where every shot carries its goalie — reconciled against official
saves in 116/117 goalie-games and goals allowed in 117/117.

**No shot-quality adjustment is possible.** With no location or defender data, a
keeper behind a defence that concedes point-blank looks worse and one behind a
defence that forces long shots looks better. Real, unmeasurable here, stated
rather than hidden.

## 10. Assists — deferred

Official assists are reliable (560 season-wide, exact in 100/100 team-games) and
are carried as a **descriptive count**. They are not valued.

The points from an assisted goal are already fully priced in the shooter's
`shooting_value`. An independent assist credit would create two players' worth
of value from one goal. Splitting credit between shooter and assister is a
defensible alternative, but it changes what `shooting_value` means, so the
choice belongs to the phase that needs it rather than being slipped in as a
default.

The feed's `shotAssistId` is used **nowhere**: it is a pre-shot pass indicator,
not a confirmed assist, and unpopulated does not mean no pass occurred.
Validation check 23 greps the value SQL to enforce this.

## 11. Opportunity and usage definitions

Every opportunity in `player_opportunities.csv` is an **individual recorded
opportunity** — something the player himself was credited with.

**Team possessions while a player was on the field are not computable.** The
PLL feed carries no lineup or substitution data of any kind. No metric in
Phase 6 is denominated in possessions; validation check 22 enforces it.

`play_shares` — appearances anywhere in the event log, Lacrosse Reference's own
definition — is published as a **usage proxy**. It is not playing time, not
possessions, and not comparable across positions (roles appear in the log at
very different rates).

Rate and volume are kept separate throughout (`shooting_value` vs
`shooting_value_per_shot`, `faceoff_value` vs `faceoff_value_per_faceoff`,
`goalie_value` vs `goalie_value_per_shot_on_goal_faced`), because a high-volume
player can post a large total on average efficiency and a low-volume player a
high per-opportunity figure on almost no contribution. Both stay visible.

## 12. Accounting identity

Because every component is a residual against a league baseline, **no team
points are ever partitioned**, and:

```
Σ over all players of every component = 0, exactly
```

Verified to 10 decimal places for all five components and the total. Full
scenario-by-scenario audit, with executed tests, in
[`docs/PLAYER_VALUE_ACCOUNTING.md`](../PLAYER_VALUE_ACCOUNTING.md).

## 13. Uncertainty and shrinkage

Empirical-Bayes (beta-binomial) shrinkage, prior estimated from the league by
method of moments, published in `player_value_shrinkage.csv` **alongside** the
raw rates and **not substituted** into any value component. Shrinking a rate
and then multiplying it by the player's own opportunity count would drag every
player's total toward zero in proportion to his sample — a much stronger claim
than shrinking the rate itself.

The prior strength is the finding:

| Rate | Prior strength | Raw SD → shrunk SD | Interpretation |
|---|---|---|---|
| Faceoff win % | **15.9 draws** | 0.272 → 0.092 | Strongly identified — real skill differences |
| Save % | 300 shots | 0.153 → 0.017 | Partially identified |
| Shooting % | 70.8 shots | 0.192 → 0.024 | Weakly identified |
| One-point % | 75.3 shots | 0.205 → 0.023 | Weakly identified |
| **Two-point %** | **1,000,000 (capped)** | 0.200 → **0.000** | **Not identified at all** |

**The 2026 season contains no statistical evidence that players differ in
two-point shooting ability.** The observed between-player variance (0.0234) is
*smaller* than binomial noise alone predicts (0.0276) — the median player took
2 two-point attempts, the maximum was 29. Every player's shrunk two-point rate
is the league mean. Differences in `shooting_value_two_point` between players
are, on this evidence, indistinguishable from chance.

## 14. Sensitivity analysis

`player_value_sensitivity.csv`, 1,596 rows.

| Component | Alternative | Mean abs diff | Max abs diff | Players changing rank | Max rank move |
|---|---|---|---|---|---|
| shooting_value | empirical-Bayes shrunk rates | 1.143 | 8.280 | 219 / 228 | 189 |
| shooting_value | rejected logistic game-state model | 0.072 | 0.602 | 181 / 228 | 84 |
| turnover_value | league PPP cost (0.271) | 0.158 | 0.928 | **0** | 0 |
| turnover_value | 30-second window (0.138) | 0.140 | 0.825 | **0** | 0 |
| turnover_value | 120-second window (0.156) | 0.099 | 0.585 | **0** | 0 |
| faceoff_value | possession-native coefficient (0.490) | 0.686 | 4.422 | **0** | 0 |
| faceoff_value | assumed 0.5 win probability | 0.066 | 0.420 | 27 / 47 | 4 |

**Turnover and faceoff rankings are completely insensitive to the coefficient
choice** — the alternatives are linear rescalings of the same residual, so
magnitudes move but nobody changes position. The faceoff coefficient is the
largest open magnitude question: the possession-native alternative is 42%
larger, which would raise the top faceoff specialist from +10.6 to +15.1.

**Shooting value is highly sensitive to shrinkage** — 219 of 228 players change
rank. This is the headline caveat: raw shooting value credits a player fully
for a conversion rate that, at 2026 sample sizes, is substantially noise.

No alternative was chosen because it produced a nicer leaderboard; the shot
model was selected on cross-validated Brier score before any player total was
inspected.

## 15. SQL architecture

Phase 5's SQL-first pattern continues. Python does statistical estimation
(bootstrap over a forward event scan, IRLS logistic fit, cross-validation,
empirical Bayes) because none of it is a clean aggregate query; the value
accounting is SQL.

```
sql/20_player_base_views.sql     eligible player-games, position resolution,
                                 event-derived goalie opportunities, play shares
sql/player_value_baselines.sql   all baselines + the pivoted coefficient view
sql/player_opportunities.sql     228 x 55  opportunity/usage table
sql/player_shooting_value.sql    finishing vs expectation
sql/player_turnover_value.sql    possession security vs role expectation
sql/player_faceoff_value.sql     wins above expectation
sql/player_defensive_value.sql   caused turnovers above positional expectation
sql/player_goalie_value.sql      points prevented
sql/player_value_components.sql  assembled, with NULL discipline and role totals
```

Coefficients estimated in Python are written to a scratch CSV and read back by
the baselines query, so the SQL layer has a single documented source for every
number it multiplies by.

## 16. Validation

`scripts/pll_validate_player_value.py` → `player_value_validation_report.csv`,
**24/24 checks passing**. Every numeric check recomputes its quantity in pandas
from the canonical tables; the SQL is never re-run to check itself. Check 19
rebuilds all five components with separate arithmetic. Check 21 rebuilds every
output into a scratch directory and compares SHA-256.

95 tests pass across the repository (60 from Phases 1–5, 35 new).

## 17. Known limitations

1. **Not opponent-adjusted.** No strength-of-schedule adjustment exists.
2. **~19% of league turnovers are charged to nobody** (§2).
3. **Defensive value is one act wide** and rests on a games-played denominator.
4. **Goalie value is not shot-quality adjusted.**
5. **Two-point shooting ability is not measurable in 2026** (§13).
6. **Cross-position totals are not comparable.** A goalie faces 150–330 shots on
   goal; an attackman takes ~80 shots. Goalies therefore dominate raw
   `total_player_value` on opportunity volume alone. This is a property of the
   unit, not a ranking claim, and is why Phase 6 stops before an award model.
7. **Ground balls and assists are unvalued** (§7, §10).
8. **Play shares are a usage proxy, not playing time.**
9. **No penalty component**, though the coefficient is estimated and published.
10. **Single season, 12–13 games per team.** Phase 5 already showed team
    rankings are fragile at this sample size; player rankings are more so.
