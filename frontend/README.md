# PLL Stats frontend

A local statistics browser for the frozen PLL Analytics publication tables.
It includes player, team, goalie, and faceoff views, traditional/advanced metrics,
season and team filters, search, sorting, and player detail pages.

The black-and-yellow interface uses locally bundled Barlow Semi Condensed type,
a compact navigation bar, striped rows, a highlighted sort column, pinned player
names on horizontal scroll, and an expandable stat key. Player pages include
season comparison charts labeled with their regular-season-plus-playoff scope.
The Standard tab displays traditional box-score statistics.

## Run

From the repository root:

```sh
python3 -B frontend/scripts/build.py
python3 -m http.server 4173 --bind 127.0.0.1 --directory frontend/dist
```

Open <http://127.0.0.1:4173/>. There are no runtime npm dependencies, remote font requests,
or CDN requests. Python's standard library builds the app from included data.
This command serves locally; it does not deploy a public website.

## Source layout

| Path | Responsibility |
| --- | --- |
| `src/index.html`, `styles.css`, `favicon.svg` | Page structure and visual styling |
| `src/app.js` | Navigation, filtering, tables, and player pages |
| `src/data.js` | Loading, routes, sorting, and formatting |
| `src/columns.js` | Column definitions and explanatory tooltips |
| `scripts/build.py` | Static bundle and provenance generation |
| `tests/` | Data, source comparison, and browser tests |

Generated files live in ignored `dist/`; browser artifacts live in ignored
`test-results/`. Edit the source files rather than generated copies.

## Data rules

Advanced values come directly from publication CSVs; the interface does not
recalculate their formulas. Traditional player totals use actual-team stints and
traditional team totals use eligible official box scores. Provenance hashes record
every directly consumed source file.

Unfiltered player views select `SEASON`. A team filter selects the corresponding
`STINT`, not the player's full-season production. Detail pages show totals and
separate team splits. Never add the splits to the total again.

Missing values display as `—`; observed zero remains zero. Percentages use pooled
counts. Goalie traditional and advanced rates may differ because their populations
are official box-score outcomes and resolved event outcomes, respectively.
The 2026 source metadata now includes the September 20 championship. The 2022–2026 Competition selector offers regular season, playoffs, combined, and Championship Series. The 2022 tournament was not held. Each 2023–2026 Sixes view uses its own tournament baseline and clearly withholds unvalidated possession/pace metrics. Every season defaults to regular season; combined field totals remain available.

## Routes

- `#/players`, `#/teams`, `#/goalies`, `#/faceoffs`
- `#/players/002015?season=2026&view=traditional`
- Shared query fields: `season`, `view`, `team`, `position`, `q`, `sort`, `dir`

Hash routing supports deep links without a special server configuration. Tables
scroll horizontally on small screens.

## Tests

```sh
python3 -B frontend/scripts/build.py
node --test frontend/tests/data.test.mjs
python3 -B frontend/tests/test_sources.py
```

For optional browser tests, install the pinned development dependency from
`package.json` with `npm install` inside `frontend/`, then run
`npx playwright install chromium`. With the local server running:

```sh
node --test frontend/tests/browser.test.mjs
```

`CHROME_PATH` can select an installed Chrome executable; `PLAYWRIGHT_MODULE` can
select an existing Playwright module. These are local options, not repository paths.
