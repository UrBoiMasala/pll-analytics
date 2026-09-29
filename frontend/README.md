# PLL Stats frontend

Local statistics interface for the `pll-analytics` repository, with player and team tables, season filters, and player detail pages. No analytics rebuild or external data fetching is required.

## Run locally

From the repository root:

```sh
python3 -B frontend/scripts/build.py
python3 -m http.server 4173 --bind 127.0.0.1 --directory frontend/dist
```

Open **http://127.0.0.1:4173/**. Default: Players → Traditional → 2026. The preview binds only to localhost. Repository publication is authorized as recorded in `docs/PUBLICATION_SAFETY.md`; the website itself is not deployed.

The app has no runtime npm dependencies, CDN calls or external fonts. Python's standard library builds its static assets and JSON bundle. Native browser modules keep the frontend small. `package.json` provides equivalent npm build/start commands and an optional Playwright development dependency; Node is needed only for JavaScript tests.

## Routes

Hash routes work with a plain static server and support deep links, refresh and browser back/forward:

- `#/players`, `#/teams`, `#/goalies`, `#/faceoffs`
- `#/players/002015?season=2026&view=traditional` (player detail)
- A player detail also works beneath its originating goalie/faceoff category.
- Shared query state: `season`, `view`, `team`, `position`, `q`, `sort`, `dir`.

## Files and architecture

- `src/index.html`, `styles.css`, `favicon.svg`: semantic shell and restrained reference-based visual system.
- `src/app.js`: navigation, filters, table and detail rendering. Source text is escaped before insertion into HTML.
- `src/data.js`: JSDoc data types, loading, routing, selection, sorting, transfer handling and formatting.
- `src/columns.js`: shared table definitions, role-relevant detail metrics and explanatory tooltips.
- `scripts/build.py`: presentation-only exporter; writes exclusively to ignored `dist/`.
- `tests/`: Node unit tests, Chrome/Playwright interaction tests, and independent Python source comparisons.

## Source contracts

Advanced values are copied from `data/publication/{season}/player_season_summary.csv` and `team_advanced_stats.csv`; no advanced metric is recalculated in the frontend. The metric dictionary supplies tooltip descriptions and limitations. Coverage metadata comes from `publication_coverage.csv`.

Traditional player counts use `data/processed/history/player_team_stints_2022_2026.csv`, the validated actual-team inventory. Season totals sum those stints once. Display percentages divide pooled source numerators by pooled denominators, following the existing definitions, never averaging percentages. Official player PTS includes assists and PLL two-point scoring. Official assists are never inferred from a pass/event-assist ID.

Traditional team totals use existing `team_game_stats.csv` records joined to exactly the existing completed, included, non-all-star game flags. Team PTS uses official `scores`, which excludes assists. The actual team names come from `teams.csv`.

This presentation step does not change eligibility rules. It does not call canonical builders or modify any backend output. `dist/data/provenance.json` records hashes of every directly consumed data source.

### SEASON and STINT

Unfiltered player tables use `SEASON` rows only. A team filter selects the actual `STINT` row and shows a small explanatory note. Production from another team is not assigned to the filtered team. Player detail shows a season total; season history contains only season totals, with the selected Traditional or role-relevant Advanced columns. Traditional history includes GB, CT and TO. A transferred player's selected season has a separate, explicitly labeled team-split table. Those splits are already included in the total and must not be added again.

### Formatting and coverage

NULL, undefined and non-finite values render as `—`; observed zero remains zero. Percentages have one decimal, point residuals two signed decimals, seconds one decimal, and small per-opportunity ratios three decimals. All numeric columns use tabular numerals.

Player season selectors and history show plain season years. Team lists retain their partial-season indicator; the frozen cutoff remains in the footer and source metadata. Its latest eligible game starts August 30, 2026 at 00:30 UTC. Completed regular-season and playoff games are included. Traditional goalie save percentages use official counts; advanced goalie percentages use the publication's resolved event outcomes and show coverage. These populations can differ legitimately.

Offensive pace and TOP describe only measurable possession spans. Source limitations remain intact. Neither goalie outcomes nor descriptive defensive production is presented as isolated player skill. There is no composite score.

## Tests

```sh
python3 -B frontend/scripts/build.py
node --test frontend/tests/data.test.mjs
python3 -B frontend/tests/test_sources.py
# With the localhost server running and Playwright installed in frontend:
node --test frontend/tests/browser.test.mjs
# Existing backend suite, unchanged:
python3 -B -m pytest tests/ -q -p no:cacheprovider
```

For a system Chrome installation set `CHROME_PATH` to its executable. `PLAYWRIGHT_MODULE` can point to an already-installed Playwright ES module; otherwise tests import the local development dependency. For Playwright-managed Chromium, install it with `npx playwright install chromium` from `frontend/`. No machine-specific executable paths are saved in this repository.

Browser screenshots are generated under ignored `test-results/`. They cover desktop, narrow mobile and advanced player detail. Unit tests cover defaults, route state, filtering, sorting, transfer behavior, NULL formatting and role relevance. Browser tests exercise all eight table views, all seasons, partial labeling, detail navigation, transfer splits, real displayed statistics and responsive scrolling. Python checks compare every exported advanced value and every traditional player row against independent source files.

## Visual decisions

The structure follows the reference rather than a dashboard template. Secondary grays are slightly brighter for readability. Filters and navigation are compact, headers are sticky, and numeric sort indicators alone receive yellow emphasis. Actual source values replace the screenshot's illustrative rows. Small screens retain tables with horizontal scrolling; rows never become cards. Player details extend the same type/divider system without promotional photography or large hero sections.
