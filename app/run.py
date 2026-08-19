"""Orchestrator: fetch -> filter -> dedup -> summarize -> render -> log. One failure never aborts the run."""
import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import fetchers, store, summarize, render  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "logs" / "run.log"
CACHE_PATH = ROOT / "cache" / "fetch_cache.json"


def _log(line: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} {line}\n")


def main() -> int:
    # Top-level guard: a source outage must never mean "no briefing ships" (per spec). Per-source
    # failures are already caught in fetchers.py; this catches everything else (bad config,
    # DB issues, an unexpected exception anywhere in the pipeline) and still writes a dashboard.
    try:
        return _run()
    except Exception as e:  # noqa: BLE001
        _log(f"FATAL {e}\n{traceback.format_exc()}")
        try:
            render.write_dashboard(summarize._empty_result(), {}, [], ["(run crashed before sources could be checked)"], [])
        except Exception:  # noqa: BLE001 - last resort only, never let the fallback itself crash
            pass
        return 1


def _run() -> int:
    config = json.loads((ROOT / "config.json").read_text())
    freshness_hours = config.get("freshness_hours", 120)

    have_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    force_refresh = "--refresh" in sys.argv or os.environ.get("FORCE_REFRESH") == "1"

    conn = store.connect()
    store.prune_old(conn)
    run_id = store.start_run(conn)
    errors: list[str] = []

    # Fetching ~100 RSS sources is the slow, network-bound part of a run. A code-only change
    # (render tweak, prompt edit) shouldn't have to re-pull every feed to see its effect, so the
    # raw fetch result is cached and reused until it's older than freshness_hours — at that point
    # the cache can no longer contain anything within the briefing's own freshness window anyway,
    # so a live re-fetch is unavoidable. --refresh (or FORCE_REFRESH=1) forces one sooner.
    cached = None
    if not force_refresh and CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            cache_age = datetime.now(timezone.utc) - datetime.fromisoformat(cached["fetched_at"])
            if cache_age > timedelta(hours=freshness_hours):
                cached = None
        except (OSError, json.JSONDecodeError, KeyError, ValueError):
            cached = None

    if cached is not None:
        items_by_category = cached["items_by_category"]
        sources_ok = cached["sources_ok"]
        fetch_errors = cached["fetch_errors"]
        popular_rss_by_cat = cached["popular_rss_by_cat"]
        popular_sources_ok = cached["popular_sources_ok"]
        popular_errors = cached["popular_errors"]
        _log(f"using cached fetch from {cached['fetched_at']} — pass --refresh to force a live pull")
    else:
        items_by_category, sources_ok, fetch_errors = fetchers.fetch_all(config["sources"])
        # Popular AI RSS feeds: mechanical fetch only — never sent to Claude, so this section
        # costs nothing to refresh regardless of how often the page is reloaded.
        popular_rss_by_cat, popular_sources_ok, popular_errors = fetchers.fetch_all(
            {"popular_rss": config.get("popular_rss_feeds", [])})
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps({
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "items_by_category": items_by_category,
            "sources_ok": sources_ok,
            "fetch_errors": fetch_errors,
            "popular_rss_by_cat": popular_rss_by_cat,
            "popular_sources_ok": popular_sources_ok,
            "popular_errors": popular_errors,
        }, indent=2), encoding="utf-8")

    errors.extend(fetch_errors)
    sources_all = [s["name"] for cat in config["sources"].values() for s in cat]
    sources_failed = [s for s in sources_all if s not in sources_ok]

    cutoff = datetime.now(timezone.utc) - timedelta(hours=freshness_hours)
    seen = store.seen_hashes(conn)
    filtered: dict[str, list[dict]] = {}
    for category, items in items_by_category.items():
        fresh = [it for it in items if datetime.fromisoformat(it["published_at"]) >= cutoff]
        deduped = [it for it in fresh if store.headline_hash(it["headline"]) not in seen]
        filtered[category] = deduped

    # Popular RSS keeps its own 14-day window, independent of the tighter daily-briefing
    # freshness_hours cutoff above: the main page shows the latest slice, the full two weeks
    # lives on its own "show more" page (see render.py).
    errors.extend(popular_errors)
    popular_names = [s["name"] for s in config.get("popular_rss_feeds", [])]
    sources_ok = sources_ok + popular_sources_ok
    sources_failed = sources_failed + [s for s in popular_names if s not in popular_sources_ok]
    popular_cutoff = datetime.now(timezone.utc) - timedelta(days=fetchers.MAX_ENTRY_AGE_DAYS)
    popular_all = [it for it in popular_rss_by_cat.get("popular_rss", [])
                   if datetime.fromisoformat(it["published_at"]) >= popular_cutoff]
    popular_all.sort(key=lambda it: it["published_at"], reverse=True)

    total_items = sum(len(v) for v in filtered.values())
    _log(f"fetched {sum(len(v) for v in items_by_category.values())} raw, "
         f"{total_items} after freshness+dedup filter, {len(popular_all)} popular-rss items "
         f"(14-day window), {len(sources_failed)} sources failed")

    if have_key:
        try:
            curated, item_lookup = summarize.curate(filtered)
        except Exception as e:  # noqa: BLE001 - a bad Claude call must not crash the whole run
            errors.append(f"summarize: {e}")
            _log(f"ERROR summarize failed: {e}\n{traceback.format_exc()}")
            curated, item_lookup = summarize._empty_result(), {}
    else:
        # Dev mode: no ANTHROPIC_API_KEY. Never call the API — write the fetched items for
        # manual curation, and use whatever curation is already waiting (if any) instead.
        # item_lookup for RESOLVING curated item_ids is built from the full (undeduped) fetch,
        # not `filtered`: `filtered` excludes items already marked "seen" by a prior run, but a
        # previously-produced curation (fresh manual submission or the persisted cache) still
        # needs to resolve those same items on every re-render, not just the run that first
        # curated them.
        _, item_lookup = summarize.build_flat_items(items_by_category)
        summarize.write_pending_items(filtered)
        manual = summarize.load_manual_curated(item_lookup)
        if manual is not None:
            curated = manual
            _log(f"DEV MODE used manually-curated data from {summarize.MANUAL_CURATED_PATH.name} (cached for future runs)")
        else:
            cached_curated = summarize.load_curated_cache()
            if cached_curated is not None:
                curated = cached_curated
                _log(f"DEV MODE reused cached curated data from {summarize.CURATED_CACHE_PATH}")
            else:
                curated = summarize._empty_result()
                errors.append("no ANTHROPIC_API_KEY — items written for manual curation, no curated data yet")
                _log(f"DEV MODE no ANTHROPIC_API_KEY — wrote {summarize.PENDING_ITEMS_PATH.name} for manual curation")
                print(f"No ANTHROPIC_API_KEY set. Fetched items written to {summarize.PENDING_ITEMS_PATH}.")

    out_path = render.write_dashboard(curated, item_lookup, sources_ok, sources_failed, popular_all)

    shown = []
    unresolved = 0
    for key in curated:
        if key == "questions":
            continue
        for ci in curated[key]:
            raw = item_lookup.get(ci.get("item_id"))
            if raw:
                shown.append(raw)
            else:
                unresolved += 1
    if unresolved:
        _log(f"WARN {unresolved} curated item_id(s) did not resolve to a fetched item — dropped from output")
    store.mark_shown(conn, shown)

    store.finish_run(conn, run_id, sources_ok, sources_failed, total_items, errors)
    _log(f"DONE wrote {out_path.name}, {len(shown)} items shown, {len(errors)} errors")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
