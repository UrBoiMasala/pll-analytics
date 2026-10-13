# Data source and permission status

Raw statistics and play-by-play data were extracted from the
[Premier Lacrosse League (PLL) statistics website](https://stats.premierlacrosseleague.com/),
provided by the [Premier Lacrosse League](https://premierlacrosseleague.com/).
The project uses these source records to produce derived datasets and independent analysis.

This is an independent, noncommercial learning project, not affiliated with or endorsed by the PLL.
Permission is being sought and remains pending. The earlier statement that permission had been obtained was incorrect.

## Audit scope

A pattern scan of all 1,855 pre-implementation history blobs found no matches for supported token/private-key patterns or quoted credential assignments. This is a bounded scan, not proof of absence of every possible secret. Tracked file names were inspected for environment files, caches and temporary artifacts; no such tracked files were found. The single personal absolute path in current documentation was converted to a repository-relative reference. Older historical text remains preserved; history was not rewritten for path cosmetics.

The initial checkout was approximately 196 MiB, including about 62 MiB raw data and 99 MiB processed data; Git objects were about 28 MiB. The largest tracked file was approximately 27.1 MiB (`data/processed/history/player_leaderboards_2022_2026.csv`). Final sizes and checks are recorded in the implementation report. No tracked analytical outputs were deleted or placed into LFS.
