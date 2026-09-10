"""
Phase 3: build canonical season-level tables from the raw JSON already
ingested under data/raw/2026/<slug>/ by pll_ingest_season.py.

Produces, under data/processed/2026/:
    games.csv
    teams.csv
    players.csv
    events.csv
    player_game_stats.csv
    team_game_stats.csv

Also prints/report player-ID resolution issues (event-referenced IDs that
don't appear in any game's players_stats roster).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pll_pbp_extractor import normalize_play_by_play  # noqa: E402
from pll_pbp_clean import clean  # noqa: E402
from pll_chronology_repair import repair_game_chronology  # noqa: E402
from pll_duplicate_faceoff import flag_duplicate_faceoffs  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

# Phase 9: season is module state defaulting to 2026, so every existing caller
# and test keeps the exact behaviour it had while the same builder can process
# 2022-2025. No 2026 code path changes.
SEASON = 2026
RAW_DIR = REPO_ROOT / "data" / "raw" / "2026"
OUT_DIR = REPO_ROOT / "data" / "processed" / "2026"


def set_season(year: int) -> None:
    global SEASON, RAW_DIR, OUT_DIR
    SEASON = int(year)
    RAW_DIR = REPO_ROOT / "data" / "raw" / str(SEASON)
    OUT_DIR = REPO_ROOT / "data" / "processed" / str(SEASON)

PLAYER_ID_FIELDS_IN_EVENTS = [
    "shooterId", "goalieId", "shotAssistId", "faceoffWinnerId", "faceoffLoserId",
    "gbPlayerId", "commitedPenaltyId", "offenseGoalieId", "assistOpportunityPlayerId",
    "closestDefenderId", "commitedTurnoverId", "causedTurnoverId",
]


def load_raw_endpoint(slug: str, name: str):
    """One raw endpoint, or None if it was never written.

    The ingester declines to write an endpoint whose feed came back empty, so a
    completed non-competitive event (the all-star SKILLS competitions in
    2022-2025) legitimately has play-by-play and game meta but no box score.
    Callers that need a specific endpoint ask for that endpoint.
    """
    p = RAW_DIR / slug / f"{name}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def load_raw(slug: str) -> dict:
    return {name: load_raw_endpoint(slug, name)
            for name in ("play_by_play", "game_meta", "players_stats", "teams_stats")}


def load_schedule() -> list[dict]:
    return json.loads(
        (RAW_DIR / "_schedule" / f"games_{SEASON}.json").read_text())["data"]["items"]


def is_completed(g: dict) -> bool:
    """A game is completed if the league says so (eventStatus 3) OR it carries
    real final scores under eventStatus 2.

    2026 uses eventStatus 3 exclusively, so this is a no-op there. The 2023 feed
    marks four PLAYED games -- two regular season, a quarterfinal, and the
    CHAMPIONSHIP -- with eventStatus 2 while still reporting final scores.
    Gating on status 3 alone would silently drop them from the season.
    """
    if g.get("eventStatus") == 3:
        return True
    return (g.get("eventStatus") == 2
            and g.get("homeScore") is not None
            and g.get("visitorScore") is not None)


def completed_slugs() -> list[str]:
    return [g["slugname"] for g in load_schedule() if is_completed(g)]


# PLL's own seasonSegment field is the authoritative source for game
# classification (values observed across the full 2026 schedule: "regular",
# "post", "allstar" — no others). Mapped directly rather than pattern-
# matching slugnames, which would be more fragile.
# "preseason" appears only in 2022 (4 scrimmages on 2022-05-31). It is mapped
# explicitly rather than falling through to "other" by accident, so its
# exclusion from league analytics is a decision on the record.
SEASON_SEGMENT_TO_GAME_TYPE = {"regular": "regular_season", "post": "playoffs",
                               "allstar": "all_star", "preseason": "preseason"}


def classify_game_type(season_segment: str) -> str:
    return SEASON_SEGMENT_TO_GAME_TYPE.get(season_segment, "other")


def build_games_table() -> pd.DataFrame:
    """
    Includes EVERY game in the schedule response (54, as of this run) —
    completed and not-yet-played alike — so games.csv is always a complete,
    current picture of the season. Classification fields (game_type,
    is_playoff, is_all_star, include_in_league_analytics, is_completed) are
    derived for every row regardless of completion status. Per-game-meta
    enrichment (period scores, venue, final score) is only available for
    completed games (raw/<slug>/game_meta.json only exists for those); for
    not-yet-played games those fields are left null rather than guessed.
    """
    rows = []
    for sched in load_schedule():
        slug = sched["slugname"]
        is_completed_game = is_completed(sched)
        season_segment = sched.get("seasonSegment")
        game_type = classify_game_type(season_segment)

        start_time = sched.get("startTime")
        start_iso = None
        if start_time:
            try:
                start_iso = datetime.fromtimestamp(int(start_time), tz=timezone.utc).isoformat()
            except (ValueError, OSError):
                start_iso = None

        row = {
            "game_id": sched.get("id"),
            "game_slug": slug,
            "event_id": sched.get("eventId"),
            "year": sched.get("year"),
            "week": sched.get("week"),
            "season_segment": season_segment,
            "game_type": game_type,
            "is_playoff": game_type == "playoffs",
            "is_all_star": game_type == "all_star",
            "include_in_league_analytics": game_type in ("regular_season", "playoffs"),
            "is_completed": is_completed_game,
            "event_status": sched.get("eventStatus"),
            "start_time_unix": start_time,
            "start_date_utc": start_iso,
            "venue": sched.get("venue"),
            "location": sched.get("location"),
            "home_team_id": (sched.get("homeTeam") or {}).get("officialId"),
            "away_team_id": (sched.get("awayTeam") or {}).get("officialId"),
            "home_score": None,
            "away_score": None,
            "home_period_scores": None,
            "away_period_scores": None,
        }

        raw_game_meta = load_raw_endpoint(slug, "game_meta") if is_completed_game else None
        if raw_game_meta is not None:
            raw_meta = raw_game_meta["data"]
            row["home_score"] = raw_meta.get("homeScore")
            row["away_score"] = raw_meta.get("visitorScore")
            row["home_period_scores"] = json.dumps(raw_meta.get("homePeriodScores"))
            row["away_period_scores"] = json.dumps(raw_meta.get("visitorPeriodScores"))
            # game_meta's venue/location/team ids are authoritative when available
            row["venue"] = raw_meta.get("venue") or row["venue"]
            row["location"] = raw_meta.get("location") or row["location"]
            row["home_team_id"] = raw_meta.get("homeTeam", {}).get("officialId") or row["home_team_id"]
            row["away_team_id"] = raw_meta.get("awayTeam", {}).get("officialId") or row["away_team_id"]

        rows.append(row)
    return pd.DataFrame(rows)


def build_teams_table(slugs: list[str], games_df: pd.DataFrame) -> pd.DataFrame:
    all_star_team_ids = set(
        games_df.loc[games_df["game_type"] == "all_star", "home_team_id"]
    ) | set(
        games_df.loc[games_df["game_type"] == "all_star", "away_team_id"]
    )

    seen = {}
    for slug in slugs:
        meta = load_raw(slug)["game_meta"]["data"]
        for side in ("homeTeam", "awayTeam"):
            t = meta.get(side)
            if not t:
                continue
            tid = t["officialId"]
            seen[tid] = {
                "team_id": tid,
                "full_name": t.get("fullName"),
                "location": t.get("location"),
                "location_code": t.get("locationCode"),
                "conference": t.get("conference"),
                "team_color": t.get("teamColor"),
                "background_color": t.get("backgroundColor"),
                # A team_id that only ever appears in an all_star-classified
                # game (per games.csv game_type, itself derived from PLL's
                # own seasonSegment field) is an all-star squad, not a real
                # franchise — exclude via this flag when computing team-level
                # league baselines/ratings.
                "is_all_star_team": tid in all_star_team_ids,
            }
    return pd.DataFrame(sorted(seen.values(), key=lambda r: r["team_id"]))


def build_players_table(slugs: list[str]) -> tuple[pd.DataFrame, dict]:
    players = {}  # officialId -> latest record
    for slug in slugs:
        ps = load_raw(slug)["players_stats"]["data"]["items"]
        for p in ps:
            pid = p["officialId"]
            players[pid] = {
                "player_id": pid,
                "name": f"{p['firstName']} {p['lastName']}",
                "first_name": p["firstName"],
                "last_name": p["lastName"],
                "team_id": p.get("teamId"),
                "position": p.get("position"),
                "position_name": p.get("positionName"),
                "jersey_num": p.get("jerseyNum"),
                "slug": p.get("slug"),
                "profile_url": p.get("profileUrl"),
            }
    df = pd.DataFrame(sorted(players.values(), key=lambda r: r["player_id"]))
    return df, players


def build_events_table(slugs: list[str], games_df: pd.DataFrame) -> pd.DataFrame:
    game_id_by_slug = dict(zip(games_df["game_slug"], games_df["game_id"]))
    include_by_slug = dict(zip(games_df["game_slug"], games_df["include_in_league_analytics"]))
    game_type_by_slug = dict(zip(games_df["game_slug"], games_df["game_type"]))
    all_rows = []
    empty_pbp_games = []
    for slug in slugs:
        raw = load_raw(slug)
        items = raw["play_by_play"]["data"]["items"]
        if not items:
            empty_pbp_games.append(slug)
            continue
        df = normalize_play_by_play(slug, raw)
        df = clean(df)
        # normalize_play_by_play's own "game_id" column is actually the slug;
        # replace it with the numeric schedule game_id + an explicit slug column.
        df = df.drop(columns=["game_id"])
        df.insert(0, "game_id", game_id_by_slug.get(slug))
        df.insert(1, "game_slug", slug)
        df["game_type"] = game_type_by_slug.get(slug)
        df["include_in_league_analytics"] = include_by_slug.get(slug)
        # Phase 11: flag confirmed duplicate faceoffs BEFORE the chronology
        # reorder repair runs, since the duplicate rule keys on the raw
        # array position immediately after a goal -- a position the reorder
        # repair may itself change for a DIFFERENT (non-duplicate) faceoff.
        # Scoped to the same games Phase 10's own classification was
        # validated against (include_in_league_analytics) -- an all-star
        # game's event order is never consumed by any possession/stat layer,
        # so it is left exactly as the feed sent it rather than repaired on
        # spec.
        if df["include_in_league_analytics"].iloc[0]:
            df = flag_duplicate_faceoffs(df)
            df = repair_game_chronology(df)
        else:
            df["duplicate_faceoff_pair_id"] = pd.array([None] * len(df), dtype="object")
            df["event_number_raw"] = df["event_number"]
            df["seconds_passed_raw"] = df["seconds_passed"]
            df["chronology_evidence_class"] = pd.array([None] * len(df), dtype="object")
            df["chronology_repair_applied"] = False
            df["chronology_repair_rule_version"] = None
        # Preserve pre_shot_pass_player_id as an explicitly-named alias of
        # secondary_player_id (which is already shotAssistId for shot/goal
        # rows) so downstream consumers don't have to know the mapping.
        df["pre_shot_pass_player_id"] = df["secondary_player_id"].where(
            df["event_type"].isin(["shot", "goal"])
        )
        # A row is "safe to use in normal analysis" only if: the game itself
        # counts toward league analytics (not all-star/other), the event is
        # not a confirmed exact duplicate, and it isn't a confirmed-invalid
        # goal/penalty THAT ALSO CARRIES NO OTHER USABLE INFORMATION.
        #
        # An invalid penalty (null penaltyLength) has no salvageable content
        # for any other metric, so it is dropped from this general
        # eligibility flag entirely, as before.
        #
        # An invalid goal is different: the one confirmed case (2026-ev-1,
        # marker shot-3004600) is a real saved shot that PLL's feed
        # mislabeled eventType=='goal' instead of 'shot' (shot_saved=True,
        # shotOnGoal=True, zero score change, empty description — see
        # pll_pbp_clean._validate_goals / _classify_shots). Its
        # `shot_outcome` is still correctly derived ("saved"). Blanket-
        # excluding every invalid goal from is_analysis_eligible_event would
        # make this row invisible to any possession/shot/save metric built
        # on top of that flag — silently erasing a legitimate shot/save,
        # not just an invalid goal. So only an invalid goal with NO
        # resolvable shot_outcome (i.e. not even salvageable as a shot) is
        # excluded here; is_valid_goal==False remains the correct, separate
        # signal for every goal-specific/scoring aggregation (goal counts,
        # points, goals_with_pre_shot_pass) to filter on directly, so this
        # event still never counts as a goal anywhere. See DATASET_2026.md.
        # Deliberately does NOT exclude anything merely ambiguous (e.g. an
        # unpopulated shotAssistId, or the small unresolved turnover/
        # groundball count residuals) — see VALIDATION_METHODOLOGY.md.
        invalid_goal_with_no_shot_data = (
            (df["event_type"] == "goal") & (df["is_valid_goal"] == False) & df["shot_outcome"].isna()  # noqa: E712
        )
        invalid_penalty = df["is_valid_penalty"] == False  # noqa: E712
        known_invalid = invalid_goal_with_no_shot_data | invalid_penalty
        df["is_analysis_eligible_event"] = (
            df["include_in_league_analytics"].fillna(False)
            & ~df["is_duplicate_event"].fillna(False)
            & ~known_invalid.fillna(False)
        )
        all_rows.append(df)

    events = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    return events, empty_pbp_games


def build_player_game_stats(slugs: list[str], games_df: pd.DataFrame) -> pd.DataFrame:
    game_id_by_slug = dict(zip(games_df["game_slug"], games_df["game_id"]))
    rows = []
    for slug in slugs:
        items = load_raw(slug)["players_stats"]["data"]["items"]
        for p in items:
            row = dict(p)
            row["game_id"] = game_id_by_slug.get(slug)
            row["game_slug"] = slug
            rows.append(row)
    return pd.DataFrame(rows)


def build_team_game_stats(slugs: list[str], games_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    The raw `teams_stats` endpoint has been observed to return a phantom
    extra team row that did not play in that game (2026-ev-46, 2026-ev-47 —
    see FULL_SEASON_ANOMALIES.md §4). The canonical `team_game_stats.csv`
    must contain only actual game participants: exactly the two team_ids
    listed as home/away in that game's own `game_meta` (the authoritative
    source for who played). Every rejected raw row is preserved, not
    dropped silently, in the returned exceptions frame with a reason —
    this is a filter with an audit trail, not a deletion.
    """
    game_id_by_slug = dict(zip(games_df["game_slug"], games_df["game_id"]))
    home_by_slug = dict(zip(games_df["game_slug"], games_df["home_team_id"]))
    away_by_slug = dict(zip(games_df["game_slug"], games_df["away_team_id"]))

    rows = []
    exceptions = []
    for slug in slugs:
        items = load_raw(slug)["teams_stats"]["data"]["items"]
        expected = {home_by_slug.get(slug), away_by_slug.get(slug)}
        seen_accepted = set()
        for t in items:
            tid = t.get("officialId")
            row = dict(t)
            row["game_id"] = game_id_by_slug.get(slug)
            row["game_slug"] = slug
            if tid not in expected:
                exceptions.append({
                    **row,
                    "rejection_reason": f"not a participant in {slug} per game_meta (expected {sorted(e for e in expected if e)})",
                })
                continue
            if tid in seen_accepted:
                exceptions.append({
                    **row,
                    "rejection_reason": f"duplicate team_game row for {slug}/{tid} (participant already has an accepted row)",
                })
                continue
            seen_accepted.add(tid)
            rows.append(row)
        missing = expected - seen_accepted
        for tid in missing:
            if tid is None:
                continue
            exceptions.append({
                "officialId": tid, "game_id": game_id_by_slug.get(slug), "game_slug": slug,
                "rejection_reason": f"expected participant {tid} has NO teams_stats row at all in {slug}",
            })

    return pd.DataFrame(rows), pd.DataFrame(exceptions)


def validate_team_game_stats(tgs_df: pd.DataFrame, games_df: pd.DataFrame) -> list[str]:
    """Hard structural checks on the canonical team_game_stats table:
    exactly two distinct participant teams per completed game, and a
    unique (game_id, officialId) key. Returns a list of problem strings
    (empty if clean)."""
    problems = []
    dup_keys = tgs_df[tgs_df.duplicated(subset=["game_id", "officialId"], keep=False)]
    if len(dup_keys):
        problems.append(f"duplicate (game_id, officialId) keys in team_game_stats: "
                         f"{sorted(set(zip(dup_keys['game_slug'], dup_keys['officialId'])))}")
    per_game_team_counts = tgs_df.groupby("game_slug")["officialId"].nunique()
    bad_games = per_game_team_counts[per_game_team_counts != 2]
    if len(bad_games):
        problems.append(f"games without exactly 2 distinct participant teams in team_game_stats: "
                         f"{bad_games.to_dict()}")
    return problems


def check_player_id_resolution(events: pd.DataFrame, player_lookup: dict) -> pd.DataFrame:
    unresolved = []
    id_cols = ["player_id", "secondary_player_id", "goalie_id", "gb_player_id"]
    for col in id_cols:
        if col not in events.columns:
            continue
        vals = events[col].dropna().unique()
        for v in vals:
            if v not in player_lookup:
                unresolved.append({"field": col, "player_id": v})
    return pd.DataFrame(unresolved).drop_duplicates() if unresolved else pd.DataFrame(columns=["field", "player_id"])


def check_team_id_resolution(events: pd.DataFrame, games_df: pd.DataFrame, teams_df: pd.DataFrame) -> pd.DataFrame:
    """Every team_id referenced in events.csv or games.csv must resolve to teams.csv."""
    known = set(teams_df["team_id"])
    unresolved = []
    ev_teams = events["team_id"].dropna()
    ev_teams = ev_teams[ev_teams != ""]
    for v in ev_teams.unique():
        if v not in known:
            unresolved.append({"source": "events.team_id", "team_id": v})
    for col in ("home_team_id", "away_team_id"):
        for v in games_df[col].dropna().unique():
            if v not in known:
                unresolved.append({"source": f"games.{col}", "team_id": v})
    return pd.DataFrame(unresolved).drop_duplicates() if unresolved else pd.DataFrame(columns=["source", "team_id"])


RAW_ENDPOINTS = ("play_by_play", "game_meta", "players_stats", "teams_stats")


def missing_raw_endpoints(slug: str) -> list:
    return [n for n in RAW_ENDPOINTS if not (RAW_DIR / slug / f"{n}.json").exists()]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_games_df = build_games_table()
    completed = all_games_df.loc[all_games_df["is_completed"]]

    # Some completed non-competitive events have no box score at all. The
    # all-star SKILLS competitions in 2022-2025 are marked completed and carry
    # play-by-play, but the players/teams stats endpoints return an empty feed,
    # so the ingester correctly declines to write those files. Such a game is
    # skipped and recorded rather than crashing the build.
    #
    # A COMPETITIVE game may never be skipped this way. If one ever lacks a raw
    # endpoint the build raises, because silently dropping a league game is the
    # exact failure this phase exists to prevent.
    skipped = []
    usable = []
    for slug in completed["game_slug"].tolist():
        miss = missing_raw_endpoints(slug)
        if not miss:
            usable.append(slug)
            continue
        row = completed.loc[completed["game_slug"] == slug].iloc[0]
        if row["include_in_league_analytics"]:
            raise RuntimeError(
                f"{slug} is a competitive game ({row['game_type']}) but is missing "
                f"raw endpoints {miss}. Refusing to build a season with a silently "
                f"missing league game.")
        skipped.append({"game_slug": slug, "game_type": row["game_type"],
                        "season_segment": row["season_segment"],
                        "missing_endpoints": ",".join(miss),
                        "reason": "completed non-competitive game with no box-score feed"})
    slugs = usable
    skipped_df = pd.DataFrame(skipped, columns=["game_slug", "game_type",
                                                "season_segment",
                                                "missing_endpoints", "reason"])
    skipped_df.to_csv(OUT_DIR / "skipped_games.csv", index=False)
    print(f"Schedule has {len(all_games_df)} games total; building tables for {len(slugs)} completed games "
          f"({len(skipped)} completed non-competitive game(s) skipped for missing box-score feeds) ...")

    dup_game_ids = all_games_df["game_id"][all_games_df["game_id"].duplicated()].tolist()
    if dup_game_ids:
        print(f"  WARNING: duplicate game_id values: {dup_game_ids}")
    all_games_df.to_csv(OUT_DIR / "games.csv", index=False)
    print(f"  saved games.csv ({len(all_games_df)} rows, {len(slugs)} completed)")
    games_df = all_games_df[all_games_df["game_slug"].isin(slugs)].reset_index(drop=True)

    teams_df = build_teams_table(slugs, games_df)
    teams_df.to_csv(OUT_DIR / "teams.csv", index=False)
    print(f"  saved teams.csv ({len(teams_df)} rows)")

    players_df, player_lookup_by_id = build_players_table(slugs)
    players_df.to_csv(OUT_DIR / "players.csv", index=False)
    print(f"  saved players.csv ({len(players_df)} rows)")

    events_df, empty_pbp_games = build_events_table(slugs, games_df)
    dup_event_ids = (
        events_df.groupby("game_slug")["event_id"]
        .apply(lambda s: s[s.duplicated()].tolist())
    )
    dup_event_ids = {k: v for k, v in dup_event_ids.items() if v}
    if dup_event_ids:
        print(f"  WARNING: duplicate event_id within a game: {dup_event_ids}")
    if empty_pbp_games:
        print(f"  WARNING: empty play-by-play feed for games: {empty_pbp_games}")
    events_df.to_csv(OUT_DIR / "events.csv", index=False)
    print(f"  saved events.csv ({len(events_df)} rows)")

    pgs_df = build_player_game_stats(slugs, games_df)
    pgs_df.to_csv(OUT_DIR / "player_game_stats.csv", index=False)
    print(f"  saved player_game_stats.csv ({len(pgs_df)} rows)")

    tgs_df, tgs_exceptions_df = build_team_game_stats(slugs, games_df)
    tgs_df.to_csv(OUT_DIR / "team_game_stats.csv", index=False)
    print(f"  saved team_game_stats.csv ({len(tgs_df)} rows, participant-filtered)")
    tgs_exceptions_df.to_csv(OUT_DIR / "team_game_stats_exceptions.csv", index=False)
    print(f"  saved team_game_stats_exceptions.csv ({len(tgs_exceptions_df)} rejected/missing rows)")
    if len(tgs_exceptions_df):
        print(tgs_exceptions_df[["game_slug", "officialId", "rejection_reason"]].to_string(index=False))
    tgs_problems = validate_team_game_stats(tgs_df, games_df)
    if tgs_problems:
        print("  TEAM_GAME_STATS VALIDATION FAILED:")
        for p in tgs_problems:
            print(f"    - {p}")
    else:
        print("  team_game_stats.csv validated: exactly 2 distinct participant teams per completed game; (game_id, officialId) unique")

    unresolved_df = check_player_id_resolution(events_df, player_lookup_by_id)
    unresolved_df.to_csv(OUT_DIR / "unresolved_player_ids.csv", index=False)
    print(f"  unresolved player IDs referenced in events: {len(unresolved_df)}")
    if len(unresolved_df):
        print(unresolved_df.to_string(index=False))

    unresolved_teams_df = check_team_id_resolution(events_df, games_df, teams_df)
    unresolved_teams_df.to_csv(OUT_DIR / "unresolved_team_ids.csv", index=False)
    print(f"  unresolved team IDs: {len(unresolved_teams_df)}")
    if len(unresolved_teams_df):
        print(unresolved_teams_df.to_string(index=False))

    print()
    print("Done.")


if __name__ == "__main__":
    main()
