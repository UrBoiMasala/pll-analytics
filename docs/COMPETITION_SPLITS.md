# Competition splits and the 2026 update

The 2026 publication now includes 48 regular-season games and all five playoff games.
The All-Star game remains outside competitive analytics. The three added games are
526 (`2026-semifinal-1`), 527 (`2026-semifinal-2`), and 529 (`2026-championship-game`).
Their 650 processed events produce 262 possessions; all six team scores reconcile.
The existing possession validator passes all 17 hard checks. Its informational
control-alternation check is not a failure. Of the new possessions, 99 are flagged
ambiguous and 8 truncated; these source/reconstruction limitations remain visible.
Complete game coverage does not imply perfect event coverage or certain boundaries.

## Versioned inputs

`data/raw/` and `data/processed/` retain the historical research checkpoint, including
its partial 2026 schedule. New raw responses and per-game processed deltas live in
`data/updates/2026/`, with retrieval provenance, hashes, and validation results.
`pll_current_data.py` merges updates by whole game ID; the original three unplayed
schedule rows are replaced, not counted twice. The publication builder, validator,
and frontend use these current inputs. Retired research tools retain their original
frozen inputs and must not be mistaken for the current product.

Rebuild the downloaded update without network access:

```sh
python -B scripts/pll_import_2026_playoffs.py
python -B scripts/pll_build_publication.py
python -B scripts/pll_validate_publication.py
python -B scripts/pll_check_publication_determinism.py
python -B frontend/scripts/build.py
```

The importer’s `--fetch` option is for an initial retrieval only. It refuses to
replace the already-retrieved update. A later source revision needs separate review.

## 2022 pilot

- Regular season: 40 games, exported under `data/publication/2022/regular/`.
- Playoffs: six games, including the championship, under `data/publication/2022/post/`.
- Combined: the existing 46-game exports under `data/publication/2022/`.
- Championship Series: not held in calendar year 2022. No invented or zero-filled
  player statistics are published. The first Sixes event was February 2023, with
  qualification based on the 2022 season; it belongs to 2023 and uses different rules.

The frontend defaults to regular season for every season, preserves competition
in URLs, and applies the choice to players, teams, goalies, faceoffs, and player
summaries. Season-history rows remain explicitly labeled regular season + playoffs.
The rollout includes every season from 2022 through 2026.

All rates are calculated from pooled counts within the chosen sample, not averages
of game percentages. Appearance denominators include only games the player played
in that stage and the actual team represented. Above-expected metrics use the same
same-year regular-season league baseline for both stage exports. This prevents a small
playoff sample from redefining the comparison baseline. The combined historical
export keeps its existing pooled baseline, so its above-expected value need not be
the sum of the two stage values. Raw counts do reconcile exactly. No causal or
persistent “clutch ability” claim is made from a one-to-three-game playoff sample.

## Sources

- [Official 2026 schedule](https://premierlacrosseleague.com/schedule?view=list)
- [PLL player table](https://stats.premierlacrosseleague.com/player-table): Regular/Post/Champ Series controls.
- [Championship Series announcement](https://www.usalacrosse.com/magazine/pll-introduces-new-championship-series-will-feature-sixes-format): February 2023 start and Sixes format.


## 2023 extension

The field season has 40 regular-season and six playoff games. Both splits use the
2023 regular-season baseline. Existing combined 2023 exports remain unchanged.

The first Championship Series took place in February 2023: nine Sixes games,
IDs 172–180, including the final. The official schedule requires `includeCS=true`;
a plain year query omits these games. Source snapshots live under
`data/competitions/2023/champ_series/`; all 13 publication table schemas are exported
under `data/publication/2023/champ_series/`, with unavailable populations empty or null.

The 1,364 raw events contain 818 usable shots. Each player's shots, one-/two-point
goals and two-point attempts, and each goalie's saves and goals allowed reconcile to
its official game box score. All 18 team final scores reconcile. One feed entry is
labeled a goal but marked saved with no score increase; the existing normalization
correctly retains it as a save and does not add a goal. Raw data stays intact.

Shooting, goalkeeping, faceoff, turnover, and defensive-production metrics use only
this tournament and its baseline. Actual game/team appearances determine exposure.
Sixes forwards appear in offensive player details. Combined views and season-history
rows continue to mean regular season + playoffs, excluding Sixes.

Possession, pace, possession sensitivity, and time-of-possession metrics are withheld.
Nineteen regulation events have clocks above eight minutes, and the source has
15 backwards elapsed-time steps. Sixes also restarts with a goalie clear after goals;
the field model expects faceoffs. Score reconciliation alone cannot validate those
boundaries. No synthetic possessions, repaired clocks, or zero-filled efficiency
values are published. The team advanced view displays the supported assist/goal and
two-point metrics and explains the limitation.

Rebuild the cached tournament with `python -B scripts/pll_import_2023_championship.py`.
The `--fetch` flag is initial retrieval only; it refuses to replace reviewed sources.
The normal publication build, validation and determinism commands include all field and Sixes
samples. `pll_validate_championship.py` also runs the Sixes checks independently.

Format references: [ESPN's 2023 tournament announcement](https://espnpressroom.com/press-release/espn-platforms-to-exclusively-carry-2023-pll-championship-series-february-22-26/)
and [the host's PLL announcement](https://eventsdc.com/news/premier-lacrosse-league-powered-ticketmaster-announces-washington-dc-host-2023-championship)
document eight-minute quarters and goalie restarts after goals.


## Full 2022–2026 rollout

| Season | Regular season | Playoffs | Championship Series |
| --- | ---: | ---: | ---: |
| 2022 | 40 | 6 | Not held |
| 2023 | 40 | 6 | 9 |
| 2024 | 40 | 5 | 9 |
| 2025 | 40 | 5 | 8 |
| 2026 | 48 | 5 | 8 |

The 2025 and 2026 tournament schedules contain six round-robin games, one semifinal,
and a final. The one-seed gets a bye; eight games is the complete PLL schedule,
not missing data. WLL games are excluded by league and reviewed game-ID membership.
See the [official tournament format](https://premierlacrosseleague.com/championship-series).

The new Sixes samples contain 753 usable shots in 2024, 735 in 2025, and 818 in 2026.
All final scores and all player shooting/goalie outcome counts reconcile to official
game box scores. The audit found no impossible regulation clocks or backwards time
steps in the 2024 and 2025 snapshots; 2026 has one backwards step. Even with cleaner
clocks, the field possession reconstruction has not been validated for Sixes, so
possession and pace metrics remain unavailable for all Championship Series views.

Each field playoff split uses that same year's regular-season baseline. Each Sixes
sample uses only its own year's tournament baseline. No cross-year or cross-format
pooling is introduced. Existing combined field tables and the 2022–2023 splits stay
unchanged. All five years now default to regular season; competition choices persist
in links and on reload, including player details. Season history remains explicitly
labeled regular season + playoffs.

To rebuild a cached tournament, run:

```sh
python -B scripts/pll_import_championship.py --year 2024
```

Use 2025 or 2026 for those snapshots. `--fetch` is initial retrieval only and refuses
to overwrite an existing source snapshot. The original 2023 command remains a
compatibility entry point. Normal build, validation, and determinism commands cover
all supported years; `pll_competitions.py` records the reviewed game memberships.
