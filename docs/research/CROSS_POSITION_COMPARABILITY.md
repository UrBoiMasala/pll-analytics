> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](../PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](../METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Cross-Position Comparability Audit (Phase 7 §11)

Which Phase 6/7 metrics can legitimately be compared across attack, midfield,
defense, faceoff and goalie — and which cannot.

This audit is a prerequisite: **no cross-position leaderboard exists anywhere in
this project, and none may be built until the question below is answered for the
metric it would rank.** Phase 7 does not build one.

---

## The core problem, in one table

`EPA_points` shares a unit across every role — PLL points above league-average
expected outcome. A shared unit is not a shared scale. What differs is the
**opportunity base** each role is measured over, and it differs by more than an
order of magnitude:

| Role | n | Defining opportunity | Season total | Observed sd of `EPA_points_raw` |
|---|---|---|---|---|
| Goalie | 17 | shots on goal faced | 2,567 | **9.59** |
| Attack | 37 | shot attempts | 2,237 offensive opps | 4.74 |
| Faceoff | 13 | faceoffs taken | 2,618 | 4.39 |
| Midfield | 63 | shot attempts | 2,368 offensive opps | 3.30 |
| Defensive field | 96 | caused turnovers / games | 622 offensive opps | **1.46** |

A goalie's season has **6.6 times** the standard deviation of a close
defender's. That is not a claim that goalies matter 6.6 times more. It is
arithmetic: a busy goalie faces 300+ shots on goal in a season while a close
defender's entire measured record is a handful of caused turnovers on a
games-played denominator. Ranking the two on one list ranks them by how much of
their job this feed happens to count.

The same point holds for usage. Per game, event-log play shares run 38.0 for a
faceoff specialist and 2.5 for a close defender — a 15× spread that is entirely
about which roles the play-by-play log records.

---

## Classification of every major metric

Four classes, as the Phase 7 brief specifies:

- **A — directly cross-position comparable**
- **B — comparable only after normalization**
- **C — role-specific; must not be compared across roles**
- **D — unsupported for some roles**

### Volume and usage

| Metric | Class | Reasoning |
|---|---|---|
| `games_played` | **A** | A game is a game. The only metric in this project that is unambiguously comparable everywhere |
| `recorded_offensive_opportunities` | **C** | Measures offensive workload. A goalie's 4 and an attackman's 121 describe different jobs, not different amounts of the same job |
| `offensive_play_share` | **C** | Same reason. Attack averages 0.114, defensive field 0.013 — the ordering is the role, not the player |
| `event_log_play_shares` | **C** | Worse than the above: the count is dominated by how often the feed records the role at all (goalie 27.4/game as an artefact of one appearance per shot faced). See the audit in `USAGE_ADJUSTMENT_REFERENCE_RESEARCH.md` §B.1 |
| `touch_share` | **C** | Counts a defenseman's clear and an attackman's dodge as one unit |
| `faceoff_team_share` | **D** | Undefined for 181 of 228 players. Meaningful only within the faceoff role |
| `shots_on_goal_faced` | **D** | Non-zero for 16 players. Meaningful only within the goalie role |

### Raw value

| Metric | Class | Reasoning |
|---|---|---|
| `EPA_points_raw` | **C** | Shared unit, incompatible opportunity bases (table above). This is the headline finding of the audit and the single most important line in this document |
| `shooting_value_raw` | **B** | Every role that takes a shot is measured on the same opportunity — a shot attempt — against the same league baseline. Comparable **after** conditioning on attempt volume, because a 121-attempt attackman and a 6-attempt FOGO have chance spreads differing by 4.5× |
| `turnover_value_raw` | **B** | Already residualized against a position-group turnover-per-touch rate in Phase 6, which removes the role effect from the *expectation*. The remaining incomparability is volume: touches range from 3 to 524 |
| `faceoff_value_raw` | **D** | NULL for 181 players. Within the 47 who took a draw it is comparable; across roles it is not a dimension most players have |
| `goalie_value_raw` | **D** | NULL for 212 players |
| `defensive_value_partial_raw` | **C and PARTIAL** | Comparable in form across roles but not in meaning: it measures one act, on a games-played denominator, and a value of 0 means "caused turnovers at the positional per-game rate", **not** "an average defender". See §Defensive caveat |

### Efficiency

| Metric | Class | Reasoning |
|---|---|---|
| `shooting_EPA_per_shot` | **B** | Volume-free and same-unit across roles, so the scale is shared. Still needs a reliability gate: only 13 of 192 shooters reach reliability 0.5 |
| `EPA_per_recorded_opportunity` | **B** | Same, on the broader offensive opportunity base |
| `faceoff_EPA_per_faceoff` | **D** | Faceoff role only |
| `goalie_EPA_per_SOG` | **D** | Goalie role only |
| `defensive_EPA_partial_per_game` | **C** | The denominator is games, so it measures per-game caused-turnover production, which is a role property before it is a player property |
| `uaEPA_per_event_log_play_share` | **C** | Inherits the incomparability of its denominator entirely |

### Rates and skill estimates

| Metric | Class | Reasoning |
|---|---|---|
| `shooting_rate_shrunk` | **B** | Same quantity for everyone who shoots; comparable after shrinkage, which is what puts a 6-shot and a 98-shot player on one footing |
| `faceoff_rate_shrunk` | **D** | Faceoff takers only (47 players) |
| `save_rate_shrunk` | **D** | Goalies only (16 players) |
| `two_point_rate_shrunk` | **D — and unsupported for everyone** | The 2026 season contains no evidence that players differ. Every shrunk value is the league mean |

### Standardized measures

| Metric | Class | Reasoning |
|---|---|---|
| `EPA_position_percentile` | **B, with a caveat** | Within-group by construction, so the group effect is removed. But a percentile is **not** a value: the 90th-percentile goalie and the 90th-percentile attackman are not equally valuable, and treating equal percentiles as equal contributions is the exact error a naive award model makes |
| `EPA_position_z`, `EPA_position_robust_z` | **B, same caveat** | Removes the group mean and scales by the group spread. Equal z is equal *unusualness within role*, not equal value |
| `EPA_points_null_z` | **A, and the closest thing to a genuinely comparable measure** | Divides value by the chance spread at the player's own opportunity volume. It has the same meaning for every role — "how far from what luck alone could produce" — and is the only standardization here that does not depend on a peer group's size or composition. It is still **not** a value measure: a goalie's +2 and an attackman's +2 mean equally-unusual seasons, not equal contributions |
| `EPA_vs_usage_expectation_z` | **B** | Defined only for the field-player population the usage model was fitted on; NULL for goalies and faceoff specialists |

### Reliability

| Metric | Class | Reasoning |
|---|---|---|
| `shooting_reliability`, `faceoff_reliability`, `save_reliability` | **A as a statement about evidence** | "This posterior puts 0.5 weight on the player's own record" means the same thing for a goalie and an attackman. It is a property of the sample, not the role. It is **not** a quality measure and must never be ranked as one |
| `rate_ranking_eligible` | **A** | A boolean about evidence sufficiency |

---

## Conclusions

**1. No metric in this project supports a cross-position value ranking.** The
only class-A value-adjacent metric is `EPA_points_null_z`, and it measures
unusualness rather than contribution. Everything that measures *how much a
player produced* is class B or C.

**2. Positional standardization removes the group effect but does not create
comparability of value.** Percentiles and z-scores put every role on a common
*statistical* scale. They do not establish that a 95th-percentile faceoff
specialist and a 95th-percentile attackman contributed equally. The evidence
that they did not is direct: the goalie group's EPA standard deviation is 9.59
against the defensive-field group's 1.46, so one percentile point means 6.6×
more points in one group than the other.

**3. The binding constraint is not statistics, it is measurement coverage.**
Attack and midfield value is measured over thousands of shots. Defensive value
is measured over 741 caused turnovers with no denominator. Until the feed
records more of what a defender does, any cross-position model will
systematically understate defenders — not because they contribute less, but
because less of what they contribute is written down.

**4. `EPA_points_raw` must never be used as a cross-position leaderboard.**
Doing so ranks by opportunity volume. Phase 6 said this and Phase 7's baselines
quantify it.

---

## Defensive caveat, stated once and enforced everywhere

`defensive_value_partial_raw` measures **caused turnovers above the position
group's per-game average, and nothing else**. Not captured:

- off-ball defence and help positioning
- matchup difficulty and who a defender was assigned to
- forcing a bad shot instead of forcing a turnover
- shot suppression
- sliding, recovery, communication
- playing time — the denominator is games played, because the feed has no
  minutes, shifts or lineups, so a defender who plays every defensive
  possession and one who rotates are treated as having equal exposure

**A `defensive_value_partial_raw` of 0.0 does not mean "an average defender".**
It means "this player caused turnovers at his position group's per-game rate,
and everything else he did on defence is unmeasured". Every row of
`player_adjusted_value.csv` carries `defense_partial = TRUE`,
`defensive_value_scope`, and a `role_interpretation_caveat` that repeats this
for defenders. Validation check 19 and three tests fail if the word "partial" is
ever dropped from a defensive column name.

---

## What Phase 8 may and may not do with this

**May:**

- Rank within a role, using the positional percentile or the within-role value.
- Use `EPA_points_null_z` to say a season was unusual, in any role.
- Use the reliability columns to decide who has enough evidence to be ranked.
- Build a cross-position model **provided the weights are argued for
  explicitly** and the argument addresses the opportunity-base problem above.

**May not:**

- Sum or average `EPA_points_raw` across roles and call the result a ranking.
- Treat equal positional percentiles as equal value.
- Treat a defensive value near zero as evidence of average defence.
- Use `event_log_play_shares` or `uaEPA_per_event_log_play_share` in any
  cross-position comparison.
- Rank two-point shooting.
