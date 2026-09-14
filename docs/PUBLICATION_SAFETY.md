# Publication authorization update — 2026-09-14

The project owner reports obtaining permission for this personal learning project and explicitly authorizes publishing the complete repository, including data and existing history. This is an owner-reported authorization, not an independently reviewed license or a grant of reuse rights to others. Source attribution remains required. The earlier blocked assessment below is retained as historical context and is superseded for this authorized publication.

# Public repository readiness

Public GitHub publication is blocked pending source-data redistribution permission. Local implementation and validation can proceed.

On 2026-09-11, the official [PLL Terms of Service](https://premierlacrosseleague.com/terms-of-service), effective June 24, 2024, were reviewed. They restrict systematic data retrieval and uses involving archived play-by-play and comprehensive statistics databases, and require source attribution. Availability through a public endpoint is not a redistribution license. The repository contains five seasons of raw responses and derived event/statistics databases, including in Git history. No grant of redistribution permission was established.

Affected material: `data/raw/`, canonical and historical statistics under `data/processed/`, publication exports under `data/publication/`, and historical data blobs. Do not publish this history until permission or another safe distribution plan is established. Removing files in a new commit does not remove them from history.

Recommended resolution: obtain explicit PLL permission covering the intended public research repository, historical data and derivative tables. Alternatively, agree on a separately prepared code/documentation release without source-data history and with ingestion instructions subject to permission. No history rewrite, source deletion or alternate repository creation was performed automatically.

The initial checkout had no Git remote. `gh` was not installed, so authenticated account/repository availability could not be verified. No repository was created, no branch was pushed, and no public URL or visibility is claimed.

After rights are resolved, install/authenticate GitHub CLI, inspect the intended account and existing repositories, then use the commands below only if the name is available and no intended remote exists:

```sh
gh auth login
gh auth status
git remote -v
gh repo view OWNER/pll-analytics
# Only after confirming absence and passing the rights/safety gate:
gh repo create OWNER/pll-analytics --public --source=. --remote=origin --description "Advanced Premier Lacrosse League analytics using five seasons of play-by-play, possession, and box-score data."
git push -u origin main
gh repo view OWNER/pll-analytics --json name,url,visibility,defaultBranchRef
git ls-remote origin refs/heads/main
```

Replace OWNER with the verified authenticated account. Do not execute creation on a generic network/authentication failure from `repo view`; establish that the repository is actually absent. Do not force-push or overwrite a remote.

## Audit scope

A pattern scan of all 1,855 pre-implementation history blobs found no matches for supported token/private-key patterns or quoted credential assignments. This is a bounded scan, not proof of absence of every possible secret. Tracked file names were inspected for environment files, caches and temporary artifacts; no such tracked files were found. The single personal absolute path in current documentation was converted to a repository-relative reference. Older historical text remains preserved; history was not rewritten for path cosmetics.

The initial checkout was approximately 196 MiB, including about 62 MiB raw data and 99 MiB processed data; Git objects were about 28 MiB. The largest tracked file was approximately 27.1 MiB (`data/processed/history/player_leaderboards_2022_2026.csv`). Final sizes and checks are recorded in the implementation report. No tracked analytical outputs were deleted or placed into LFS.
