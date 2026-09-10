> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Player Identity Across Seasons (2022–2026)

Cross-season player identity is the load-bearing assumption behind every
career-level statistic in this project. If two ids are the same person and are
not merged, his career is split; if two people share an id or are merged on a
name, two careers are fused. Both errors are silent and both corrupt the
reliability findings in
[`MULTI_SEASON_RELIABILITY.md`](MULTI_SEASON_RELIABILITY.md).

Labels: **OBSERVED** · **DERIVED** · **MODELED** · **INFERRED** ·
**UNSUPPORTED**. Source: `historical_player_identity_audit.csv`.

---

## 1. The rule

**Identity is `officialId`. Nothing else.**

**OBSERVED.** The feed carries an integer `officialId` on every player-game row.
It is stored as the canonical, zero-padded 6-character `player_id` and is the
only join key used anywhere in this repository.

**No player is ever merged on a name.** Name evidence is used in exactly one
direction — to *raise a flag* that two ids might be one person, or that one id's
name changed — and every such case is reported for adjudication rather than
resolved. A fuzzy name match is a hypothesis, not an identity.

---

## 2. What the five seasons actually contain — **OBSERVED**

| | |
|---|---|
| Distinct `officialId`s, 2022–2026 | **423** |
| Player-season rows | **1,032** |
| Ids appearing in more than one season | **266** (62.9%) |
| Ids whose identity status is `confirmed` | **423 (100%)** |
| Ids flagged for review | **0** |
| Ids not safe to aggregate across seasons | **0** |

### Career length distribution

| Seasons played | Players |
|---|---|
| 1 | 157 |
| 2 | 88 |
| 3 | 71 |
| 4 | 49 |
| **5 (every season)** | **58** |

---

## 3. The audit found the feed to be unusually clean — **OBSERVED**

Three independent checks, each of which could have found a problem and did not:

| Check | Result |
|---|---|
| One `officialId` carrying more than one name spelling | **0 of 423** |
| One name carried by more than one `officialId` | **0** |
| One *normalised* name (case, punctuation, Jr/Sr/III stripped) carried by more than one id | **0** |

**This is a genuinely unusual result** and it was verified independently of the
audit script before being relied on. It means the hardest part of a multi-season
build — reconciling identities — required no reconciliation at all, and that
every career-level statistic in Phase 9 rests on an exact key rather than a
matching heuristic.

**INFERRED caveat.** "No name collision was observed" is not "no name collision
can occur". Two players with the same name in the same season would be two ids
and would be correctly kept apart; two ids for one person across seasons would
produce a split career that the name check *would* flag. Neither pattern occurs
in 2022–2026. A future season could introduce either, which is why the check
runs every time rather than being retired.

---

## 4. Players who move, change role, or disappear — **OBSERVED**

These are recorded, not treated as identity problems: the id is stable through
all of them.

| Pattern | Count | Example |
|---|---|---|
| Changed team at least once | **100** | Dylan Molloy — ATL, CHR, RED across 5 seasons |
| Played for 3 different franchises | 8 | Will Manny — ARC, CAN, WHP |
| Changed listed position | **42** | Jake Carraway — A then M; Brett Kennedy — D then LSM |
| Season gap (absent, then returned) | **26** | Tim Troutner — 2022, 2023, 2024, **2026** |

**INFERRED.** A position change is a genuine analytical hazard even though it is
not an identity hazard. Phase 7's `canonical_position` is resolved **per season**
from that season's box scores, so a player who moved from attack to midfield is
correctly labelled differently in each season, and a career-pooled rate for him
mixes two roles. That is a limitation of career pooling, recorded here and in
the reliability document, not a defect in the identity system.

**Franchise turnover compounds it:** Chrome (CHR) exits after 2023 and Outlaws
(OUT) enter in 2024, so a "team" is also not a stable unit across the window —
see [`OPPONENT_ADJUSTMENT_FEASIBILITY.md`](OPPONENT_ADJUSTMENT_FEASIBILITY.md) §4.

---

## 5. Ids that legitimately do not resolve — **OBSERVED**

2022 carries **19** player ids referenced by events but absent from
`players.csv`. Every one of them appears **only in the four preseason
scrimmages** of 2022-05-31 — trialists who never played a regular-season game
and therefore never appear in a box score.

This is correct behaviour, not a gap. Phase 9 validation check 5 asserts the
precise invariant that makes it safe: **every id referenced by an
analytics-eligible game resolves**, and anything unresolved is confined to an
excluded game. The same scoping applies to the all-star roster codes ASA/ASH in
2023–2024.

---

## 6. When a statistic may aggregate across seasons

**Permitted — the identity is exact:**

- Career trial and success totals for a rate (`shooting_pct`, `save_pct`,
  `faceoff_win_pct`, `one_point_pct`, `turnovers_per_touch`). This is what
  `pooled_player_career` in the reliability analysis does.
- Counting a player's seasons, teams, or appearances.

**Permitted with the caveat stated on the row:**

- A career rate for one of the 42 players whose listed position changed — it
  mixes roles.
- Any career figure spanning a franchise change (100 players) — team context is
  not held constant.

**Not permitted — UNSUPPORTED:**

- Treating a career rate as an estimate of *current* ability. Ageing and role
  change are not modelled anywhere in this repository.
- Aggregating across seasons for any player whose `safe_to_aggregate_across_seasons`
  is false. That count is currently **0**, and the column exists so the answer is
  checked rather than assumed.
- Merging two ids, under any circumstances, without new evidence from the source
  that they are the same registration.
