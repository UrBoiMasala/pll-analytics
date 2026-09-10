# The 2023 Possession Anomaly — Diagnosis and Repair (Phase 10 §B)

Phase 9 found that 2023 carried **97.0 possessions per game** against a
five-season median of 89.1, **43.2%** flagged-ambiguous possessions, and a large
block of goals with no faceoff logged after them. It concluded that 2023's
per-possession metrics were **not cross-season comparable** and stopped there.

Phase 10 went back to the raw events. The faceoffs are not missing. They are in
the wrong place, and the feed itself says so.

Labels: **OBSERVED** · **DERIVED** · **INFERRED** · **UNRESOLVED**.

Sources: `possession_repair_evidence_2022_2026.csv`,
`2023_possession_repair_audit.csv`, `2023_possession_sensitivity.csv`,
`possession_stats_original_vs_repaired.csv`,
`possession_repair_residual_by_game.csv`,
`possession_team_rank_stability.csv`, `data/processed/<year>/possessions_repaired.csv`.

---

## 1. What Phase 9's diagnosis got wrong

Phase 9 described the anomaly as **missing faceoff events**. That reading was
natural and it was wrong. 2023 logs **26.28 faceoffs per game** against 26.02 in
2026, 26.51 in 2024, 26.27 in 2025 and 25.93 in 2022 — the normal number, in a
season with a normal number of goals (22.76/game against 21.8–22.7 elsewhere).

The faceoffs exist. What differs is where they sit in the event stream.

---

## 2. The defect — **OBSERVED**

`event_number` is the index of the event in the raw feed's `items` array
(`pll_pbp_extractor.normalize_play_by_play`), and the Phase 4 possession state
machine processes events in that order. In **12 games of 2023** the feed emits
the faceoff that FOLLOWS a goal **before** that goal, and stamps it with the
goal's own clock.

The real `championship-2023-9-22`, period 1:

| array pos | `markerId` | clock | `secondsPassed` | team | event |
|---|---|---|---|---|---|
| 17 | `turnover-7910` | 08:17 | 223 | ARC | turnover |
| 18 | **`9000`** | 07:40 | **260** | WAT | **faceoff** win Z. Currier, *GB WAT Z. Currier* |
| 19 | **`shot-8900`** | 07:40 | **260** | WAT | **GOAL** by R. Conrad |
| 20 | `groundball-9100` | 07:34 | **266** | WAT | groundball picked up by Z. Currier |

Three independent facts identify this as a feed ordering defect rather than
real play:

**2.1 The feed's own sequence number contradicts the array order.** `markerId`
is a monotone counter carried on every event and stored as `event_id`. Here it
reads 7910 → **9000** → **8900** → 9100. Sorted, the goal (8900) comes before
the faceoff (9000), which comes before the ground ball (9100) — exactly where
lacrosse puts them. Array order and `markerId` order disagree on precisely
these rows.

**2.2 A goal sits between a faceoff and its own ground ball, which is
impossible.** The faceoff row names its ground-ball recoverer in `gbPlayerId`
(here Currier, `000409`), and that recovery is logged as a separate `groundball`
event. A faceoff and the recovery of that same draw are **one moment**, and in
every season they share `seconds_passed` exactly:

| | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| faceoffs with a companion GB | 973 | 1,073 | 1,028 | 948 | 1,086 |
| companion GB at the **same** second | **973** | 805 | 984 | **948** | **1,083** |
| companion GB **later** | 0 | **265** | 43 | 0 | 1 |

2023 is the outlier by a factor of six, and 265 of 265 of its late-companion
cases fall in the same 12 games.

**2.3 The repaired interval matches the clean seasons.** Under the repair the
goal-to-faceoff interval in 2023 becomes median 3s / mean 4.6s, against 2025's
median 5s / mean 5.9s and 2026's median 4s / mean 5.4s. **This distribution was
never targeted by the rule** — it is a post-hoc diagnostic, and it is reported
as one.

---

## 3. The evidence taxonomy

The repository already carries `PASS / KNOWN_DATA_ISSUE / UNRESOLVED` for
validation and `OBSERVED / DERIVED / MODELED / INFERRED / UNSUPPORTED` for
metrics. Neither fits a per-sequence repair decision, so Phase 10 adds a
narrower scale and **maps it onto the existing vocabulary** rather than
replacing it.

| Class | Condition | Repo label | Repaired? |
|---|---|---|---|
| **DIRECT** | `markerId` contradicts array order **and** the faceoff's companion ground ball is the very next event after the goal | OBSERVED | **yes** |
| **DIRECT_TIMING** | the companion ground ball is the next event and is later than the faceoff: order already right, timestamp wrong | OBSERVED | **yes** |
| **STRONGLY_INFERRED** | `markerId` contradicts array order but the faceoff logged no companion ground ball, so the true time is unrecoverable | INFERRED | no — sensitivity only |
| **DUPLICATE_FACEOFF_EVENT** | the same faceoff appears twice, once mis-stamped before the goal and once correctly after it | KNOWN_DATA_ISSUE | no |
| **WEAKLY_INFERRED** | odd, but no feed field implies the direction of a fix | INFERRED | **never** |
| **UNRESOLVED** | the two sequence sources disagree, or the displacement is wider than one event | UNRESOLVED | **never** |

### Counts, all five seasons — **OBSERVED**

| | DIRECT | DIRECT_TIMING | DUPLICATE | STRONGLY_INFERRED | UNRESOLVED |
|---|---|---|---|---|---|
| 2022 | 0 | 0 | 0 | 9 | 0 |
| **2023** | **199** | **57** | 0 | 26 | 9 |
| 2024 | 1 | 0 | **33** | 4 | 9 |
| 2025 | 0 | 0 | 0 | 1 | 0 |
| 2026 | 0 | 0 | 0 | 3 | 1 |

Two things follow that were not designed for:

1. **2022, 2025 and 2026 contain zero rows in the two repaired classes.** The
   frozen 2026 possession layer is left bit-identical *by construction*, not by
   exemption. The rule is season-agnostic; it fires where the defect is.
2. **2024 has a different defect.** Its 33 cases are the *same faceoff logged
   twice* — once mis-stamped before the goal, once correctly after it with its
   ground ball. The repair for that is de-duplication, which touches the
   canonical event layer, and Phase 10 repairs **order only**. Reported, not
   fixed. See §9.

---

## 4. The repair, stated exactly

Two operations, both applied only to events the feed already contains:

```
transpose : swap the faceoff's and the goal's own event_number values
retime    : set the faceoff's seconds_passed to its companion ground ball's
```

* No event is created, deleted, duplicated or re-attributed.
* No `team_id`, `player_id`, `shot_type`, `is_valid_goal`, score or outcome
  field is touched anywhere. **Scoring reconciliation is therefore unaffected by
  construction**, and validation check 7 verifies it anyway.
* Every other event keeps the `event_number` the feed gave it, so an unrepaired
  season comes back byte-for-byte identical.
* The Phase 4 state machine is **imported, not modified**. A repair that had to
  change the possession rules would not be a data repair.

### Why the "single adjacent displacement" precondition exists

Both repaired classes require the scramble to be **one event wide** — the goal
alone between the faceoff and its ground ball, or nothing at all. This is not a
convenience. A two-event transposition restores `markerId` order only when the
displacement is one event wide; applied to a wider scramble it strands the
faceoff after events that `markerId` puts before it, which surfaces immediately
as a possession of **negative duration**.

One real 2023 sequence does this (`playoffs-quarterfinal-2-2023-9-1`, period 2,
`markerId` 1023300 → 1023400 → 1023410 → 1023700 → **1023800** → 1023900, with
the faceoff at 1023800 emitted first). It is classified **UNRESOLVED** and left
alone. An assertion in the build refuses to write any possession of negative
duration, and `tests/test_phase10.py::TestRepairRuleUnit` covers this exact
sequence as a false positive.

---

## 5. ORIGINAL_2023 vs REPAIRED_2023 — **OBSERVED**

`possession_stats_original_vs_repaired.csv`, primary variant
`V2_direct_and_timing`. The five-season context is given so the reader can judge
plausibility; **it was not used to decide any repair**.

| Metric | **2023 original** | **2023 repaired** | 2022 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| Possessions | 4,460 | **4,204** | 3,795 | 4,045 | 4,009 | 4,388 |
| Possessions / game | **96.96** | **91.39** | 82.50 | 89.89 | 89.09 | 87.76 |
| Team possessions / game | 48.48 | **45.70** | 41.25 | 44.94 | 44.54 | 43.88 |
| Points per possession *(= offensive efficiency = defensive efficiency at league level)* | **0.2520** | **0.2674** | 0.2819 | 0.2621 | 0.2729 | 0.2712 |
| Goals per possession | 0.2348 | **0.2490** | 0.2669 | 0.2425 | 0.2544 | 0.2548 |
| Shots per possession | **0.8621** | **0.9146** | 0.9360 | 0.9308 | 0.9379 | 0.9357 |
| Possession-ending turnover rate | 0.2957 | **0.3137** | 0.3436 | 0.3226 | 0.3051 | 0.3081 |
| Possession ambiguity | **43.2%** | **35.0%** | 31.9% | 34.0% | 35.9% | 36.2% |
| Truncated rate | 2.87% | 3.04% | 3.11% | 3.24% | 3.42% | 3.62% |
| Mean duration (untruncated) | 22.30s | **23.62s** | 26.25s | 23.48s | 23.93s | 23.59s |
| Median duration (untruncated) | 17s | **20s** | 22s | 19s | 20s | 20s |
| Goals followed by a faceoff | **72.0%** | **91.1%** | 94.9% | 99.1% | 97.9% | 96.5% |
| `ambiguous_control_change` ends | 1,027 | **771** | 640 | 737 | 755 | 838 |
| `other_confirmed_control` starts | 1,119 | **836** | 672 | 761 | 813 | 922 |
| **Total PLL points** | **1,124** | **1,124** | 1,070 | 1,060 | 1,094 | 1,190 |

**The Phase 9 paradox is resolved.** Phase 9 noted that 2023 had the *highest*
points per game and the *lowest* offensive efficiency of the five seasons, and
that both could not be true of the offence. After repair 2023's points per
possession (0.2674) sits above 2024's (0.2621) and inside the five-season range,
while its points per game are unchanged — because the repair changed the
denominator and left the numerator alone.

### Team rankings do not move at all

`possession_team_rank_stability.csv`: **0 of 40 team-season offensive-efficiency
ranks change**, in any season, under the primary repair. Every 2023 team's
offensive efficiency rises (ARC 0.2720 → 0.2840, CAN 0.3213 → 0.3333, WAT 0.2796
→ 0.3054, WHP 0.2569 → 0.2840, …) and the order is identical.

This is the cleanest possible statement of what the defect was: it inflated a
**denominator uniformly**, so it corrupted cross-season comparison and left
within-season conclusions intact.

---

## 6. Sensitivity — `2023_possession_sensitivity.csv`

Five variants, all built from the same detection pass:

| Variant | Classes applied | 2023 poss/game | 2023 ambiguity | 2023 points/poss | 2022/25/26 identical? |
|---|---|---|---|---|---|
| `V0_original` | none | 96.96 | 43.2% | 0.2520 | — |
| `V1_direct_only` | DIRECT | 91.39 | 35.0% | 0.2674 | **yes** |
| **`V2_direct_and_timing`** *(primary)* | DIRECT + DIRECT_TIMING | **91.39** | **35.0%** | **0.2674** | **yes** |
| `V3_direct_and_strongly_inferred` | DIRECT + STRONGLY_INFERRED | 90.78 | 33.8% | 0.2692 | no |
| `V4_all_repairable` | all three | 90.78 | 33.8% | 0.2692 | no |

**The answer barely depends on the choice.** Adding the 26 STRONGLY_INFERRED
cases moves 2023 by 0.6 possessions per game and 0.0018 points per possession.
It also moves 2022, 2025 and 2026, which is exactly why it is not in the primary
variant: those seasons' 13 cases have no companion ground ball to confirm the
correction, and moving a frozen layer on inferred evidence is not a trade this
phase is willing to make for a third of a possession per game.

`V1` and `V2` are identical in possession *counts* — the 57 DIRECT_TIMING cases
correct timestamps only — but differ in possession **durations**, which is why
V2 is primary: the duration numbers in §5 are the ones a later phase would use.

---

## 7. What the repair did NOT fix — **UNRESOLVED**

`possession_repair_residual_by_game.csv`.

| | 2022 | **2023** | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| Goals with no faceoff after them, before | 51 | **288** | 10 | 21 | 39 |
| …after the repair | 51 | **91** | 9 | 21 | 39 |
| Faceoff shortfall vs `goals + periods` | 14 | **27** | 20 | 20 | 20 |
| Games left `CLEAN` | 19/46 | 17/46 | 38/45 | 28/45 | 24/50 |

2023's residual is still the largest of the five seasons, and it is honestly
still elevated: 91 against 39 in 2026 and 51 in 2022. It is now the **same kind**
of residual the other seasons carry rather than a different one, and the
faceoff shortfall — the number of draws the feed simply never logged — is now
*inside* the range every other season occupies.

One game remains genuinely damaged: **`playoffs-quarterfinal-1-2023-9-1`** logs
30 goals and only **21 faceoffs**, a shortfall of 13, and keeps 14 unfollowed
goals after the repair. No reordering can recover events that were never
written. It is flagged `UNRESOLVED_MISSING_FACEOFF_EVENTS` and its possession
count remains inflated.

---

## 8. Publication decision, and the blast radius of adopting the repair

**`possessions.csv` is unchanged in every season.** The repaired layer is
published alongside it as `data/processed/<year>/possessions_repaired.csv`.

Why not overwrite:

* Section A of the Phase 10 brief freezes Phases 1–9 output. Overwriting four
  seasons' possessions would cascade through `team_game_advanced`,
  `team_season_advanced`, `team_stats_YEAR`, `team_leaderboards_YEAR`, the
  pooled `team_stats_2022_2026.csv`, `multi_season_metric_distributions.csv`
  and every Phase 9 sanity flag that quotes a possession number.
* Every prior validator and test would then need its expected values re-derived
  in the same commit that changes the data, which is the failure mode
  reproducible-research practice exists to prevent.

**What adoption would change, measured:**

| Layer | Seasons affected | Change |
|---|---|---|
| `possessions.csv` | 2023, 2024 | −256 and −2 possessions |
| `team_game_advanced.csv` / `team_season_advanced.csv` | 2023, 2024 | every possession-denominated column |
| `team_stats_YEAR.csv` / `team_leaderboards_YEAR.csv` | 2023, 2024 | pace, efficiency, per-possession rates; **rankings unchanged** |
| pooled `team_stats_2022_2026.csv` | rows for 2023, 2024 | as above |
| `player_stats_YEAR.csv`, `player_value_components.csv`, `player_adjusted_value.csv` | none measurably | possessions enter the player layer only through the *context* baselines in `player_value_baselines.sql` (`points_per_possession_league`, `points_per_faceoff_started_possession`), which no value formula consumes |
| 2026 anything | **none** | zero candidates in the repaired classes |

**Recommendation:** adopt `V2_direct_and_timing` into the canonical layer in
Phase 11, in a commit that does nothing else, and re-derive the affected
expected values in the same commit. Until then, any cross-season
possession-denominated comparison **must state which layer it used**.

---

## 9. The 2024 duplicate-faceoff finding — **KNOWN_DATA_ISSUE, not repaired**

`2024_game_10`, period 1, is the canonical shape:

```
markerId 1000  151s  CHA faceoff  N. Rowlett (vs M. Sisselberger)  GB J. Rowlett
markerId  900  151s  ARC GOAL     M. O'Keefe
markerId 1100  158s  CHA faceoff  N. Rowlett (vs M. Sisselberger)  GB J. Rowlett   <-- identical
markerId 1200  158s  CHA groundball  J. Rowlett
```

The two faceoff rows agree on winner, loser and ground-ball recoverer. Phase
3.5's `is_duplicate_faceoff` did not catch them because their clocks differ.
**33 such pairs exist in 4 games of 2024**, and one in 2023.

The correct repair is de-duplication, which changes the canonical event layer
and the official faceoff counts that Phase 2 reconciles against. That is out of
scope for Phase 10 and is recommended for Phase 11 as a separate, separately
validated correction.

---

## 10. Cross-season comparability verdict

**2023 per-possession metrics are comparable across seasons when computed on
`possessions_repaired.csv`, with the residual in §7 stated.** They remain
**NOT comparable** on the frozen `possessions.csv`, exactly as Phase 9 said.

The three residual reservations, stated rather than buried:

1. 91 of 2023's 1,047 goals (8.7%) still have no faceoff logged after them,
   against 3.5% in 2026 — so 2023's possession count is still mildly inflated.
2. `playoffs-quarterfinal-1-2023-9-1` is materially damaged and no repair
   recovers it.
3. 2022 sits at 82.5 possessions per game, **7.4% below the five-season
   median**, and Phase 10 found no defect that explains it. Phase 9's
   `POSSESSION_COUNT_ANOMALY` flag for 2022 stands, unexplained. 2023 was
   diagnosed; 2022 was not.

---

## 11. Reproducing this

```
python3 scripts/pll_phase10_possession_repair.py    # detection, repair, all statistics
python3 scripts/pll_validate_phase10.py             # checks 5-8 and 23 cover this document
python3 -m unittest tests.test_phase10 -v           # 9 unit tests on the rules themselves
```

Every step is deterministic and contains no random component. Validation check
19 re-runs the module and compares every output by SHA-256.
