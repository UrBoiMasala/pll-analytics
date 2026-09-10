# Two-Point Historical Analysis (2022–2026)

PLL's two-point arc is the single largest structural difference between a PLL
statistical system and an NCAA one, and Phase 8's sharpest refusal was to rank
individual two-point shooting. Five seasons and **2,464 two-point attempts**
now exist. This document tests that refusal rather than assuming it, and
separately reports what the extra seasons *did* change.

Labels: **OBSERVED** · **DERIVED** · **MODELED** · **INFERRED** ·
**UNSUPPORTED**.

Sources: `multi_season_two_point_analysis.csv`,
`multi_season_two_point_identification.csv`.

---

## 1. League economics by season — **OBSERVED**

| Season | 1PT att | 1PT G | 2PT att | 2PT G | 2PT share | 1PT conv | 2PT conv | Wilson 95% | Pts/1PT att | Pts/2PT att | **Difference** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 3,181 | 956 | 371 | 57 | 10.4% | .3005 | .1536 | [.121, .194] | .3005 | .3073 | **+0.0067** |
| 2023 | 3,325 | 970 | 520 | 77 | 13.5% | .2917 | .1481 | [.120, .181] | .2917 | .2962 | **+0.0044** |
| 2024 | 3,237 | 902 | 528 | 79 | 14.0% | .2787 | .1496 | [.122, .183] | .2787 | .2992 | **+0.0206** |
| 2025 | 3,251 | 946 | 509 | 74 | 13.5% | .2910 | .1454 | [.117, .179] | .2910 | .2908 | **−0.0002** |
| 2026 | 3,570 | 1,046 | 536 | 72 | 13.1% | .2930 | .1343 | [.108, .166] | .2930 | .2687 | **−0.0243** |
| **POOLED** | **16,564** | **4,820** | **2,464** | **359** | **12.9%** | **.2910** | **.1457** | **[.132, .160]** | **.2910** | **.2914** | **+0.0004** |

### This overturns a 2026 impression — **OBSERVED**

Phase 8 reported that in 2026 the two-point shot returned **0.024 points fewer
per attempt** than the one-point shot, and correctly declined to draw a
shot-selection conclusion from it. Five seasons show that **2026 is the outlier**:
the return difference was *positive* in 2022, 2023 and 2024, essentially zero in
2025, and over 2,464 pooled attempts it is **+0.0004 — break-even to four
decimal places**.

**INFERRED.** The honest statement is not "the long shot is a bad shot" and not
"the long shot is a good shot". It is: **at league level the two-point shot has
returned almost exactly what the one-point shot returned, and a single season's
sign is noise.** A team-season's two-point conversion rests on 38–83 attempts;
the Wilson intervals above overlap heavily across every season.

Two-point usage rose from 10.4% of attempts in 2022 to a 13–14% plateau from
2023 onward — a **modest** season effect (20.9% of variance between seasons),
consistent with teams settling on a stable rate rather than continuing to
increase it.

---

## 2. Is individual two-point ability identifiable? — **OBSERVED: NO**

The test is whether the observed spread of player conversion rates exceeds what
binomial noise alone would produce. If it does not, there is no between-player
signal for any estimator to recover.

| Scope | Shooters | Attempts | Median att | Observed variance | Binomial noise | **Excess** | κ | Max reliability | Identifiable |
|---|---|---|---|---|---|---|---|---|---|
| 2022 | 102 | 372 | 2 | 0.024805 | 0.036085 | **−0.011280** | capped 1e6 | 0.000017 | **No** |
| 2023 | 114 | 520 | 3 | 0.022264 | 0.027656 | **−0.005392** | capped 1e6 | 0.000035 | **No** |
| 2024 | 122 | 528 | 2 | 0.027483 | 0.029399 | **−0.001916** | capped 1e6 | 0.000029 | **No** |
| 2025 | 120 | 509 | 2 | 0.020189 | 0.029292 | **−0.009103** | capped 1e6 | 0.000028 | **No** |
| 2026 | 127 | 536 | 2 | 0.023445 | 0.027552 | **−0.004107** | capped 1e6 | 0.000029 | **No** |
| **Pooled player-seasons** | 585 | 2,465 | 2 | 0.023642 | 0.029598 | **−0.005956** | capped 1e6 | 0.000035 | **No** |
| **Pooled player-CAREER** | 271 | 2,465 | 3 | 0.010224 | 0.013711 | **−0.003487** | capped 1e6 | 0.000110 | **No** |

**The excess variance is negative in every season and in both pooled scopes.**
Not small — negative. Five independent seasons replicate the 2026 result, and
career pooling, which rescued shooting and goalie identification, does not
rescue this one.

### Why five seasons did not help — **INFERRED**

The binding constraint is **attempts per player, not seasons**. The median
two-point shooter takes **2 attempts a season**, and career pooling raises that
only to **3**, because two-point shooting is spread thinly across many players
rather than concentrated in specialists. 271 career shooters share 2,464
attempts. Pooling multiplies the number of tiny samples without making any
sample large.

Year-to-year stability is likewise **untestable**: across five seasons only
**4** player pairs clear 20 attempts in consecutive seasons.

---

## 3. What is and is not published

**Published — production, descriptively:**
two-point goals, attempts, conversion with its denominator, attempt share,
points per attempt, the return difference, and Wilson intervals so a thin cell
looks thin. `two_point_audit_YEAR.csv` exists for every season, and
`two_point_audit_2022_2026.csv` pools them.

**Not published, in any season — UNSUPPORTED:**
a qualified two-point ability leaderboard, a two-point shooting *skill* rating,
or any shrunk two-point rate presented as an ability estimate. Every season's
`player_leaderboards_YEAR.csv` carries the two-point conversion rate under
`scope = ALL` with qualification rule `NOT_QUALIFIABLE_TWO_POINT` and **no
QUALIFIED scope at all**. Phase 9 validation check 14 and four tests fail if one
appears in any season.

---

## 4. The interpretation that must not be made

**Non-identification is not proof that players have equal two-point ability.**

It is a statement about *evidence*, not about *players*. A shooter who is
genuinely better over the arc almost certainly exists; what the data establishes
is that **2,464 attempts spread over 271 players cannot distinguish him from
chance.** Reporting "no measurable difference" as "no difference" would be the
same error in the opposite direction from the one the refusal exists to prevent.

**What would settle it — INFERRED:**

- Not more seasons of the same shape. At ~500 attempts a season league-wide,
  another five seasons would roughly double the pooled sample and leave the
  median career shooter around 5–6 attempts. That is still nowhere near the
  ~1,000-attempt scale at which a 0.15 rate separates players.
- A genuine two-point **specialist** — one player taking 40+ attempts a season
  for several seasons — would be individually estimable even while the
  population is not. Bryan Costabile's 29 attempts in 2026 is the closest the
  five seasons come.
- Shot location, which does not exist in this feed, would let the question be
  reframed as shot quality rather than shot outcome.

---

## 5. Summary

| Question | Answer | Basis |
|---|---|---|
| Is the two-point shot worth taking? | League-wide, it has returned **break-even** (+0.0004 pts/attempt over 2,464 attempts). 2026's negative was a one-season result. | OBSERVED |
| Did two-point usage change? | Rose 10.4% → ~13.5% of attempts after 2022, then flat. | OBSERVED |
| Can individual two-point ability be ranked? | **No**, in any season, pooled by season, or pooled by career. | OBSERVED |
| Did five seasons change that? | **No.** The excess variance is negative in all seven scopes tested. | OBSERVED |
| Does that mean players are equally good? | **No.** It means the evidence cannot separate them. | INFERRED |
| Will more seasons fix it? | Not at this attempt rate. | INFERRED |
