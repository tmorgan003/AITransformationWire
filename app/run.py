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
    freshness_hours = config.get("freshness_hours", 36)

    have_key = bool(os.environ.get("ANTHROPIC_API_KEY"))

    conn = store.connect()
    store.prune_old(conn)
    run_id = store.start_run(conn)
    errors: list[str] = []

    items_by_category, sources_ok, fetch_errors = fetchers.fetch_all(config["sources"])
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

    # Popular AI RSS feeds: mechanical fetch only — never sent to Claude, so this section costs
    # nothing to refresh regardless of how often the page is reloaded. Own 14-day window,
    # independent of the tight daily-briefing freshness_hours cutoff above: the main page shows
    # the latest slice, the full two weeks lives on its own "show more" page (see render.py).
    popular_cutoff = datetime.now(timezone.utc) - timedelta(days=fetchers.MAX_ENTRY_AGE_DAYS)
    popular_rss_by_cat, popular_sources_ok, popular_errors = fetchers.fetch_all(
        {"popular_rss": config.get("popular_rss_feeds", [])})
    errors.extend(popular_errors)
    popular_names = [s["name"] for s in config.get("popular_rss_feeds", [])]
    sources_ok = sources_ok + popular_sources_ok
    sources_failed = sources_failed + [s for s in popular_names if s not in popular_sources_ok]
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
        item_lookup = summarize.write_pending_items(filtered)
        manual = summarize.load_manual_curated(item_lookup)
        if manual is not None:
            curated = manual
            _log(f"DEV MODE used manually-curated data from {summarize.MANUAL_CURATED_PATH.name}")
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
