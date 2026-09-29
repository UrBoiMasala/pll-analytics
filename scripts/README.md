# Pipeline commands

Run commands from the repository root, after installing `requirements.txt`.

## Current workflow

| Script | Purpose | Writes |
| --- | --- | --- |
| `pll_build_publication.py` | Execute publication SQL and export tables | `data/publication/` by default; use `--output` for another location |
| `pll_validate_publication.py` | Independently check stored outputs | Nothing unless `--write-report` is supplied |
| `pll_check_publication_determinism.py` | Compare repeated builds with the frozen exports | Temporary directories |
| `pll_query_publication.py` | Run example queries against the publication views | Console output |
| `../frontend/scripts/build.py` | Build the local statistics browser | Ignored `frontend/dist/` |

## Foundation and research tools

Ingestion, cleaning, possession reconstruction, chronology repair, and historical
player-value studies remain here for reproducibility. Scripts named `pll_phase*`
refer to historical development work. They are not prerequisites for the current UI
or publication-table build.

`pll_refocus_foundation.py` compares against an original Git checkpoint and is not
a supported first-run command for a downloaded source ZIP. The audit validator uses
the [portable checkpoint](../archive/README.md) for verification instead.

Refreshing source data or rebuilding canonical tables changes the statistical
snapshot. Read the relevant [methodology](../docs/README.md) before doing so; do not
run every script in this directory in alphabetical order.
