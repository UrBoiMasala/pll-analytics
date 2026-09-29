# Advanced metrics

The publication layer contains **35 core metrics**, defined by
[publication.sql](../sql/publication.sql) and the
[metric dictionary](../data/publication/metric_dictionary.csv).
The [full catalog](FINAL_METRIC_CATALOG.md) lists formulas, units, and source rules.

| Area | Examples | Interpretation |
| --- | --- | --- |
| Team | Offensive and defensive efficiency, possessions per game | Points per 100 possessions and team workload |
| Shooting | Shooting percentage, points per shot, shooting value above expected | Observed conversion relative to a same-season shot-class baseline |
| Two-point play | Attempt rate, conversion, two-point shooting value | PLL-specific selection and production |
| Ball security | Turnovers per touch, turnovers below expected | Recorded turnover events relative to a touch proxy |
| Faceoffs | Win rate, draw share, wins above average | Draw outcomes and participation |
| Goalkeeping | Resolved save rate, saves above average | Outcomes among attributed, resolved shots |
| Defense | Caused turnovers, ground balls, penalties per game | Recorded production, not comprehensive defensive value |

## Avoid double counting

- Select either `SEASON` totals or `STINT` rows for actual teams, never both.
- Two-point shooting value is already a component of total shooting value.
- Do not sum quantities with different units: saves, faceoff wins, turnovers, and points.

A proportion of `0.25` displays as 25%. Efficiency is already expressed per 100
possessions. Empty CSV cells represent unavailable or undefined values, not zero.
Show denominators alongside rates. Positive exposure is not a reliability guarantee.

The older 29-metric catalog in the historical outputs was a proposal. It is not the
current publication dictionary. See [limitations](METRIC_LIMITATIONS.md) for source
coverage and assumptions.
