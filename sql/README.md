# SQL

## Current publication layer

- [publication.sql](publication.sql): the definitions behind current team and player tables.
- [publication_examples.sql](publication_examples.sql): 16 example analyses.

Build a queryable database using:

```sh
python -B scripts/pll_build_publication.py --database /tmp/pll-publication.duckdb --output /tmp/pll-publication-check
```

Run this from the repository root. The [SQL guide](../docs/SQL_GUIDE.md) explains
keys, aggregation levels, and example queries.

## Earlier layers

The remaining SQL files support canonical team calculations and historical research.
Their presence does not mean that every earlier model is published in the current
statistics browser. Use the publication dictionary to identify supported metrics.

Keep calculations in SQL, make denominators explicit, and represent undefined
quantities with `NULL`. A metric change should include a corresponding definition,
source contract, and regression case. Never join player data by display name or
combine actual-team stints with season totals.
