"""RSS/Atom fetching. One feed failure never blocks the others."""
import calendar
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import feedparser
import requests

from . import tags as tag_module

USER_AGENT = "AITransformationDashboard/1.0 (personal daily briefing bot)"
TIMEOUT_SECONDS = 12
MAX_ENTRY_AGE_DAYS = 14  # perf guard only — the real freshness cutoff is applied later in run.py
MAX_WORKERS = 8


def fetch_feed(name: str, url: str) -> tuple[list[dict], str | None]:
    """Returns (items, error_message). error_message is None on success."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as e:
        return [], f"{name}: {e}"

    parsed = feedparser.parse(resp.content)
    if parsed.bozo and not parsed.entries:
        return [], f"{name}: unparseable feed ({parsed.bozo_exception})"

    age_cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_ENTRY_AGE_DAYS)
    items = []
    for entry in parsed.entries:
        published_at = _entry_datetime(entry)
        if published_at is None:
            continue  # every shown item must carry a real publish date
        if published_at < age_cutoff:
            continue  # skip parsing full historical archives some feeds return
        headline = (entry.get("title") or "").strip()
        raw_summary = _clean_summary(entry)
        items.append({
            "headline": headline,
            "raw_summary": raw_summary,
            "source_name": name,
            "source_url": entry.get("link") or url,
            "published_at": published_at.isoformat(),
            "image_url": _entry_image(entry),
            "tags": tag_module.keyword_tags(headline, raw_summary),
        })
    return items, None


def _entry_image(entry) -> str | None:
    if entry.get("media_thumbnail"):
        return entry.media_thumbnail[0].get("url")
    if entry.get("media_content"):
        return entry.media_content[0].get("url")
    for enc in entry.get("enclosures", []):
        if enc.get("type", "").startswith("image/") or enc.get("href", "").rstrip("/").lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return enc.get("href")
    summary_html = entry.get("summary") or entry.get("description") or ""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)', summary_html)
    return m.group(1) if m else None


def _entry_datetime(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        t = entry.get(field)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
    return None


def _clean_summary(entry) -> str:
    text = entry.get("summary") or entry.get("description") or ""
    # strip any embedded HTML tags — feed descriptions are often raw HTML
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:600]


def fetch_all(sources_by_category: dict[str, list[dict]]) -> tuple[dict[str, list[dict]], list[str], list[str]]:
    """Fetch every configured source concurrently. Returns (items_by_category, sources_ok, errors)."""
    items_by_category: dict[str, list[dict]] = {cat: [] for cat in sources_by_category}
    sources_ok: list[str] = []
    errors: list[str] = []

    jobs = [(cat, s) for cat, sources in sources_by_category.items() for s in sources]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_feed, s["name"], s["url"]): (cat, s) for cat, s in jobs}
        for future in as_completed(futures):
            cat, source = futures[future]
            items, error = future.result()
            if error:
                errors.append(error)
            else:
                sources_ok.append(source["name"])
                items_by_category[cat].extend(items)

    return items_by_category, sources_ok, errors
