# Validation

Checks establish consistency with the recorded source and the declared formulas.
They do not establish that the event feed captured every play or that a statistic
isolates player skill.

## Check the published tables

```sh
python -B scripts/pll_validate_publication.py
```

This is read-only by default. It checks scoring and possession conservation, team
and player attribution, transfer totals, goalie outcomes, duration eligibility,
finite outputs, and agreement between SQL results and stored CSVs.

## Run regressions

```sh
python -B -m pytest tests/ -q -p no:cacheprovider
```

The suite includes synthetic edge cases and checks on the frozen data. Historical
validators may regenerate their own diagnostic outputs; inspect `git diff` afterward.
Do not loosen a test or rewrite a checkpoint merely to make a mismatch disappear.

## Check frontend data

```sh
python -B frontend/scripts/build.py
node --test frontend/tests/data.test.mjs
python -B frontend/tests/test_sources.py
```

The Python source checks compare every exported advanced value and traditional
player row against independent input files. Browser interaction tests are described
in the [frontend guide](../frontend/README.md).

## Check reproducibility

```sh
python -B scripts/pll_check_publication_determinism.py
```

This rebuilds CSVs into temporary directories and compares their bytes. It does not
compare binary DuckDB files or replace the included publication checkpoint.

## Historical evidence

Raw files and canonical tables have separate hash manifests. A compact
[checkpoint archive](../archive/README.md) preserves the historical v1 payloads;
current v2 files are checked on disk. Both versions remain identifiable.

Known gaps remain explicit, including the named 2022 seven-point source discrepancy.
A passing check does not make an ambiguous possession certain. Read the
[limitations](METRIC_LIMITATIONS.md) alongside any validation result.
