# Contributing

Start with the [setup guide](docs/GETTING_STARTED.md) and the
[current metric catalog](docs/FINAL_METRIC_CATALOG.md).

## Before changing a statistic

Describe the question, source population, numerator, denominator, unit, and NULL
behavior. Distinguish a code defect from a limitation of the original feed. Include
a small concrete example with stable game or player IDs where possible.

Keep observed counts, derived rates, and model-based claims distinct. A comparison
with official totals is evidence to investigate; it is not permission to fabricate
missing events or force agreement.

## Make a focused change

1. Create a branch for one coherent improvement.
2. Edit source files rather than generated frontend output.
3. Update the relevant definition and add a regression case for behavioral changes.
4. Run the checks below and review `git diff` for unintended generated-file changes.
5. Open a pull request explaining the problem, change, validation, and limitations.

```sh
python -B -m pytest tests/ -q -p no:cacheprovider
python -B scripts/pll_validate_publication.py
python -B scripts/check_documentation.py
python -B frontend/scripts/build.py
node --test frontend/tests/data.test.mjs
python -B frontend/tests/test_sources.py
```

## Data and provenance

Do not edit frozen raw payloads or rewrite manifests to make a test pass. A new
source snapshot needs an explicit provenance and coverage update. Preserve string
IDs and season keys. Avoid reformatting CSV/JSON archives during unrelated work.

Prior phase reports and research models remain available for audit. They are not
the current publication specification. Source-data attribution and the existing
[publication record](docs/PUBLICATION_SAFETY.md) must remain visible.

## Commits and reports

Use descriptive commits for actual changes. Do not include credentials, local
machine paths, generated bundles, screenshots of private accounts, or unrelated
formatting. For a data discrepancy, provide expected and observed values and the
exact game/season rather than a screenshot alone.
