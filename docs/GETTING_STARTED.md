# Getting started

## Requirements

- Python **3.9** for the tested, pinned analytics environment.
- Git to clone the repository.
- Node.js **22** for frontend unit tests; it is not needed to view the app.

## Clone and install

```sh
git clone https://github.com/UrBoiMasala/pll-analytics.git
cd pll-analytics
python3.9 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell.
Use the Python 3.9 launcher available on your system to create the environment.
The data needed for the local demo is included; no API token or new ingestion is required.

## Open the statistics browser

```sh
python -B frontend/scripts/build.py
python -m http.server 4173 --bind 127.0.0.1 --directory frontend/dist
```

Open <http://127.0.0.1:4173/>. Stop the server with **Ctrl+C**.
The interface includes player, team, goalie, and faceoff tables, season selection,
search, team filters, and individual player pages.

## Validate the included results

```sh
python -B scripts/pll_validate_publication.py
python -B -m pytest tests/ -q -p no:cacheprovider
```

## Build a separate set of publication tables

```sh
python -B scripts/pll_build_publication.py --output /tmp/pll-publication-check
```

The output option leaves the included publication checkpoint intact. For a SQL
workspace, add `--database /tmp/pll-publication.duckdb`. See the
[SQL guide](SQL_GUIDE.md) for examples.

The normal workflow reads frozen inputs. Running ingestion or historical rebuild
scripts is a different operation; it is not necessary to try this project.
