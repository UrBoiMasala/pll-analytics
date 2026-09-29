# Audit checkpoint

`canonical-v1.zip` contains only the historical canonical artifacts referenced
by `data/processed/history/CANONICAL_MANIFEST_V1.json`. They were exported from
the original checkpoint commit recorded in `refocus_source_checkpoint.json`,
and each file was verified against the existing manifest before packaging.
The historical and current manifests have not been rewritten.

The archive lets the canonical audit tests run in a fresh clone or downloaded
source folder without the original Git history. It is not another dataset to
combine with current analytical tables. Validation reads it directly; do not
extract it over current data.

The current frontend and publication workflow uses current data and requires no
old Git checkout. Re-running the historical refocus transformation itself
(`pll_refocus_foundation.py`) still requires the original checkpoint commit;
that provenance-sensitive script is preserved unchanged. The original input
ZIP retains the complete history for that purpose.

`legacy_phase1_2/README.md` explains the obsolete sample files omitted from this
clean distribution.
