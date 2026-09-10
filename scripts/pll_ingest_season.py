"""
Phase 3 (repaired in Phase 4.25): full-season raw data ingestion.

Discovers all 2026 games from the public schedule endpoint, classifies them
by status, and downloads the 4 per-game endpoints (play-by-play, game meta,
player stats, team stats) for every completed game, under:

    data/raw/2026/<slug>/{play_by_play,game_meta,players_stats,teams_stats}.json

Safely resumable and safe to rerun after the season progresses: the
schedule is always re-fetched fresh (so newly-completed games are detected
automatically — a game's eventStatus can change from 0 to 3 between runs),
but a given completed game's 4 raw files are only downloaded once per
--force invocation — a game is skipped (no network call) if all 4 already
exist AND pass structural validation (see `validate_payload`). Games with
eventStatus==0 (not yet played) are never queried beyond the schedule row
itself — no play-by-play/box-score request is made for them, since that
data doesn't exist yet. Polite rate limiting (sleep between requests) is
applied. Failures are logged and do not stop the run; a summary of failed
games is printed and saved at the end so a re-run can retry just those.
Nothing here hard-codes a game count — the schedule response is the sole
source of truth for how many games exist and which are complete.

Phase 4.25 repairs over the Phase 3 version:
  - `--force` actually re-downloads and replaces already-cached endpoint
    files (previously it was silently ignored inside `ingest_game`, so a
    forced rerun never re-fetched anything that already existed on disk).
  - Structural validation (`validate_payload`) replaces the old "truthy
    JSON" cache-hit check: a non-empty JSON envelope with an empty/missing
    `data.items` (or missing required game_meta fields) is no longer
    accepted as a valid cache hit or a valid download.
  - Every write is atomic (write to a temp file in the same directory, then
    `os.replace`) so a failed/partial download can never clobber a
    previously valid cached file.
  - Before a valid cached file is replaced by a refreshed download, the OLD
    content is preserved as a versioned snapshot under
    `<slug>/_snapshots/<endpoint>__<retrieved_at>__<hash10>.json`, and
    `<slug>/_meta.json` tracks, per endpoint, the retrieval time, source
    URL, and content hash of what is currently on disk.
  - Outcomes are classified explicitly per endpoint: `ok` (fetched or
    already valid), `incomplete_download` (network/HTTP/JSON-parse
    failure), `empty_feed` (well-formed envelope, but `data.items` is
    empty for an endpoint that requires it), `unavailable_pbp` (play-by-
    play specifically empty for a completed game — flagged for manual
    review rather than silently cached as "done"), `unchanged`
    (re-fetched under --force, content identical to what was cached), and
    `changed` (re-fetched under --force, content differs — see the
    snapshot/diff behavior above).

Usage:
    python3 pll_ingest_season.py [--force] [--sleep 0.4] [--games slug1,slug2]
"""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = "https://stats.premierlacrosseleague.com/api/v4"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

REPO_ROOT = Path(__file__).resolve().parent.parent

# Phase 9: the season is module state with a 2026 default, so every existing
# caller, test and cached path keeps working untouched while the same client
# can retrieve 2022-2025. Nothing about the 2026 code path changes.
SEASON = 2026


def set_season(year: int) -> None:
    """Point the ingester at a season. Affects the schedule path, the raw
    directory and the Referer, which are the only season-dependent things."""
    global SEASON, SCHEDULE_PATH
    SEASON = int(year)
    SCHEDULE_PATH = (REPO_ROOT / "data" / "raw" / str(SEASON) / "_schedule"
                     / f"games_{SEASON}.json")


SCHEDULE_PATH = REPO_ROOT / "data" / "raw" / "2026" / "_schedule" / "games_2026.json"

ENDPOINTS = {
    "play_by_play": "games/{slug}/play-by-plays",
    "game_meta": "games/{slug}",
    "players_stats": "games/{slug}/players/stats",
    "teams_stats": "games/{slug}/teams/stats",
}


def referer_for(slug: str) -> str:
    """The stats site's own game URL.

    The public API rejects a request that carries neither an Origin nor a
    Referer with `403 {"error":"Origin not allowed"}`. This client has always
    sent the ordinary Referer a browser sends when viewing that game's page on
    the league's own stats site, which is why 2026 ingestion worked; Phase 9
    only makes the season in that URL follow the season being fetched. No
    access control is bypassed and no header is forged beyond identifying the
    page the request is made from.
    """
    return f"https://stats.premierlacrosseleague.com/games/{SEASON}/{slug}?tab=plays"


def fetch_json(url: str, slug: str) -> dict:
    headers = dict(HEADERS)
    headers["Referer"] = referer_for(slug)
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def content_hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically: a failed write can never leave a partial or
    corrupt file at `path`, and a crash mid-write cannot clobber a
    previously good file (the temp file is only renamed into place after a
    fully successful write+flush)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{time.time_ns()}")
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def validate_payload(name: str, data: dict, is_completed_game: bool = True) -> tuple:
    """
    Structural validation beyond "is this truthy JSON". Returns
    (status, detail) where status is one of:
      "ok"             - well-formed and has the content it should
      "empty_feed"     - well-formed envelope but data.items is empty
                         (for endpoints that always require rows)
      "unavailable_pbp" - play_by_play specifically empty (distinct from
                         empty_feed because a genuinely completed game
                         with 0 PBP events is a stronger anomaly signal
                         than an empty player/team stats list, and is
                         reported separately per the ingestion brief)
      "malformed"      - missing the envelope/keys entirely
    A non-empty JSON envelope is NOT sufficient on its own for any of
    these endpoints — every one of them is expected to carry a non-empty
    `data.items` list (game_meta additionally requires real score fields)
    for a completed game.
    """
    if not isinstance(data, dict) or "data" not in data:
        return "malformed", f"{name}: missing top-level 'data' key"

    inner = data["data"]
    if name == "game_meta":
        if not isinstance(inner, dict):
            return "malformed", "game_meta: 'data' is not an object"
        required = ("homeTeam", "awayTeam")
        missing = [k for k in required if not inner.get(k)]
        if missing:
            return "malformed", f"game_meta: missing {missing}"
        if is_completed_game and (inner.get("homeScore") is None or inner.get("visitorScore") is None):
            return "malformed", "game_meta: completed game missing homeScore/visitorScore"
        return "ok", ""

    # play_by_play / players_stats / teams_stats all share the
    # {"data": {"items": [...]}} shape.
    items = inner.get("items") if isinstance(inner, dict) else None
    if items is None:
        return "malformed", f"{name}: missing 'data.items'"
    if not isinstance(items, list):
        return "malformed", f"{name}: 'data.items' is not a list"
    if len(items) == 0:
        if name == "play_by_play":
            return "unavailable_pbp", "play_by_play: 'data.items' is empty for a completed game"
        return "empty_feed", f"{name}: 'data.items' is empty"
    return "ok", ""


def fetch_schedule(offline: bool = False) -> dict:
    """
    The schedule is always re-fetched (it's one cheap request) so that
    reruns detect games that have newly completed since the last run —
    unlike per-game raw data, it is NOT treated as immutable/cached,
    because its content (eventStatus) changes over time for the same URL.
    Pass offline=True only to reuse the last-saved copy (e.g. for local
    testing without network access); this is not used in normal operation.
    """
    if offline:
        return json.loads(SCHEDULE_PATH.read_text())
    data = fetch_json(f"{BASE_URL}/games?year={SEASON}", "schedule")
    status, detail = validate_payload("schedule", data)
    if status != "ok":
        raise RuntimeError(f"Schedule response failed structural validation: {detail}")
    atomic_write_json(SCHEDULE_PATH, data)
    return data


def has_final_scores(it: dict) -> bool:
    return it.get("homeScore") is not None and it.get("visitorScore") is not None


def classify_games(schedule: dict):
    """Split the schedule into completed / upcoming / other.

    eventStatus==3 is the league's normal "final" marker and is the only status
    2026 ever uses. Phase 9 found that the 2023 feed marks FOUR played games
    with eventStatus==2 while still carrying real final scores -- two regular
    season games, a quarterfinal, and the 2023 CHAMPIONSHIP. Treating status 3
    as the sole completion signal would silently drop them, so a status-2 row
    that carries both final scores is admitted as completed and is separately
    reported so the anomaly stays visible rather than being normalized away.
    Rows with any other status, or status 2 with no scores, stay in `other`.
    """
    items = schedule["data"]["items"]
    completed, upcoming, other = [], [], []
    for it in items:
        status = it.get("eventStatus")
        if status == 3:
            completed.append(it)
        elif status == 0:
            upcoming.append(it)
        elif status == 2 and has_final_scores(it):
            completed.append(it)
        else:
            other.append(it)
    return completed, upcoming, other


def raw_dir_for(slug: str) -> Path:
    return REPO_ROOT / "data" / "raw" / str(SEASON) / slug


def meta_path_for(slug: str) -> Path:
    return raw_dir_for(slug) / "_meta.json"


def load_meta(slug: str) -> dict:
    p = meta_path_for(slug)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_meta(slug: str, meta: dict) -> None:
    atomic_write_json(meta_path_for(slug), meta)


def load_existing_endpoint(slug: str, name: str):
    """Returns (data_or_None, status) for whatever is currently on disk."""
    p = raw_dir_for(slug) / f"{name}.json"
    if not p.exists():
        return None, "missing"
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None, "malformed"
    status, _ = validate_payload(name, data)
    return data, status


def snapshot_old_file(slug: str, name: str, old_data: dict, old_meta_entry: dict) -> str:
    """Preserve the file about to be overwritten as a versioned snapshot.
    Returns the snapshot's relative path (for logging)."""
    snap_dir = raw_dir_for(slug) / "_snapshots"
    retrieved_at = old_meta_entry.get("retrieved_at", "unknown-retrieval-time")
    safe_retrieved_at = retrieved_at.replace(":", "-")
    h = old_meta_entry.get("content_hash") or content_hash(old_data)
    snap_path = snap_dir / f"{name}__{safe_retrieved_at}__{h[:10]}.json"
    if not snap_path.exists():  # identical retrieval already snapshotted
        atomic_write_json(snap_path, old_data)
    return str(snap_path.relative_to(REPO_ROOT))


def diff_play_by_play(old_data: dict, new_data: dict) -> dict:
    """Event-ID-level diff of two play_by_play payloads, keyed on markerId."""
    old_items = {it.get("markerId"): it for it in old_data.get("data", {}).get("items", [])}
    new_items = {it.get("markerId"): it for it in new_data.get("data", {}).get("items", [])}
    added = sorted(set(new_items) - set(old_items))
    removed = sorted(set(old_items) - set(new_items))
    changed = sorted(
        mid for mid in (set(old_items) & set(new_items))
        if old_items[mid] != new_items[mid]
    )
    return {"added": added, "removed": removed, "changed": changed}


def already_cached(slug: str) -> bool:
    for name in ENDPOINTS:
        data, status = load_existing_endpoint(slug, name)
        if status != "ok":
            return False
    return True


def ingest_endpoint(slug: str, name: str, path_tmpl: str, force: bool, is_completed_game: bool) -> dict:
    """
    Fetch (or validate-and-skip) one endpoint for one game.
    Returns a result dict: {"endpoint", "outcome", "detail", "snapshot"}
    outcome in: skipped_cached, ok (freshly fetched, nothing cached before),
    unchanged (force re-fetch, identical content), changed (force re-fetch,
    different content, snapshot + diff recorded), incomplete_download,
    empty_feed, unavailable_pbp.
    """
    existing_data, existing_status = load_existing_endpoint(slug, name)
    meta = load_meta(slug)

    if not force and existing_status == "ok":
        return {"endpoint": name, "outcome": "skipped_cached", "detail": "", "snapshot": None}

    url = f"{BASE_URL}/{path_tmpl.format(slug=slug)}"
    try:
        data = fetch_json(url, slug)
    except Exception as e:  # noqa: BLE001
        return {"endpoint": name, "outcome": "incomplete_download", "detail": str(e), "snapshot": None}

    status, detail = validate_payload(name, data, is_completed_game=is_completed_game)
    if status != "ok":
        # A failed/invalid download must never replace a previously valid
        # cached file — if we had nothing valid cached, this game just
        # stays unfetched (retryable); if we DID have something valid
        # cached, it is left untouched on disk.
        return {"endpoint": name, "outcome": status, "detail": detail, "snapshot": None}

    new_hash = content_hash(data)
    # Prefer the recorded meta hash, but fall back to hashing the actual
    # on-disk content directly — this matters the first time _meta.json is
    # introduced for an already-cached game, where there is no prior
    # recorded hash to compare against even though a valid file exists.
    old_hash = meta.get(name, {}).get("content_hash")
    if old_hash is None and existing_data is not None:
        old_hash = content_hash(existing_data)
    snapshot_rel = None
    outcome = "ok"

    if existing_status == "ok" and existing_data is not None:
        if new_hash == old_hash:
            outcome = "unchanged"
        else:
            outcome = "changed"
            snapshot_rel = snapshot_old_file(slug, name, existing_data, meta.get(name, {}))
            if name == "play_by_play":
                pbp_diff = diff_play_by_play(existing_data, data)
                detail = (f"events added={len(pbp_diff['added'])} removed={len(pbp_diff['removed'])} "
                           f"changed={len(pbp_diff['changed'])}")
                if pbp_diff["changed"]:
                    detail += f"; changed_marker_ids(sample)={pbp_diff['changed'][:10]}"

    out_path = raw_dir_for(slug) / f"{name}.json"
    atomic_write_json(out_path, data)
    meta[name] = {
        "retrieved_at": utc_now_iso(),
        "url": url,
        "content_hash": new_hash,
    }
    save_meta(slug, meta)

    return {"endpoint": name, "outcome": outcome, "detail": detail, "snapshot": snapshot_rel}


def ingest_game(slug: str, sleep_sec: float, force: bool, is_completed_game: bool = True) -> dict:
    d = raw_dir_for(slug)
    d.mkdir(parents=True, exist_ok=True)
    result = {"slug": slug, "ok": True, "endpoints": []}
    for name, path_tmpl in ENDPOINTS.items():
        r = ingest_endpoint(slug, name, path_tmpl, force, is_completed_game)
        result["endpoints"].append(r)
        if r["outcome"] in ("incomplete_download", "empty_feed", "malformed"):
            result["ok"] = False
        if r["outcome"] != "skipped_cached":
            time.sleep(sleep_sec)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="re-download game data even if cached, replacing it if changed (preserving the prior version as a snapshot)")
    parser.add_argument("--offline", action="store_true", help="reuse the last-saved schedule instead of re-fetching")
    parser.add_argument("--sleep", type=float, default=0.4, help="seconds between requests")
    parser.add_argument("--games", type=str, default=None, help="comma-separated slug allowlist, for targeted re-ingestion/testing (default: all completed games)")
    parser.add_argument("--year", type=int, default=SEASON, help="season to ingest (default 2026)")
    args = parser.parse_args()
    set_season(args.year)
    print(f"Season: {SEASON}")

    print("Fetching schedule ..." if not args.offline else "Loading cached schedule (--offline) ...")
    try:
        schedule = fetch_schedule(offline=args.offline)
    except Exception as e:  # noqa: BLE001
        print(f"LIVE SCHEDULE UNAVAILABLE ({e}). Cannot refresh or discover newly-completed games this run.")
        print("Falling back to the last cached schedule for informational purposes only; "
              "no completeness claim is made from it.")
        schedule = json.loads(SCHEDULE_PATH.read_text())

    completed, upcoming, other = classify_games(schedule)
    if args.games:
        allow = set(args.games.split(","))
        completed = [g for g in completed if g["slugname"] in allow]

    print(f"Schedule: {len(schedule['data']['items'])} total games — "
          f"{len(completed)} completed{' (filtered by --games)' if args.games else ''}, "
          f"{len(upcoming)} upcoming/not-started, {len(other)} other-status")
    print(f"  never fetches play-by-play/box-score data for upcoming/not-started games — "
          f"those endpoint calls are only made for eventStatus==3 games")
    if other:
        print("  other-status games:", [(g["slugname"], g.get("eventStatus")) for g in other])

    failures = []
    changed_games = []
    skipped = 0
    fetched = 0
    unchanged_ct = 0
    for i, g in enumerate(completed, 1):
        slug = g["slugname"]
        if not args.force and already_cached(slug):
            skipped += 1
            continue
        print(f"[{i}/{len(completed)}] {'force-refreshing' if args.force else 'fetching'} {slug} ...")
        result = ingest_game(slug, args.sleep, args.force)
        outcomes = {r["endpoint"]: r["outcome"] for r in result["endpoints"]}
        if any(o == "changed" for o in outcomes.values()):
            changed_games.append({"slug": slug, "endpoints": {k: v for k, v in outcomes.items() if v == "changed"},
                                   "detail": {r["endpoint"]: r["detail"] for r in result["endpoints"] if r["outcome"] == "changed"}})
        if result["ok"]:
            fetched += 1
            if all(o in ("unchanged",) for o in outcomes.values()):
                unchanged_ct += 1
        else:
            failures.append(result)
            bad = [f"{r['endpoint']}:{r['outcome']}({r['detail']})" for r in result["endpoints"] if r["outcome"] not in ("ok", "unchanged", "changed", "skipped_cached")]
            print(f"  ISSUES: {bad}")

    print()
    print(f"Done. {fetched} games processed with no unresolved issues, {skipped} already cached (skipped, no network call), "
          f"{len(failures)} with unresolved issues.")
    if args.force:
        print(f"  of the processed games: {unchanged_ct} identical to cache, {len(changed_games)} had at least one changed endpoint")
    if changed_games:
        print(f"Games with CHANGED content vs. prior snapshot: {[c['slug'] for c in changed_games]}")
        diff_path = SCHEDULE_PATH.parent / "refresh_diff.json"
        atomic_write_json(diff_path, {"generated_at": utc_now_iso(), "changed_games": changed_games})
        print(f"Saved diff detail to {diff_path.relative_to(REPO_ROOT)}")
    if failures:
        print("Games with unresolved issues:", [f["slug"] for f in failures])
        fail_path = SCHEDULE_PATH.parent / "ingest_failures.json"
        atomic_write_json(fail_path, {"generated_at": utc_now_iso(), "failures": failures})
        print(f"Saved failure details to {fail_path.relative_to(REPO_ROOT)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
