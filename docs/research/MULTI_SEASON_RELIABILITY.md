> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](../PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](../METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Multi-Season Reliability and Shrinkage (2022–2026)

Phase 8's central negative finding was that one PLL season barely identifies
individual skill: 13 of 192 shooters and **1 of 16 goalies** cleared
reliability 0.5. This document answers the question Phase 9 exists to ask —
**does more data fix it?** — and the answer is *yes, but only if you pool the
right thing*.

Labels: **OBSERVED** · **DERIVED** · **MODELED** · **INFERRED** ·
**UNSUPPORTED**.

Source: `data/processed/history/multi_season_reliability.csv`,
`player_year_to_year_stability.csv`.

---

## 1. Method

**DERIVED.** Identical to Phases 6–8, using the *same imported estimator*
(`pll_player_value_models.beta_prior_by_moments`) so a pooled prior is directly
comparable with the per-season priors already published. For a set of binomial
rates, the prior strength κ is set so the between-player variance the prior
implies matches the observed variance net of the binomial noise each player's
own sample contributes. Reliability is `n / (n + κ)`; reliability ≥ 0.5 means
the posterior weights a player's own record above the league prior, and implies
`n ≥ κ` trials.

Three scopes, and the distinction between the last two is the whole finding:

| Scope | Unit | What it asks |
|---|---|---|
| `2026_only` | player-season | the Phase 8 baseline |
| `pooled_player_seasons` | player-season, 5 seasons | are there more *units*? |
| `pooled_player_career` | **player**, trials summed across seasons | does a *player* have more evidence? |

---

## 2. The result

| Rate | Scope | Players | Trials | κ | Reach rel. ≥ 0.5 |
|---|---|---|---|---|---|
| **shooting_pct** | 2026 only | 192 | 4,106 | 70.8 | **13** (6.8%) |
| | pooled seasons | 863 | 19,030 | 145.5 | **0** (0.0%) |
| | **pooled career** | 370 | 19,030 | 102.8 | **66** (17.8%) |
| **one_point_pct** | 2026 only | 168 | 3,570 | 75.3 | 8 (4.8%) |
| | pooled seasons | 781 | 16,565 | 156.3 | 0 |
| | **pooled career** | 340 | 16,565 | 124.5 | **47** (13.8%) |
| **save_pct** | 2026 only | 16 | 2,412 | 300.3 | **1** (6.3%) |
| | pooled seasons | 73 | 11,183 | 336.9 | 0 |
| | **pooled career** | 27 | 11,183 | 495.2 | **8** (29.6%) |
| **faceoff_win_pct** | 2026 only | 47 | 2,618 | 15.9 | 18 (38.3%) |
| | pooled seasons | 199 | 12,174 | 9.4 | 102 (51.3%) |
| | **pooled career** | 103 | 12,174 | 10.4 | **56** (54.4%) |
| **turnovers_per_touch** | 2026 only | 228 | 26,228 | 108.8 | 81 (35.5%) |
| | pooled career | 419 | 119,917 | 138.0 | **218** (52.0%) |
| **two_point_pct** | *every scope* | — | 2,465 | **capped 1e6** | **0** |

---

## 3. Three findings, in order of importance

### 3.1 Pooling player-SEASONS makes identification *worse* — **OBSERVED**

Adding four seasons as extra rows drives shooting κ from 70.8 to **145.5**, and
**not one** of 863 player-seasons reaches reliability 0.5 — worse than 2026
alone.

**INFERRED explanation, and it is not a paradox.** A larger pool of
player-seasons adds *units*, not *evidence per unit*: the median player-season
still carries only 11 shot attempts. What it does add is genuine heterogeneity —
a 2022 rookie and a 2026 veteran are different — which inflates the observed
between-player variance the estimator must explain, and the estimator correctly
attributes more of it to noise. **Stacking seasons as independent rows is the
wrong way to use them.**

### 3.2 Pooling a player's CAREER makes shooting and goalie skill identifiable — **OBSERVED**

Summing a player's trials across the seasons in which his identity is confirmed
raises the median shooter from 9 attempts (2026) to **18**, and the median
goalie from 148 trials to **354**.

| | 2026 only | Career-pooled | Change |
|---|---|---|---|
| Shooters clearing the gate | 13 of 192 | **66 of 370** | 6.8% → **17.8%** |
| Goalies clearing the gate | **1 of 16** | **8 of 27** | 6.3% → **29.6%** |
| Faceoff takers clearing | 18 of 47 | 56 of 103 | 38.3% → 54.4% |

**So: does shooting skill become identifiable? YES, at career level — for about
one shooter in six.** It remains unidentifiable for a single season.

**Does goalie skill become more identifiable? YES, and this is the largest
single improvement in the phase.** Phase 8's one-row save-percentage leaderboard
was the starkest symptom of one-season data; eight goalies now clear the gate on
career trials. Note κ *rises* to 495 — the true between-goalie spread is
genuinely small (implied sd 0.022) — so this is more evidence overcoming a
harder problem, not a lowered bar.

**INFERRED limitation.** A career estimate answers "how good has this player
been across 2022–2026", not "how good is he now". Ageing and role change are not
modelled. It is the right input to an ability claim and the wrong input to a
single-season retrospective.

### 3.3 Faceoff remains the one cleanly identified skill — **OBSERVED**

κ = 9.4–15.9 trials, against 70–500 for every other rate, and an implied true
between-player sd of 0.122–0.155, five to seven times any other rate's.
Faceoff is where individual skill genuinely separates from noise in this feed.

---

## 4. Year-to-year stability — **OBSERVED / MODELED**

Does last season predict next season? Player-seasons paired at ≥ 20 trials, with
a 2,000-sample bootstrap CI.

| Rate | Pairs | Players | Median trials | **Observed r** | 95% CI | Mean reliability | Disattenuated r (**MODELED**) |
|---|---|---|---|---|---|---|---|
| turnovers_per_touch | 481 | 227 | 107 | **0.368** | [0.263, 0.478] | 0.486 | 0.769 |
| shooting_pct | 177 | 86 | 52 | **0.350** | [0.202, 0.487] | 0.262 | ≥1.0 (capped) |
| one_point_pct | 161 | 80 | 48 | **0.293** | [0.126, 0.444] | 0.237 | ≥1.0 (capped) |
| faceoff_win_pct | 30 | 16 | 251 | 0.289 | [−0.079, 0.690] | 0.937 | 0.313 |
| save_pct | 36 | 16 | 220 | 0.162 | [−0.132, 0.481] | 0.348 | 0.462 |
| two_point_pct | **4** | — | — | — | — | — | **untestable** |

**A raw correlation between two noisy rates is attenuated**, so the observed
column *understates* persistence. The disattenuated column divides by the
geometric mean of the two years' reliabilities; it is **MODELED**, it is an
upper bound, and where it reaches 1.0 the honest reading is "the observed
correlation is consistent with *all* of the year-to-year signal being real
skill, measured badly" — not "skill is perfectly persistent".

**The two findings that matter:**

1. **Shooting and turnover tendency persist.** Both bootstrap CIs exclude zero
   comfortably. A player's shooting rate does carry information about next
   season, which is precisely what makes the career-pooled estimate legitimate
   rather than an averaging trick.
2. **Faceoff and save percentage cannot be shown to persist from this sample** —
   both CIs include zero, on 30 and 36 pairs. That is a *sample-size* statement
   about the number of goalies and specialists in an 8-team league, not evidence
   that the skills are transient. **Do not read a wide CI as a negative result.**
3. **Two-point stability is untestable**: only **4** player pairs clear 20
   attempts in consecutive seasons across five seasons.

---

## 5. Consequences for the published system

**Nothing in Phases 5–8 changed as a result of this.** The per-season priors
each season's own layer estimates are correct for that season, and the published
2026 numbers are untouched.

What this establishes for a later phase:

- **INFERRED.** A career-pooled, empirical-Bayes shrunk rate is a defensible
  ability estimate for shooting, one-point conversion, faceoff and turnover
  tendency, for the subset of players who clear the gate. It is the right input
  to a projection.
- **INFERRED.** A *single-season* rate remains an unreliable ability estimate for
  everything except faceoff, exactly as Phase 8 concluded. Five seasons did not
  change that; they explained it.
- **UNSUPPORTED.** Two-point shooting ability, at any scope. See
  [`TWO_POINT_HISTORICAL_ANALYSIS.md`](TWO_POINT_HISTORICAL_ANALYSIS.md).
- **UNSUPPORTED.** Any claim that a player's *current* ability equals his career
  rate. Ageing, role change and team context are not modelled anywhere.
