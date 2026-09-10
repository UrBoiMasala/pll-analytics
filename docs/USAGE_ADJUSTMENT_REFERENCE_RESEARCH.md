> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Lacrosse Reference Usage / uaEGA — Reference Research (Phase 7 §1)

Research pass over Lacrosse Reference's **publicly documented** usage
methodology, carried out before any Phase 7 code was written, to establish what
can be faithfully reproduced from the 2026 PLL feed and what has to be derived
independently.

Same structure as [`EGA_REFERENCE_RESEARCH.md`](EGA_REFERENCE_RESEARCH.md):
**Part A** is what Lacrosse Reference publishes, **Part B** is what this project
does, and §B.1 states precisely where they diverge. Nothing in Part A is
inferred; where a formula is not published, this document says so rather than
inventing one.

Retrieved 2026-09-07.

---

# Part A — What Lacrosse Reference publicly documents

## A.1 Play shares

The definition is published in one sentence and never expanded:

> "my metric that corresponds to the number of times each player appears in the
> play-by-play logs"

The companion stats page says what counts as an appearance:

> "a shot, a penalty, a forced turnover, anything that shows up in the play by
> play"

So a play share is a **raw appearance count in the event log**, with no
weighting by event type and no positional adjustment. Lacrosse Reference is
explicit about the intent — it is a proxy for touches and playing time, "since a
player has to be on the field to appear in the log" — and equally explicit about
where it fails:

> it "isn't great at capturing players on the defensive side, but for offensive
> players, it's a good proxy for who the offense runs through"

**No formula for computing play shares from the logs is published.** Which
fields are read, whether both participants in a faceoff count, whether the
goalie of record on a shot counts, and whether a play generating two log lines
counts twice are all undocumented.

## A.2 Usage-adjusted EGA (uaEGA)

The operation is published verbatim and is a single division:

> "You just divide total EGA by play shares."

The stated interpretation is "production-per-touch" or "success per
opportunity", as opposed to EGA, which is "total production".

**The adjustment is a division, not a multiplication, a residualization or a
normalization.** This matters, because "usage-adjusted" is used elsewhere in
sports analytics to mean all four.

## A.3 The minimum-usage rule

> a cutoff of "1% of a team's play shares", which "typically works out to the
> 15th or 16th spot on the depth chart"

Explicitly analogised to a minimum-plate-appearances rule. This is the only
published eligibility threshold in the methodology.

## A.4 Positional baselines and percentiles

Lacrosse Reference reports percentile ranks **within an offensive-player pool**
("98th percentile … in most of the rate stats" for an offensive player), so
positional pooling clearly exists in their published output. **The pool
definitions, the metrics percentiled and whether any positional mean or
standard deviation is subtracted are not documented.**

## A.5 Player classification into roles

Documented in 2019 with explicit thresholds, and the only place Lacrosse
Reference publishes a numeric rule for role assignment:

| Step | Rule | Class |
|---|---|---|
| 1 | "If 50% or more of a player's value is related to winning face-offs" | FOGO |
| 2 | otherwise, "if 30% of their value comes from defensive type plays, including caused turnovers and penalties" | defensive |
| 3 | otherwise | offensive |

Inputs named: faceoff wins, goals, assists, caused turnovers, penalties.

**Not documented:** how "value" is computed per play type for this purpose, why
50% and 30%, or how a defensive player with substantial offensive scoring is
handled.

## A.6 Statistical Tewaaraton inputs

The award pages state that a player's value is "calculated based on the
percentage of a player's value that comes from faceoffs vs offensive plays vs
defensive plays", that separate pages exist per position, and that a separate
Faceoff Elo rating exists. The pages also concede that a FOGO table "is as much
about offensive contributions from FOGOs as it is about actual faceoff circle
success".

**The composite weights are not published anywhere.** Neither is whether EGA or
uaEGA is the input.

## A.7 Acknowledged limitations

- EGA "does not account for playing time or opponents."
- "players with high usage-adjusted-EGA do tend to see some regression back to
  more normal levels in the following season" — an explicit acknowledgement that
  uaEGA is noisy year to year.
- Play shares are weak for defensive players (§A.1).

## A.8 What is NOT publicly documented

Searched and not found:

- Any formula for computing play shares from a play-by-play feed.
- Whether uaEGA divides by the play-share **count** or by the play-share
  **fraction of team**.
- Any positional baseline, positional mean or positional standard deviation.
- Any reliability, shrinkage or regression-to-the-mean adjustment, despite the
  regression being acknowledged in prose.
- Any goalie treatment in EGA or uaEGA.
- The Statistical Tewaaraton weights.

None of these was assumed. Where Phase 7 needed one, it derived its own answer
and says so below.

---

# Part B — What this PLL project does

## B.1 The central divergence: dividing by play shares does not survive an audit of play shares

Phase 7 **reproduced** the Lacrosse Reference operation exactly — `EPA_points /
event_log_play_shares`, published as `uaEPA_per_event_log_play_share` — and then
**declined to adopt it** as this project's usage adjustment, on evidence from
auditing the denominator.

The Phase 6 `play_shares` column already implements the Lacrosse Reference
definition faithfully (Phase 6 built it from that source). Decomposing its
17,063 appearances over the 2026 season:

| Source | Appearances | What it is |
|---|---|---|
| Primary actor | 8,779 | shooter, faceoff winner, ground-ball recoverer, penalty committer |
| Goalie of record | 4,106 | **one per shot or goal event** |
| Secondary actor | 3,092 | faceoff loser (1,301) + the shot's `shotAssistId` pre-shot passer (1,791) |
| Faceoff `gbPlayerId` | 1,086 | the scrum recovery folded into the faceoff event |

Three consequences:

**1. It is not comparable across positions.** Play shares per game:

| Role | Per game |
|---|---|
| Faceoff specialist | 38.0 |
| Goalie | 27.4 |
| Attack | 8.8 |
| Midfield | 6.0 |
| SSDM | 3.5 |
| LSM | 3.2 |
| Defense | 2.5 |

A goalie's play-share count is essentially "shots faced" and an attackman's is
essentially "shots taken". Dividing each player's value by his own count
produces two numbers on different scales, and Lacrosse Reference's own caveat
about defensive players is the same observation.

**2. One faceoff generates up to three appearances** — winner, loser, and the
scrum recovery, 61.5% of which is the winner himself. A specialist is credited
roughly twice per draw in his own denominator.

**3. It contains `shotAssistId`.** 1,791 of the appearances are the feed's
pre-shot-pass indicator, which Phase 6 documented as unreliable (populated on
42–48% of shots; an empty value is not a negative assertion) and excluded from
every value component. It is inside this usage count. That is faithful to the
published definition and is precisely why the measure is reproduced rather than
adopted.

A fourth observation is about what is *missing*: **turnovers contribute zero
play shares**, because the feed's turnover events name only a team
(`commitedTurnoverId` is null in every event of the season). The most common
negative offensive act is invisible to the Lacrosse Reference definition.

The sensitivity analysis quantifies the difference: swapping this project's
usage measure for the Lacrosse Reference one moves 226 of 228 players' usage
ranks, with a rank correlation of **0.556** and a maximum move of 200 places.

## B.2 What WAS directly reproduced

| Concept | Reproduced as |
|---|---|
| Play shares (appearance count) | `event_log_play_shares` — identical to Phase 6's `play_shares`, asserted by validation check 5 |
| Play shares as a team fraction | `event_log_play_share` |
| uaEGA operation (value ÷ play shares) | `uaEPA_per_event_log_play_share` — identical to Phase 6's `total_player_value_per_play_share`, asserted by validation check 24 |
| The 1% team play-share minimum | `future_award_input_eligible` |
| Percentiles within a positional pool | `EPA_position_percentile` and the usage/efficiency equivalents |
| FOGO classification at a 50% threshold | `value_role = 'faceoff'` — see §B.3 for the one change |

## B.3 Classification of every Lacrosse Reference concept

| Concept | Classification | What Phase 7 did |
|---|---|---|
| Play shares as an appearance count | **directly reproducible** | Reproduced exactly. Audited (§B.1) and published as a reference measure, not adopted as the usage measure |
| uaEGA = EGA ÷ play shares | **directly reproducible** | Reproduced exactly on this project's estimand and named `uaEPA_per_event_log_play_share` so it cannot be mistaken for their metric |
| 1% team play-share minimum | **directly reproducible** | Adopted verbatim as `future_award_input_eligible` |
| Percentile within an offensive pool | **conceptually reproducible** | Pool definitions are not published, so this project defines its own (`position_group`, `value_role`) and publishes both partitions |
| FOGO threshold at 50% | **conceptually reproducible, denominator independently chosen** | Their 50% applies to a share of VALUE. EPA_points is a signed residual, so "50% of a possibly-negative sum" is undefined. Applied to the player's share of his **team's faceoffs** instead — a non-negative, well-defined quantity. In 2026 the threshold lands in an empty band between 0.158 and 0.812, so no player's classification depends on the choice |
| Defensive threshold at 30% | **not reproducible — tested and rejected** | Applying 30% to opportunity shares put **24 of 96 rostered defenders (21 of 42 SSDMs) in the offensive class**, because the feed attributes one defensive act (741 caused turnovers) against 4,106 shots. Phase 7 falls back to the roster label for the offence/defence split and records that on every row |
| Positional baselines / normalization | **not documented; independently derived** | `player_positional_baselines.csv`, with sample sizes, standard errors and an explicit ≥9-player suppression rule |
| Reliability / shrinkage of rates | **acknowledged but not documented; independently derived** | Empirical-Bayes posterior weight `n/(n+kappa)` with exact beta-posterior intervals |
| Goalie usage or goalie uaEGA | **not documented; independently derived** | Goalies are normalized only against goalies; a goalie usage share is published but never compared to a field player's |
| Statistical Tewaaraton composite | **deferred by scope** | Explicitly not built. Phase 7 forbids it and a test enforces it |
| Opponent adjustment | **deferred by scope** | Lacrosse Reference states EGA is not opponent-adjusted either |

## B.4 What this project does that Lacrosse Reference does not

- **A usage measure with a stated numerator and denominator.**
  `offensive_play_share = (shots + turnovers) / the same summed over the team in
  the games played`, both sides from the same player-attributed box score.
- **A distinction between usage the mean of value responds to and usage its
  variance responds to.** Fitting E[value | usage] by cross-validated model
  selection found the **constant** wins: usage has essentially no predictive
  power for the mean of measured value in 2026 (r = +0.07). What usage moves is
  the spread — the standard deviation of offensive EPA rises from 0.50 in the
  lowest usage quintile to 4.73 in the highest.
- **A closed-form sampling variance for every value component**, so "unusual
  given the player's own volume" is answerable without resampling.
- **Reliability coefficients and exact posterior intervals** for every rate,
  with the finding that shooting and save percentage are barely identified
  individually in one PLL season.
- **An explicit cross-position comparability audit**
  ([`CROSS_POSITION_COMPARABILITY.md`](CROSS_POSITION_COMPARABILITY.md)),
  which Lacrosse Reference's published material does not attempt.

## Sources

- [Output vs Efficiency: EGA vs Usage-Adjusted EGA — Lacrosse Reference](https://lacrossereference.com/2021/11/02/output-vs-efficiency-ega-vs-usage-adjusted-ega/)
- [Lacrosse Reference Stats – Player Contributions](https://lacrossereference.com/stats/playsdistribution/)
- [In which we use box scores to classify players… — Lacrosse Reference](https://lacrossereference.com/2019/02/07/player-classification-lacrosse-analytics/)
- [A Koury-ious Case — Lacrosse Reference](https://lacrossereference.com/2021/11/29/a-maddi-koury-ious-case/)
- [Statistical Tewaaraton – FOGO (D1 Men) — Lacrosse Reference](https://lacrossereference.com/stats/statistical-tewaaraton-fogo-d1-men/)
- [Play-by-Play to EGA (a recipe) — Lacrosse Reference](https://lacrossereference.com/2021/02/09/play-by-play-to-ega-a-recipe/)
