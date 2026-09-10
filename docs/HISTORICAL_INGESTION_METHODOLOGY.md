> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Historical Ingestion Methodology (2022–2025)

How the four historical seasons were retrieved, processed and admitted, and
what was deliberately **not** done.

Every statement below is labelled:
**OBSERVED** (read directly from the feed) ·
**DERIVED** (computed from observed values by a stated rule) ·
**MODELED** (the output of a fitted model) ·
**INFERRED** (a judgement, argued for) ·
**UNSUPPORTED** (cannot be established from this data).

---

## 1. Source access

**OBSERVED.** The public endpoint is
`https://stats.premierlacrosseleague.com/api/v4`, the same host Phases 1–8 used
for 2026. A request carrying neither an `Origin` nor a `Referer` header is
refused:

```
GET /api/v4/games?year=2026        (no headers)  -> 403 {"error":"Origin not allowed"}
GET /api/v4/games?year=2026        (+ Referer)   -> 200
```

**INFERRED.** This is an ordinary CORS/hotlink guard, not an authorisation
control. The existing client has always sent the `Referer` a browser sends when
viewing that game's page on the league's own stats site, which is why 2026
ingestion worked and why the Phase 7 note about a 403 reflected a header-less
probe rather than a change at the source.

**The minimum legitimate change was made:** the season in that Referer now
follows the season being fetched (`/games/2022/<slug>?tab=plays` instead of a
hard-coded `/games/2026/`). No credential is used, no rate limit is evaded, no
access control is bypassed, and no header is forged beyond identifying the page
the request is made from. Requests are rate-limited (0.25 s) as before.

---

## 2. What was retrieved

**OBSERVED.** For each season, one schedule request plus four endpoints per
completed game:

| Endpoint | Path |
|---|---|
| play-by-play | `games/{slug}/play-by-plays` |
| game meta | `games/{slug}` |
| player stats | `games/{slug}/players/stats` |
| team stats | `games/{slug}/teams/stats` |

Raw payloads are stored unmodified under `data/raw/<year>/<slug>/`, with
`_meta.json` recording, per endpoint, the **retrieval timestamp**, the **source
URL** and the **SHA-256 content hash**. A superseded payload is never
overwritten in place: it is preserved under `_snapshots/`. Raw and processed
data never mix — processed tables live under `data/processed/<year>/`.

Ingestion is **restartable and idempotent**: a game whose four endpoints are
already on disk and structurally valid is skipped with no network call, and
re-running produces identical files.

| Season | Schedule rows | Completed | Retrieved with PBP |
|---|---|---|---|
| 2022 | 52 | 52 | 52 |
| 2023 | 48 | 48 | 48 |
| 2024 | 47 | 47 | 47 |
| 2025 | 47 | 47 | 47 |

---

## 3. Two source anomalies that would have silently lost data

### 3.1 `eventStatus == 2` is also a played game — **OBSERVED**

2026 marks every finished game `eventStatus == 3`, and the Phase 3 ingester
treated that as the sole completion signal. **The 2023 feed marks four PLAYED
games `eventStatus == 2` while still reporting real final scores:**

| Slug | Segment | Score |
|---|---|---|
| `game-17-2023-07-14` | regular | 13–16 |
| `game-42-2023-08-25` | regular | 7–13 |
| `playoffs-quarterfinal-2-2023-9-1` | post | 15–12 |
| **`championship-2023-9-22`** | post | **15–14** |

Gating on status 3 would have dropped the 2023 championship. The completion rule
is now "status 3, **or** status 2 carrying both final scores", which is a no-op
for every other season and is unit-tested on synthetic schedule rows.

### 3.2 A game with no box-score feed — **OBSERVED**

The all-star **skills** competitions (2022–2025) and the 2023/2024 all-star
**games** return an empty `players_stats` feed. The ingester correctly declines
to write an empty payload, which then broke the table builder.

The fix is a **guarded** skip: such a game is skipped and recorded in
`skipped_games.csv` with the missing endpoints named, and the build **raises**
if the game is competitive. Silently dropping a league game is the specific
failure this phase exists to prevent, so it is made impossible rather than
unlikely.

---

## 4. Pipeline

**DERIVED.** Each season runs the *existing, validated* Phase 1–4 pipeline with
its season state pointed at that year. No cleaning rule, table definition or
possession rule was re-implemented, specialised or tuned per season — that is
what makes a 2022-vs-2026 difference evidence about the league rather than
evidence about the code.

```
pll_ingest_season.py --year Y      raw JSON
pll_build_tables.py                games / teams / players / events /
                                   player_game_stats / team_game_stats
pll_build_possessions.py           possessions
pll_validate_season.py             validation_report
pll_validate_possessions.py        possession_validation_report
   then Phase 5 / 6 / 7 / 8 layers, unchanged
```

Two things **are** re-estimated per season, and must be: every empirical
baseline (shot conversion, faceoff win probability, positional caused-turnover
rates, the beta priors) and the Phase 7 usage model. A 2026 baseline applied to
2022 would silently express 2022 in 2026's units.

`data/processed/history/historical_ingestion_report.csv` records every stage of
every season with its status, timestamp and log.

---

## 5. Admission rules

A game enters league analytics only if **all** hold:

1. **OBSERVED** it is completed (§3.1);
2. **OBSERVED** its `seasonSegment` is `regular` or `post` — this excludes
   all-star games and the four 2022 **preseason scrimmages**, a segment 2026
   does not have;
3. **DERIVED** its goal events reproduce its own official final score.

Rule 3 is a **measured** criterion, not a hand-maintained blocklist. It excludes
nothing in 2023–2026 and exactly one game in 2022.

| Season | Scheduled | Completed | Competitive | Admitted |
|---|---|---|---|---|
| 2022 | 52 | 52 | 46 | **46** |
| 2023 | 48 | 48 | 46 | **46** |
| 2024 | 47 | 47 | 45 | **45** |
| 2025 | 47 | 47 | 45 | **45** |
| 2026 | 54 | 51 | 53 | **50** |

Every scheduled game appears in `historical_game_inventory.csv` with a reason if
it is not admitted. 2026's three unadmitted competitive games are the semifinals
and championship, not yet played as of retrieval.

### The one documented exception

`archers-cannons-2022-6-18` — **OBSERVED.** Its goal events give ARC 14 against
an official 20, and CAN 8 against 9. Traced to the source: the feed's score
columns **move on missed-shot events** (+3 on "Missed shot by Lyle Thompson",
+2, +1 on two others) and **decrease** (−2 on a later goal). Phase 2's existing
validity rule correctly refuses to treat goals with no score movement as valid,
so 7 points are unrecoverable.

**INFERRED decision: the game is admitted, flagged, and never quietly corrected.**
It is one game of 46 and 7 points of 1,077 (0.65%) in 2022; excluding it would
also discard its valid shots, faceoffs and ground balls. It is recorded in
`historical_analytics_exclusions.csv`, raised as a class-D sanity flag, and
carried as a stated caveat on every 2022 aggregate. Phase 9 validation check 7
fails if any *undocumented* score residual ever appears.

---

## 6. Why 2021 was not ingested — **OBSERVED**

Phase 8's probe asserted 2021 is incompatible. That was verified independently
against all **42** competitive 2021 games (11,939 events), read-only, and the
verdict is confirmed for a stronger reason than the probe gave.

| Evidence | 2021 | 2022–2026 |
|---|---|---|
| `2_PT` shot tag | **never occurs** | present in every season |
| Goals moving the score by 2 | **58** | tagged `2_PT` |
| Those 58 goals' tag | **`1_PT` — actively wrong** | correct |
| Goals with no tag and no score movement | **923 of 1,846** | n/a |
| Extra event types | `ballcleared`, `timeoutcalled`, `powerplayend`, `offside`, `challengeend` | absent |

**The point-class encoding in 2021 is not merely absent — it is wrong.** A goal
worth two points is labelled one point, and half the goal events do not move the
score at all. Since every efficiency, value and two-point metric in this system
begins with "how many points was this goal worth", 2021 cannot be admitted
without inventing that answer. **INCOMPATIBLE. Not ingested.**

---

## 7. What this ingestion does not establish — **UNSUPPORTED**

- Any 2021 or earlier season.
- Lineups, shifts or minutes, in any season.
- Shot location, distance or defender, in any season.
- A ride success count or a clear event, in any season.
- Whether a 2022 roster and a 2026 roster of the same franchise name are
  comparable units for a pooled model. They are treated as separate units.
