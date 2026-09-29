> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](../PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](../METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Multi-Season Feasibility (Phase 7 §20)

Phase 6 named the single-season sample as its largest limitation. Phase 7's
reliability work quantifies exactly how much it costs: only 13 of 192 shooters
and 1 of 16 goalies have enough of their own record for it to outweigh the
league prior.

This document reports what a **read-only investigation** of prior PLL seasons
found. **No prior-season data was ingested.** The production dataset remains
2026-only, as the Phase 7 brief requires. Nothing under `data/raw/` or
`data/processed/` was added, changed or removed by this investigation.

Investigated 2026-09-07 against
`https://stats.premierlacrosseleague.com/api/v4`.

---

## 1. Is the same data structure available for prior seasons?

**Yes, for 2021 onward.** The same four endpoints the Phase 3 ingestion uses
(`games?year=`, `games/{slug}/play-by-plays`, `games/{slug}/players/stats`,
`games/{slug}/teams/stats`) return well-formed payloads for every year queried.

| Season | Games on schedule | Completed | Play-by-play | Player stats | Team stats |
|---|---|---|---|---|---|
| 2019 | 37 | 0 | — | — | — |
| 2020 | 20 | 0 | — | — | — |
| 2021 | 44 | 44 | yes | yes | yes |
| 2022 | 52 | 52 | yes | yes | yes |
| 2023 | 48 | 44 | yes | yes | yes |
| 2024 | 47 | 47 | yes | yes | yes |
| 2025 | 47 | 47 | yes | yes | yes |
| 2026 | 54 | 53 | yes | yes | yes |

2019 and 2020 return schedule rows with `eventStatus` 0 for every game — the
league's earliest seasons are listed but not marked complete in this API, and
their per-game endpoints were not probed further.

### One operational finding, which affects the existing pipeline

The API now rejects requests without an `Origin` header:

```
HTTP 403  {"error":"Origin not allowed"}
```

`Origin: https://stats.premierlacrosseleague.com` is accepted; the site's own
public origin and no origin at all are refused. **The current
`scripts/pll_ingest_season.py` sends no `Origin` header**, so a re-run of the
2026 ingestion today would fail with a 403 rather than a data error. This is
recorded here rather than fixed, because Phase 7's scope is the analytics layer
and the cached 2026 raw data is intact; it is a one-line change whenever the
ingestion is next run.

---

## 2. Are the stat definitions comparable?

**2022–2025: yes, structurally identical to 2026.** Sampling five completed
games from each season:

| Season | Event types present | Shot types present | Position labels |
|---|---|---|---|
| 2022 | the same 9 as 2026 | `1_PT`, `2_PT`, `MU` | A, M, SSDM, LSM, D, FO, G |
| 2023 | the same 9 as 2026 | `1_PT`, `2_PT`, `MU`, `MU_2_PT` | same |
| 2024 | the same 9 as 2026 | `1_PT`, `2_PT`, `MU` | same |
| 2025 | the same 9 as 2026 | `1_PT`, `2_PT`, `MU`, `MU_2_PT` | same |
| 2026 | pregame, faceoff, groundball, shot, goal, shotclockexpired, turnover, penalty, gameEnd | `1_PT`, `2_PT`, `MU` | same |

The JSON key sets are **identical** — no key present in 2026 is missing in any
sampled prior-season game, and none of them carries a key 2026 does not. Player
box-score keys match exactly as well.

**2021: no.** It is a different feed generation and would need its own cleaning
pass:

- **Every goal is logged twice.** One structured event (`GOAL by L. Thompson.`,
  with `shotType`) and one raw text-feed line (`CAN: 1st-11:02: SHOT GOOD S:
  #4-Thompson`, with `shotType` null). The sampled game shows 46 `goal` events
  for 23 actual goals, confirmed against the team box score (11 + 12).
- **Extra event types** that no later season uses: `ballcleared` (218 in five
  games), `powerplayend`, `timeoutcalled`, `offside`, `challengeend`.
- **No two-point tagging.** `2_PT` does not appear at all in the 2021 sample and
  the sampled game's team box score reports `twoPointGoals = 0` for both teams,
  despite the two-point arc existing in 2021.

2021 is therefore excluded from any near-term multi-season plan.

---

## 3. Are the two-point rules comparable?

The two-point arc has been a PLL rule throughout, but **the feed's tagging of it
is only reliable from 2022**. 2023 and 2025 also carry `MU_2_PT` (man-up
two-point goals), which 2026 documents as appearing on goal events only.

Because every Phase 6 expectation is denominated in **points** and a two-point
attempt is valued at `P(goal) × 2`, a season whose two-point attempts are
untagged cannot be pooled: its shots would all be priced as one-pointers. This
is the specific reason 2021 cannot be added without bespoke work, and the
specific reason 2022–2025 can.

A residual risk worth stating: the two-point **conversion rate** may not be
stable across seasons even where tagging is. Pooling seasons for a shrinkage
prior assumes the underlying league rate is comparable, and that assumption
should be tested season by season before any pooling, not asserted.

---

## 4. Would historical data materially improve the shrinkage priors?

**Yes, and by a large factor.** 2022–2025 add **190 completed games** to 2026's
50 — a roughly 4.8× increase in the estimation base.

What that buys, per rate:

| Rate | 2026 prior strength | 2026 players at reliability ≥ 0.5 | What more seasons would change |
|---|---|---|---|
| Faceoff win % | 15.9 draws | 18 / 47 | Already the best-identified rate. More seasons would sharpen the prior itself and allow a genuine year-to-year stability test |
| Shooting % | 70.8 shots | 13 / 192 | **The biggest gain.** A regular starter takes roughly 80–120 attempts a season; four more seasons puts most regulars comfortably past 71 attempts, turning a 7% identification rate into a majority |
| Save % | 300.3 SOG | **1 / 16** | **The other big gain.** A busy goalie faces ~300 shots on goal a season, which is exactly the prior strength, so one season buys reliability 0.5 and no more. Four seasons would put every regular starter above 0.8 |
| Two-point % | capped at 1,000,000 | 0 / 127 | 536 league attempts in 2026; four more seasons would give roughly 2,700. That is the difference between "no evidence of any spread" and a testable question. **It would not automatically make two-point skill measurable** — the honest statement is that the test becomes possible, not that it will pass |

There is a second, subtler gain. A multi-season panel makes the **year-to-year
correlation** of each rate estimable, which is the direct measure of whether a
rate reflects a persistent player property. That is a stronger form of evidence
than the within-season prior strength Phase 7 currently relies on, and it is the
only way to check whether the empirical-Bayes prior is doing the right thing.

---

## 5. Do player IDs remain linkable?

**Yes.** `officialId` is a stable, league-wide player identifier, not a
per-season key:

- Connor Buczek carries `000233` in a 2021 game.
- Liam Entenmann carries `003079` in 2025 and the same id in the 2026 roster.
- Of 157 distinct players sampled across eight 2025 games, **125 (79.6%)** appear
  on the 2026 roster.

The zero-padded six-character convention this repo uses throughout would apply
unchanged. Team codes are the linkage risk rather than player ids: the league
has renamed and relocated clubs (the 2021 slugs are team-name-based,
`cannons-redwoods-2021-6-04`, while 2024–2026 use `YYYY_game_N`), so a
team-season crosswalk would be needed for anything team-level.

---

## 6. Recommendation

**Do not expand the production dataset in Phase 7.** Nothing in the Phase 7
deliverables is blocked by the single-season sample: usage, position mapping,
positional baselines, reliability and the raw/shrunk policy are all computable
on 2026 and all correctly report the limitation rather than working around it.

**Ingesting 2022–2025 is the single highest-value next step for this project**,
and it is a better use of effort than anything in Phase 8's stated scope. It
would move shooting and save percentage from "weakly identified" to genuinely
rankable, make the two-point question testable, and permit the year-to-year
stability analysis that would validate the shrinkage priors rather than
assuming them.

If it is undertaken, the work is:

1. Add the `Origin` header to the ingestion (§1).
2. Ingest 2022–2025 into `data/raw/<year>/`, leaving 2026 untouched.
3. Re-run the Phase 1–2 validation per season. Do **not** assume the 2026
   anomaly profile carries over — the Phase 4.25 findings (duplicate ground
   balls, unattributed turnovers, the placeholder score fields) were established
   season-specifically and must be re-established.
4. Build the team-season crosswalk for franchise moves.
5. Re-estimate the shrinkage priors on the pooled panel, and **report the
   single-season and pooled priors side by side** rather than replacing one with
   the other.
6. Leave 2021 out until its duplicate-goal logging and missing two-point tags
   have their own cleaning pass and validation.

**Every number in this document was obtained by read-only HTTP GETs against the
public API. No file in the repository was created or modified by the
investigation.**
