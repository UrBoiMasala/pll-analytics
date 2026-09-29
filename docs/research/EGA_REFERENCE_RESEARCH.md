> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](../PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](../METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Lacrosse Reference EGA — Reference Research (Phase 6 §1)

Research pass over Lacrosse Reference's **publicly documented** methodology,
carried out before any Phase 6 code was written, to establish what can be
faithfully reproduced from the 2026 PLL feed and what must be derived
independently.

This document is deliberately split into two parts. **Part A** is what
Lacrosse Reference publishes. **Part B** is what this project does. They are
not the same thing, and §B.1 states precisely where they diverge.

Retrieved 2026-09-07.

---

# Part A — What Lacrosse Reference publicly documents

## A.1 What EGA is

Expected Goals Added is described by Lacrosse Reference and by USA Lacrosse as
"the lacrosse version of WAR": a single number that takes everything a player
does that shows up in the box score and expresses it in goal-equivalent units.
Its stated purpose is cross-positional comparison — putting a value on gaining
possession as well as on finishing, so a faceoff specialist and an attackman
can be compared on one scale.

## A.2 How the event values are estimated

The recipe is published and is unusually explicit:

> For each play type: count how many times it occurs, count the number of times
> the team scored within the next 60 seconds of play, count the number of times
> the other team scored within the next 60 seconds, and compute
> `(myGoals − theirGoals) / TOT`.

So each play type carries an empirical **net goal margin over the following 60
seconds**. A player's EGA is then the sum of the values of the events
attributed to him.

The 2021 recipe post lists the valued play types as: penalties committed,
turnovers, shot-clock violations, assisted goals, unassisted goals, blocked
shots, pipe shots, saved shots, missed shots, and ground balls. The published
estimation base was 8,180 D1 men's and women's games back to 2015.

## A.3 The published NCAA values

| Play type | EGA value |
|---|---|
| Missed shot | +0.19 |
| Ground ball | +0.19 |
| Faceoff win | +0.18 |
| Pipe shot | +0.16 |
| Blocked shot | +0.10 |
| Assisted goal | +0.04 |
| Saved shot | +0.03 |
| Unassisted goal | +0.02 |
| Forced turnover | −0.17 |
| Unforced turnover | −0.17 |
| Penalty (2 min) | −0.31 |
| Penalty (30 sec) | −0.33 |
| Penalty (1 min) | −0.36 |

**The single most important thing to understand about this table is that a goal
is worth almost nothing (+0.02 to +0.04) while a missed shot is worth +0.19.**
That is not a mistake and it is not a claim that missing is better than
scoring. It follows directly from the 60-second forward window: after you
score, the opponent gets the ball at the next faceoff, so the goals-in-the-next-
60-seconds margin nets out near zero — and the goal itself is *not counted*,
because the window starts after the event. After a missed shot you usually
still have the ball.

EGA is therefore a **state-transition / field-position value**: it measures how
much better off your team is *after* the play, not the scoring the play itself
produced.

## A.4 Components

Lacrosse Reference separates offensive EGA (oEGA), defensive EGA (dEGA) and
faceoff-specific EGA, so specialists can be evaluated on their own phase. The
faceoff page notes explicitly that "if a FOGO scores a goal off a faceoff, that
contribution would be captured in the total value but not in the faceoff-only
EGA column."

## A.5 Usage-adjusted EGA

> "You just divide total EGA by play shares."

**Play shares** are "the number of times each player appears in the play-by-play
logs" — a proxy for touches and playing time, since a player has to be on the
field to appear in the log. A 1% team play-share minimum is applied to keep
small samples out. uaEGA answers "production per touch" where EGA answers
"total production".

## A.6 Acknowledged limitations

Lacrosse Reference states that EGA "does not account for playing time or
opponents."

## A.7 What is NOT publicly documented

Searched and not found in public material:

- Any formula for how goalie value enters EGA, or whether saves are credited to
  the goalie at the published "saved shot" value or at a separate one.
- The exact opportunity-cost treatment — whether components are ever expressed
  relative to a positional baseline rather than as raw event sums.
- Whether the 60-second window is tuned or conventional.
- How ground balls are split by context, if at all.
- The Statistical Tewaaraton composite weights.

None of these were assumed. Where Phase 6 needed one of them, it derived its
own answer and says so.

---

# Part B — What this PLL project does

## B.1 The central divergence: this project's metric is NOT Lacrosse Reference's EGA

The Phase 6 brief asks for a value framework answering:

> "How much scoring value does a player's statistical production add or remove
> relative to league-average opportunities?"

and specifies `shooting_value = observed_points_from_shots −
expected_points_from_shots`. That is an **opportunity-baseline residual**: what
the player produced versus what an average player would have produced on the
same chances.

Lacrosse Reference's EGA estimates a **different quantity**: the net scoring
margin in the 60 seconds after an event, summed over the player's events. The
two are not rescalings of each other:

| | Lacrosse Reference EGA | This project (`EPA_points`) |
|---|---|---|
| Estimand | net goal margin in the 60s *after* each event | points produced *minus* points expected on the same opportunities |
| Does a goal score highly? | No — +0.02, because the goal itself is outside the window | Yes — a one-point goal is worth `1 − 0.293 = +0.707` |
| Baseline | implicit (a zero net margin) | explicit league-average conversion for that opportunity class |
| League aggregate | not zero | exactly zero, by construction |
| Volume behaviour | cumulative — more events, more value | residual — more events only help if converted above average |

**Because of this, the metric is named `EPA_points`, not EGA.** Calling it EGA
would assert an equivalence that is demonstrably false: under EGA the league's
best finisher gains almost nothing for finishing.

## B.2 What WAS directly reproduced

The forward-window estimator itself was reproduced exactly and run on the 2026
PLL season (`scripts/pll_player_value_models.py::estimate_event_values`), in
PLL points rather than goals. This is used to derive the turnover, faceoff and
ground-ball coefficients empirically rather than inventing them.

The reproduction validates well against the published NCAA figures:

| Play type | LR (NCAA, goals) | PLL 2026 (points) | n |
|---|---|---|---|
| Faceoff win | +0.18 | **+0.188** | 1,301 |
| Turnover | −0.17 | **−0.185** | 1,721 |
| Ground ball | +0.19 | +0.139 | 3,091 |
| Missed shot | +0.19 | +0.097 | 1,539 |
| Saved shot | +0.03 | −0.086 | 1,295 |
| Unassisted goal | +0.02 | −0.027 (1-pt goal) | 1,046 |
| Penalty | −0.31 to −0.36 | −0.402 | 281 |

Faceoff wins, turnovers and penalties land almost exactly on the published
NCAA values, which is strong evidence the estimator was reproduced correctly.
Ground balls and shots are lower in the PLL and saved shots are negative rather
than positive — plausibly because the PLL's 32/52-second shot clocks and higher
pace shorten the window's reach, but this project does not claim to have
established the cause.

A **neutral reference** was added, which Lacrosse Reference does not document:
the same statistic over all team-attributed events is +0.0151, so each PLL
coefficient is reported net of it. Without that adjustment a coefficient of
zero would not mean "neutral".

## B.3 Classification of every Lacrosse Reference concept

| Concept | Classification | What Phase 6 did |
|---|---|---|
| Forward-window event valuation | **directly reproducible** | Reproduced in PLL points; used to derive turnover, faceoff and ground-ball coefficients |
| Faceoff EGA | **conceptually reproducible, formula independently derived** | LR gives an event value, not a marginal one. Phase 6 uses `(wins − expected wins) × 2v`, so a league-average specialist scores zero |
| Offensive EGA | **conceptually reproducible, formula independently derived** | Rebuilt as an opportunity-baseline residual (§B.1) with explicit PLL two-point handling, which has no NCAA analogue |
| Defensive EGA | **partially reproducible** | Only caused turnovers are supported; published as an explicitly partial component. Blocked shots do not exist in this feed |
| Goalie value | **not documented by LR; independently derived** | Built from scratch: expected points allowed on shots on goal faced, with separate one- and two-point baselines |
| Usage-adjusted EGA (play shares) | **directly reproducible** | Play shares computed from the event log as LR defines them; published as a usage measure. The uaEGA ratio itself is deferred to the phase that ranks players |
| Assisted vs unassisted goal split | **not reproducible** | The feed's `shotAssistId` is a pre-shot pass indicator, not a confirmed assist, and unpopulated does not mean no pass. Official assists exist but are not valued (see accounting) |
| Blocked shots, pipe shots | **not reproducible** | Neither event type exists in the PLL feed |
| Penalty value | **reproducible but deferred** | The coefficient is estimated (−0.417) and published in the baselines table, but no penalty component is added to player value in Phase 6 |
| Statistical Tewaaraton | **deferred by scope** | Explicitly out of scope; no composite is built |
| Opponent adjustment | **deferred by scope** | LR states EGA is not opponent-adjusted either |

## B.4 What this project does that Lacrosse Reference does not

- **PLL two-point scoring**, throughout. Every expectation is in points, and a
  two-point attempt carries `P(goal) × 2`. There is no NCAA equivalent.
- **Explicit opportunity baselines** with sample sizes and standard errors, in
  `player_value_baselines.csv`.
- **A neutral reference** for the event values (§B.2).
- **Empirical-Bayes shrinkage diagnostics**, which surfaced that 2026 two-point
  shooting shows no measurable between-player skill spread at all.
- **A league-sum-to-zero identity** that every component satisfies exactly, and
  that validation checks 14–16 assert.

## Sources

- [Play-by-Play to EGA (a recipe) — Lacrosse Reference](https://lacrossereference.com/2021/02/09/play-by-play-to-ega-a-recipe/)
- [Beyond the Basics: Understanding Expected Goals Added — USA Lacrosse](https://www.usalacrosse.com/magazine/beyond-basics-understanding-expected-goals-added)
- [Output vs Efficiency: EGA vs Usage-Adjusted EGA — Lacrosse Reference](https://lacrossereference.com/2021/11/02/output-vs-efficiency-ega-vs-usage-adjusted-ega/)
- [Statistical Tewaaraton – FOGO (D1 Men) — Lacrosse Reference](https://lacrossereference.com/stats/statistical-tewaaraton-fogo-d1-men/)
- [Cumulative Efficiency – D1 Men — Lacrosse Reference](https://lacrossereference.com/stats/adj-efficiency-d1-men/)
