# Troubleshooting

## The frontend is blank or data requests return 404

Run `python3 -B frontend/scripts/build.py` from the repository root before starting
the server. Serve `frontend/dist/` with the command in the setup guide; opening
`src/index.html` directly is not supported. Check that the build finished successfully.

## Port 4173 is already in use

Choose another local port:

```sh
python3 -m http.server 4174 --bind 127.0.0.1 --directory frontend/dist
```

Then open <http://127.0.0.1:4174/>. For browser tests, set
`FRONTEND_URL=http://127.0.0.1:4174`.

## Analytics imports fail

Activate the virtual environment and install `requirements.txt` with that environment's
Python. Python 3.9 is the tested pinned environment. Do not assume the system's latest
Python supports the same pinned wheels.

## Historical validation cannot find a document

Use the complete checkout, including `docs/history/`, `docs/research/`, and `archive/`.
The phase reports are archived, not deleted. Avoid copying only scripts and CSVs.

## A checkpoint hash fails

Do not regenerate the manifest to dismiss the failure. Inspect `git diff`, identify
which file changed, and compare with the original snapshot. A hash mismatch is evidence
to investigate, not a formatting issue to normalize away.

## A historical rebuild needs an old commit

The normal publication and frontend workflows do not require the original Git history.
The historical refocus transformation does. See the [audit archive](../archive/README.md)
for the distinction between verifying a checkpoint and rerunning that old transformation.

## Totals or percentages look different

Check season, team filters, and `SEASON` versus `STINT` first. Traditional goalie values
use official counts; advanced goalie values use resolved event outcomes. Read
[metric definitions](FINAL_METRIC_CATALOG.md) before assuming a mismatch is a bug.

If the problem remains, report the command, environment, game or player key, and expected
versus actual result. Do not include credentials or private local paths.
