"""Render the curated briefing to a single self-contained HTML file, plus an archive index.

<!--
THESIS: An AI briefing that reads like an actual newsroom front page, not a list of
  cards — one lead story earns the front, everything else is an indexed, color-coded wire.
OWN-WORLD: Wire-service red masthead rule, Archivo Black display type, one named accent
  color per beat (frontier labs / dev tools / enterprise AI / platforms / research /
  community), hairline-divided list rows instead of boxed cards, color-block image
  fallback when a story has no photo.
STORY: The analyst scans the lead in one glance, sees which beat every other item
  belongs to by color alone, and never mistakes the unfiltered RSS wire for curated
  content — its section is deliberately desaturated.
FIRST VIEWPORT: Masthead (site name + red rule) → lead story (full-width image or
  color-block, black display headline, dek) → secondary top-signal row (2-up).
FORM: Editorial/wire-service redesign of the prior boxed-card layout, direction pinned
  by the user as "The Verge / tech-news style."
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish
  review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.
-->
"""
import html
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .tags import TAG_VOCAB

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
RSS_MAIN_PAGE_LIMIT = 15

# The site's four pages, shared by every generated page and the live server's /settings page,
# so the app reads as one multi-page site instead of one page plus a bolted-on admin form.
SITE_PAGES = [
    ("today", "Today", "/"),
    ("archive", "Archive", "/archive"),
    ("popular-rss", "Popular RSS", "/output/popular-rss-all.html"),
    ("settings", "Settings", "/settings"),
]


def tag_filter_html() -> str:
    buttons = '<button class="active" data-tag="">All</button>' + "".join(
        f'<button data-tag="{html.escape(t)}">{html.escape(t)}</button>' for t in TAG_VOCAB
    )
    return f'<div class="tag-filter" aria-label="Filter by topic">{buttons}</div>'


TAG_FILTER_JS = """
document.querySelectorAll('.tag-filter').forEach(function (bar) {
  bar.addEventListener('click', function (e) {
    var btn = e.target.closest('button');
    if (!btn) return;
    bar.querySelectorAll('button').forEach(function (b) { b.classList.remove('active'); });
    btn.classList.add('active');
    var tag = btn.dataset.tag;
    document.querySelectorAll('[data-tags]').forEach(function (el) {
      var tags = (el.dataset.tags || '').split('|');
      el.classList.toggle('filter-hidden', tag !== '' && tags.indexOf(tag) === -1);
    });
  });
});
"""


def site_nav_html(active: str) -> str:
    links = "".join(
        f'<a href="{href}"{" class=\"active\"" if slug == active else ""}>{label}</a>'
        for slug, label, href in SITE_PAGES
    )
    return f'<nav class="site-nav" aria-label="Site">{links}</nav>'


def _config() -> dict:
    try:
        return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _local_zone(config: dict | None = None) -> ZoneInfo:
    config = config if config is not None else _config()
    return ZoneInfo(config.get("timezone", "America/Chicago"))


def _homepage_map(config: dict) -> dict[str, str]:
    # name -> real homepage (not the RSS/query URL), shared by the Resources chips and by the
    # per-article source tag so both point at the same place.
    seen: dict[str, str] = {}
    for feed in config.get("popular_rss_feeds", []):
        seen.setdefault(feed["name"], feed.get("homepage", feed["url"]))
    for feeds in config.get("sources", {}).values():
        for feed in feeds:
            seen.setdefault(feed["name"], feed.get("homepage", feed["url"]))
    return seen


def _resources_html(config: dict) -> str:
    # Every configured source, name + link to its real homepage — so the analyst can see and
    # click through to what's actually feeding the briefing.
    chips = "".join(
        f'<a class="chip" href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(name)}</a>'
        for name, url in sorted(_homepage_map(config).items())
    )
    return f'<div class="resources">{chips}</div>'


SECTION_TITLES = {
    "top_signal": "Top Signal",
    "frontier_labs": "Frontier Model & Lab News",
    "dev_tools": "Agentic & AI-Assisted Dev Tools",
    "enterprise_ai": "Enterprise AI & Business Transformation",
    "journalism": "Tech & Business Press",
    "enterprise_platforms": "Enterprise Platform Updates",
    "research_digest": "Research & Technical Digest",
    "community_pulse": "Community Pulse",
}

# One named accent per beat — a real taxonomy of content verticals, not decoration.
SECTION_COLORS = {
    "frontier_labs": "blue",
    "dev_tools": "green",
    "enterprise_ai": "violet",
    "journalism": "slate",
    "enterprise_platforms": "amber",
    "research_digest": "teal",
    "community_pulse": "magenta",
}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@600;800;900&display=swap');

:root {
  color-scheme: light dark;
  --bg: #ffffff; --ink: #0a0a0a; --ink-soft: #4b4b4b; --line: #e3e3de; --line-strong: #0a0a0a;
  --signal: #e8291c; --signal-ink: #ffffff;
  --blue: #1d4ed8; --green: #0f8a4f; --violet: #7c3aed; --amber: #c2680a; --teal: #0891b2; --magenta: #c0227a; --slate: #475569;
  --muted: #6b7280;
  --card-hover: rgba(10,10,10,0.04);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0b0b0d; --ink: #f2f2f0; --ink-soft: #b7b7b2; --line: #2a2a2c; --line-strong: #f2f2f0;
    --signal: #ff5b4d; --signal-ink: #0b0b0d;
    --blue: #6a9bff; --green: #3ddc97; --violet: #b794ff; --amber: #ffb648; --teal: #4dd6ec; --magenta: #ff7ac6; --slate: #94a3b8;
    --muted: #9a9a9f;
    --card-hover: rgba(255,255,255,0.055);
  }
}

* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  max-width: 900px; margin: 0 auto; padding: 0 20px 96px;
  line-height: 1.5; color: var(--ink); background: var(--bg);
  font-variant-numeric: tabular-nums;
}
::selection { background: var(--signal); color: var(--signal-ink); }
:focus-visible { outline: 2px solid var(--signal); outline-offset: 3px; }
::-webkit-scrollbar { width: 12px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--line); border-radius: 8px; border: 3px solid var(--bg); }
* { scrollbar-color: var(--line) var(--bg); }

a { color: inherit; }

header.masthead { padding: 28px 0 14px; border-bottom: 4px solid var(--line-strong); margin-bottom: 8px;
  display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 8px 20px; }
header.masthead h1 { font-family: Archivo, sans-serif; font-weight: 900; letter-spacing: -0.03em;
  font-size: clamp(1.6rem, 4.5vw, 2.4rem); margin: 0; line-height: 1.02; }
header.masthead .byline { font-size: 0.82rem; color: var(--ink-soft); }
header.masthead .meta-row { font-size: 0.85rem; color: var(--ink-soft); display: flex; gap: 14px; align-items: baseline; }

nav.site-nav { display: flex; gap: 18px; }
nav.site-nav a { font-family: Archivo, sans-serif; font-weight: 700; font-size: 0.85rem; color: var(--ink-soft);
  text-decoration: none; padding-bottom: 2px; border-bottom: 2px solid transparent; }
nav.site-nav a:hover { color: var(--ink); }
nav.site-nav a.active { color: var(--signal); border-bottom-color: var(--signal); }

nav.wire-nav { position: sticky; top: 0; z-index: 10; background: var(--bg); border-bottom: 1px solid var(--line);
  display: flex; gap: 4px; overflow-x: auto; padding: 10px 0; margin-bottom: 10px; -ms-overflow-style: none; scrollbar-width: none; }
nav.wire-nav::-webkit-scrollbar { display: none; }
nav.wire-nav a { flex: 0 0 auto; font-family: Archivo, sans-serif; font-weight: 700; font-size: 0.78rem;
  letter-spacing: -0.01em; text-decoration: none; padding: 6px 12px; border-radius: 999px; white-space: nowrap;
  border: 1.5px solid var(--line); color: var(--ink-soft); }
nav.wire-nav a:hover, nav.wire-nav a:focus-visible { border-color: currentColor; color: var(--nav-c, var(--ink)); }
nav.wire-nav a.nav-top { background: var(--signal); border-color: var(--signal); color: var(--signal-ink); }
section[id] { scroll-margin-top: 62px; }

/* Stretched-link pattern: the headline <a> stays inline, but its ::after covers the whole
   positioned card ancestor, so the card is click-anywhere while .src-tag (own z-index) still
   independently opens the publisher's homepage — two real links, never nested. */
.card-link { color: inherit; text-decoration: none; }
.card-link::after { content: ''; position: absolute; inset: 0; }
.src-tag { position: relative; z-index: 1; }

/* Lead story */
.lead { position: relative; display: block; margin: 22px 0 30px; }
.lead-media { width: 100%; aspect-ratio: 16/7.5; border-radius: 2px; overflow: hidden; margin-bottom: 16px;
  animation: lead-in 0.6s cubic-bezier(0.16, 1, 0.3, 1) both; }
.lead-media img { width: 100%; height: 100%; object-fit: cover; display: block; }
.lead-media.block, .top-item .media.block { display: flex; align-items: flex-end; padding: 20px; background: var(--signal); }
.top-item .media.block { padding: 14px; }
.lead-media.block span, .top-item .media.block span { font-family: Archivo, sans-serif; font-weight: 900; color: var(--signal-ink);
  font-size: 1rem; text-transform: uppercase; letter-spacing: -0.01em; opacity: 0.85; }
.top-item .media.block span { font-size: 0.78rem; }
@keyframes lead-in { from { opacity: 0; transform: scale(1.02) translateY(6px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) { .lead-media { animation: none; } }
.lead h2 { font-family: Archivo, sans-serif; font-weight: 900; letter-spacing: -0.03em;
  font-size: clamp(1.6rem, 5vw, 2.5rem); line-height: 1.04; margin: 0 0 10px; }
.lead:hover h2 { color: var(--signal); }
.lead .dek { font-size: 1.05rem; color: var(--ink-soft); max-width: 68ch; margin: 0 0 8px; }
.lead .why { font-size: 0.92rem; color: var(--signal); font-weight: 600; max-width: 68ch; margin: 8px 0 0; }
.lead .meta { font-size: 0.8rem; color: var(--muted); margin-top: 10px; }

/* Secondary top-signal row */
.top-row { display: grid; grid-template-columns: repeat(2, 1fr); gap: 22px 28px; margin-bottom: 40px; }
@media (max-width: 640px) { .top-row { grid-template-columns: 1fr; } }
.top-item { position: relative; display: block; }
.top-item .media { aspect-ratio: 16/9; border-radius: 2px; overflow: hidden; margin-bottom: 10px; }
.top-item .media img { width: 100%; height: 100%; object-fit: cover; display: block; }
.top-item h3 { font-family: Archivo, sans-serif; font-weight: 800; letter-spacing: -0.025em;
  font-size: 1.18rem; line-height: 1.15; margin: 0 0 6px; }
.top-item:hover h3 { color: var(--signal); }
.top-item .dek { font-size: 0.88rem; color: var(--ink-soft); margin: 0; }
.top-item .meta { font-size: 0.76rem; color: var(--muted); margin-top: 6px; }

/* Section beats */
h2.beat { font-family: Archivo, sans-serif; font-weight: 900; letter-spacing: -0.02em; font-size: 1.3rem;
  margin: 44px 0 4px; padding-bottom: 10px; border-bottom: 3px solid currentColor; }
h2.beat .note { font-family: -apple-system, sans-serif; font-weight: 400; font-size: 0.62em; color: var(--muted);
  letter-spacing: 0; margin-left: 8px; }
.beat-blue { color: var(--blue); } .beat-green { color: var(--green); } .beat-violet { color: var(--violet); }
.beat-amber { color: var(--amber); } .beat-teal { color: var(--teal); } .beat-magenta { color: var(--magenta); }
.beat-muted { color: var(--muted); }

.wire { border-bottom: 1px solid var(--line); }
.item-row { position: relative; display: flex; gap: 16px; padding: 16px 8px;
  border-radius: 4px; transition: background 0.15s ease; }
.item-row:hover { background: var(--card-hover); }
.item-row .thumb { flex: 0 0 76px; width: 76px; height: 76px; border-radius: 2px; overflow: hidden; }
.item-row .thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.item-row .thumb.block { display: flex; align-items: center; justify-content: center; }
.item-row .thumb.block .dot { width: 10px; height: 10px; border-radius: 50%; background: currentColor; }
.item-row .body { flex: 1; min-width: 0; }
.item-row h3 { font-family: Archivo, sans-serif; font-weight: 700; font-size: 1rem; line-height: 1.25; margin: 0 0 4px; }
.item-row:hover h3 { text-decoration: underline; text-underline-offset: 3px; }
.item-row .dek { font-size: 0.88rem; color: var(--ink-soft); margin: 0 0 4px; max-width: 70ch; }
.item-row .meta { font-size: 0.76rem; color: var(--muted); }
.badge { display: inline-block; font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.02em; padding: 2px 7px; border-radius: 3px; background: var(--green); color: #fff; margin-left: 7px; vertical-align: middle; }

.src-tag { color: var(--muted); text-decoration: none; font-weight: 600; }
.src-tag:hover { color: var(--ink); text-decoration: underline; }
.via-tag { display: inline-block; font-size: 0.64rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.03em; padding: 1px 6px; border-radius: 3px; margin-left: 6px; vertical-align: 1px; }
.via-ai { background: color-mix(in srgb, var(--signal) 16%, transparent); color: var(--signal); }
.via-rss { background: var(--line); color: var(--muted); }

.topic-tags { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 5px; }
.topic-tag { font-size: 0.68rem; font-weight: 600; color: var(--muted); background: var(--card-hover);
  border-radius: 3px; padding: 2px 7px; }

/* Cross-section tag filter — client-side only, no server round trip. */
.tag-filter { position: sticky; top: 41px; z-index: 9; background: var(--bg); border-bottom: 1px solid var(--line);
  display: flex; gap: 6px; overflow-x: auto; padding: 8px 0; margin-bottom: 4px; -ms-overflow-style: none; scrollbar-width: none; }
.tag-filter::-webkit-scrollbar { display: none; }
.tag-filter button { flex: 0 0 auto; font-family: -apple-system, sans-serif; font-weight: 600; font-size: 0.72rem;
  padding: 5px 11px; border-radius: 999px; border: 1.5px solid var(--line); background: transparent; color: var(--ink-soft);
  cursor: pointer; white-space: nowrap; }
.tag-filter button:hover { border-color: var(--ink-soft); }
.tag-filter button.active { background: var(--ink); border-color: var(--ink); color: var(--bg); }
.filter-hidden { display: none !important; }

.raw .item-row .thumb, .raw .item-row .dot { opacity: 0.7; }
.raw .item-row h3 { font-weight: 600; font-size: 0.95rem; }
.raw .item-row .thumb.block { color: var(--muted); background: var(--card-hover); }

.empty { color: var(--muted); font-size: 0.9rem; font-style: italic; padding: 10px 8px; }
.stub { padding: 18px; border: 1px dashed var(--line-strong); border-radius: 4px; color: var(--ink-soft); font-size: 0.9rem; opacity: 0.85; }

.resources { display: flex; flex-wrap: wrap; gap: 8px; padding: 4px 0 6px; }
.resources .chip { font-size: 0.82rem; font-weight: 600; text-decoration: none; color: var(--ink-soft);
  border: 1.5px solid var(--line); border-radius: 999px; padding: 6px 13px; transition: all 0.15s ease; }
.resources .chip:hover, .resources .chip:focus-visible { color: var(--ink); border-color: currentColor; }

a.show-more { display: block; margin-top: 6px; padding: 12px 8px; font-family: Archivo, sans-serif;
  font-weight: 700; font-size: 0.9rem; color: var(--muted); text-decoration: none; }
a.show-more:hover { color: var(--signal); }
.back-link { display: inline-block; margin-bottom: 18px; font-size: 0.85rem; font-weight: 600; color: var(--signal); text-decoration: none; }
.back-link:hover { text-decoration: underline; }
.day-heading { font-family: Archivo, sans-serif; font-weight: 800; font-size: 0.95rem; letter-spacing: -0.01em;
  color: var(--muted); text-transform: uppercase; margin: 30px 0 4px; padding-bottom: 6px; border-bottom: 1px solid var(--line); }

.questions { background: color-mix(in srgb, var(--signal) 8%, var(--bg)); border-radius: 4px; padding: 20px 22px; margin-top: 4px; }
.questions ol { margin: 8px 0 0; padding-left: 20px; }
.questions li { margin-bottom: 6px; }

footer { margin-top: 56px; padding-top: 16px; border-top: 1px solid var(--line); font-size: 0.76rem; color: var(--muted); }
footer .fail { color: var(--signal); }
"""


def resolve_item(curated_item: dict, item_lookup: dict[str, dict]) -> dict | None:
    raw = item_lookup.get(curated_item.get("item_id"))
    if raw is None:
        return None
    return {**raw, **curated_item}


def _local_time(item: dict, tz: ZoneInfo) -> str:
    local_dt = datetime.fromisoformat(item["published_at"]).astimezone(tz)
    return local_dt.strftime("%b %d, %I:%M %p").replace(" 0", " ")  # %-I isn't portable on Windows


def _media_html(item: dict, css_class: str, color_var: str = "signal") -> str:
    img = item.get("image_url")
    label = html.escape(item["source_name"])
    if img:
        return (f'<div class="{css_class}"><img src="{html.escape(img)}" alt="" loading="lazy" '
                f'data-fb-mode="label" data-fb-color="{color_var}" data-fb-label="{label}" '
                f'onerror="imgFallback(this)"></div>')
    return f'<div class="{css_class} block" style="background:var(--{color_var})"><span>{label}</span></div>'


def _thumb_html(item: dict, color_var: str) -> str:
    img = item.get("image_url")
    if img:
        return (f'<div class="thumb"><img src="{html.escape(img)}" alt="" loading="lazy" '
                f'data-fb-mode="dot" data-fb-color="{color_var}" onerror="imgFallback(this)"></div>')
    return f'<div class="thumb block" style="color:var(--{color_var})"><span class="dot"></span></div>'


def _meta_html(item: dict, tz: ZoneInfo, homepage_map: dict[str, str], via: str) -> str:
    # Every article carries where it came from (a real link to the publisher) and how it got
    # into the briefing: AI-curated (selected/summarized by Claude) or a raw RSS pull.
    name = html.escape(item["source_name"])
    homepage = homepage_map.get(item["source_name"])
    source = f'<a class="src-tag" href="{html.escape(homepage)}" target="_blank" rel="noopener">{name}</a>' if homepage else f'<span class="src-tag">{name}</span>'
    via_class = "via-ai" if via == "AI curated" else "via-rss"
    return (f'<div class="meta">{source}<span class="via-tag {via_class}">{via}</span> '
            f'&middot; {_local_time(item, tz)}</div>')


def _tags_html(item: dict) -> str:
    tags = item.get("tags") or []
    if not tags:
        return ""
    chips = "".join(f'<span class="topic-tag">{html.escape(t)}</span>' for t in tags)
    return f'<div class="topic-tags">{chips}</div>'


def _data_tags_attr(item: dict) -> str:
    # Always emit the attribute (even empty) so an untagged item is still a filter
    # candidate — it must be hidden when a specific tag is selected, not skipped by
    # the filter loop entirely.
    tags = item.get("tags") or []
    return f' data-tags="{html.escape("|".join(tags))}"'


def _lead_html(item: dict, tz: ZoneInfo, homepage_map: dict[str, str]) -> str:
    why = f'<p class="why">Why it matters: {html.escape(item["why_it_matters"])}</p>' if item.get("why_it_matters") else ""
    badge = ' <span class="badge">toolset</span>' if item.get("notable_for_toolset") else ""
    return f"""<div class="lead"{_data_tags_attr(item)}>
  {_media_html(item, "lead-media")}
  <h2><a class="card-link" href="{html.escape(item['source_url'])}" target="_blank" rel="noopener">{html.escape(item['headline'])}</a>{badge}</h2>
  <p class="dek">{html.escape(item['summary'])}</p>
  {why}
  {_meta_html(item, tz, homepage_map, "AI curated")}
  {_tags_html(item)}
</div>"""


def _top_item_html(item: dict, tz: ZoneInfo, homepage_map: dict[str, str]) -> str:
    badge = ' <span class="badge">toolset</span>' if item.get("notable_for_toolset") else ""
    return f"""<div class="top-item"{_data_tags_attr(item)}>
  {_media_html(item, "media")}
  <h3><a class="card-link" href="{html.escape(item['source_url'])}" target="_blank" rel="noopener">{html.escape(item['headline'])}</a>{badge}</h3>
  <p class="dek">{html.escape(item['summary'])}</p>
  {_meta_html(item, tz, homepage_map, "AI curated")}
  {_tags_html(item)}
</div>"""


def _item_row_html(item: dict, tz: ZoneInfo, color_var: str, homepage_map: dict[str, str], via: str) -> str:
    badge = ' <span class="badge">toolset</span>' if item.get("notable_for_toolset") else ""
    return f"""<div class="item-row"{_data_tags_attr(item)}>
  {_thumb_html(item, color_var)}
  <div class="body">
    <h3><a class="card-link" href="{html.escape(item['source_url'])}" target="_blank" rel="noopener">{html.escape(item['headline'])}</a>{badge}</h3>
    <p class="dek">{html.escape(item['summary'])}</p>
    {_meta_html(item, tz, homepage_map, via)}
    {_tags_html(item)}
  </div>
</div>"""


def _raw_feed_html(items: list[dict], tz: ZoneInfo, homepage_map: dict[str, str]) -> str:
    # No Claude call involved — these are the fetched RSS entries verbatim (raw_summary as-is),
    # which is what keeps this section free to refresh as often as you like. Deliberately muted
    # styling (see .raw in CSS) so it never reads as curated content.
    shown, total = items[:RSS_MAIN_PAGE_LIMIT], len(items)
    rows = "\n".join(
        _item_row_html({**it, "summary": it["raw_summary"]}, tz, "muted", homepage_map, "RSS feed") for it in shown
    )
    if not rows:
        return "<p class='empty'>No fresh items from these feeds right now.</p>"
    more = ""
    if total > len(shown):
        more = f'<a class="show-more" href="/output/popular-rss-all.html">Show all {total} articles from the last 2 weeks &rarr;</a>'
    return f'<div class="raw wire">{rows}</div>{more}'


def _section_html(key: str, curated_items: list[dict], item_lookup: dict[str, dict], tz: ZoneInfo,
                   homepage_map: dict[str, str]) -> str:
    resolved = [r for r in (resolve_item(ci, item_lookup) for ci in curated_items) if r]
    color = SECTION_COLORS.get(key, "muted")
    heading = f'<h2 class="beat beat-{color}">{SECTION_TITLES[key]}</h2>'
    if not resolved:
        return heading + "\n<p class='empty'>No qualifying items today.</p>"
    rows = "\n".join(_item_row_html(r, tz, color, homepage_map, "AI curated") for r in resolved)
    return f'{heading}\n<div class="wire">{rows}</div>'


def render_dashboard(curated: dict, item_lookup: dict[str, dict], sources_ok: list[str],
                      sources_failed: list[str], run_date: str, popular_rss: list[dict] | None = None) -> str:
    config = _config()
    tz = _local_zone(config)
    homepage_map = _homepage_map(config)
    top_signal_items = [r for r in (resolve_item(ci, item_lookup) for ci in curated.get("top_signal", [])) if r]

    if top_signal_items:
        lead_html = _lead_html(top_signal_items[0], tz, homepage_map)
        rest_html = "\n".join(_top_item_html(it, tz, homepage_map) for it in top_signal_items[1:5])
        top_block = f"{lead_html}\n<div class=\"top-row\">{rest_html}</div>" if rest_html else lead_html
    else:
        top_block = "<p class='empty'>No standout items today.</p>"

    section_keys = ("frontier_labs", "dev_tools", "enterprise_ai", "journalism", "enterprise_platforms",
                    "research_digest", "community_pulse")
    sections_html = "\n".join(
        f'<section id="{key}">{_section_html(key, curated.get(key, []), item_lookup, tz, homepage_map)}</section>'
        for key in section_keys
    )

    popular_rss_html = _raw_feed_html(popular_rss or [], tz, homepage_map)
    resources_html = _resources_html(config)

    nav_html = '<a class="nav-top" href="#top-signal">Top</a>' + "".join(
        f'<a href="#{key}" style="--nav-c:var(--{SECTION_COLORS[key]})">{SECTION_TITLES[key]}</a>'
        for key in section_keys
    ) + '<a href="#popular-rss" style="--nav-c:var(--muted)">Popular RSS</a>' \
        '<a href="#internal-data" style="--nav-c:var(--muted)">Internal Data</a>' \
        '<a href="#questions" style="--nav-c:var(--signal)">Questions</a>' \
        '<a href="#resources" style="--nav-c:var(--muted)">Resources</a>'

    questions = curated.get("questions", [])
    questions_html = "".join(f"<li>{html.escape(q)}</li>" for q in questions) or "<li class='empty'>None generated today.</li>"

    failed_html = ""
    if sources_failed:
        failed_html = " &middot; <span class='fail'>Failed: " + html.escape(", ".join(sources_failed)) + "</span>"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AI Transformation Briefing — {run_date}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}</style>
</head>
<body>
<header class="masthead">
  <h1>AI Transformation Wire</h1>
  <div class="meta-row"><span class="byline">Daily briefing &middot; {run_date}</span>{site_nav_html("today")}</div>
</header>

<nav class="wire-nav" aria-label="Sections">{nav_html}</nav>
{tag_filter_html()}

<section id="top-signal">
{top_block}
</section>

{sections_html}

<section id="popular-rss">
<h2 class="beat beat-muted">Popular AI RSS Feeds<span class="note">unfiltered — no AI curation, refreshes free</span></h2>
{popular_rss_html}
</section>

<section id="internal-data">
<h2 class="beat beat-muted">Internal Data</h2>
<div class="stub">Not yet connected. Once employer API credentials are available, this section will
pull open AI Transformation project status, Salesforce/Oracle AI feature rollouts affecting the
business, and Tableau dashboard health metrics.</div>
</section>

<section id="questions">
<h2 class="beat" style="color:var(--signal)">Questions This Raises For Your Projects</h2>
<div class="questions"><ol>{questions_html}</ol></div>
</section>

<section id="resources">
<h2 class="beat beat-muted">Resources<span class="note">every source this briefing pulls from</span></h2>
{resources_html}
</section>

<footer>
  Sources checked ({len(sources_ok)} ok, {len(sources_failed)} failed): {html.escape(", ".join(sources_ok)) or "none"}
  {failed_html}
</footer>
<script>
function imgFallback(img) {{
  var d = img.parentElement;
  d.classList.add('block');
  var s = document.createElement('span');
  if (img.dataset.fbMode === 'dot') {{
    d.style.color = 'var(--' + img.dataset.fbColor + ')';
    s.className = 'dot';
  }} else {{
    d.style.background = 'var(--' + img.dataset.fbColor + ')';
    s.textContent = img.dataset.fbLabel || '';
  }}
  d.textContent = '';
  d.appendChild(s);
}}
{TAG_FILTER_JS}
</script>
</body>
</html>"""


def render_rss_archive(items: list[dict], tz: ZoneInfo, homepage_map: dict[str, str]) -> str:
    # Full 2-week backlog behind the main page's "show more" link — grouped by local day so a
    # ~200-400 item list stays scannable instead of one undifferentiated wall of rows.
    groups: dict[str, list[dict]] = {}
    for it in items:
        day = datetime.fromisoformat(it["published_at"]).astimezone(tz).strftime("%A, %B %d")
        groups.setdefault(day, []).append(it)

    body = "".join(
        f'<h2 class="day-heading">{html.escape(day)}</h2>\n<div class="raw wire">'
        + "\n".join(_item_row_html({**it, "summary": it["raw_summary"]}, tz, "muted", homepage_map, "RSS feed") for it in day_items)
        + "</div>"
        for day, day_items in groups.items()
    ) or "<p class='empty'>No items in the last two weeks.</p>"

    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Popular AI RSS Feeds — Last 2 Weeks</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}
.tag-filter {{ top: 0; }}
</style></head>
<body>
<header class="masthead"><h1>AI Transformation Wire</h1>
<div class="meta-row"><span class="byline">Popular AI RSS Feeds &middot; last 2 weeks ({len(items)} articles)</span>{site_nav_html("popular-rss")}</div></header>
<a class="back-link" href="/">&larr; Back to today's briefing</a>
{tag_filter_html()}
{body}
<script>{TAG_FILTER_JS}</script>
</body>
</html>"""


def render_archive_index() -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Sort by the calendar date the filename encodes, not filesystem mtime — a re-run that
    # regenerates today's file must not reorder it relative to other days.
    dated_files = []
    for f in OUTPUT_DIR.glob("20*.html"):
        try:
            day = datetime.strptime(f.stem, "%Y-%m-%d").date()
        except ValueError:
            continue  # not a dated briefing file (e.g. a stray non-conforming name)
        dated_files.append((day, f))
    dated_files.sort(key=lambda pair: pair[0], reverse=True)
    files = [f for _, f in dated_files[:14]]
    items = "\n".join(
        f'<li><a href="/output/{f.name}">{f.stem}</a></li>' for f in files
    ) or "<li class='empty'>No briefings yet.</li>"
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Briefing Archive</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}
ul {{ list-style: none; padding: 0; margin: 20px 0; }}
ul li {{ border-bottom: 1px solid var(--line); }}
ul li a {{ display: block; padding: 14px 8px; text-decoration: none; font-family: Archivo, sans-serif; font-weight: 700; }}
ul li a:hover {{ color: var(--signal); }}
</style></head>
<body>
<header class="masthead"><h1>AI Transformation Wire</h1><div class="meta-row"><span class="byline">Archive &middot; last 14 days</span>{site_nav_html("archive")}</div></header>
<ul>{items}</ul>
</body>
</html>"""


def prune_old_output(days: int = 45) -> None:
    if not OUTPUT_DIR.exists():
        return
    # By the filename's date, not mtime — regenerating an old date's file (a manual re-run,
    # a backfill) must not reset its retention clock.
    cutoff = datetime.now().date()
    for f in OUTPUT_DIR.glob("20*.html"):
        try:
            day = datetime.strptime(f.stem, "%Y-%m-%d").date()
        except ValueError:
            continue
        if (cutoff - day).days > days:
            f.unlink(missing_ok=True)


def write_dashboard(curated: dict, item_lookup: dict[str, dict], sources_ok: list[str],
                     sources_failed: list[str], popular_rss: list[dict] | None = None) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prune_old_output()
    run_date = datetime.now().strftime("%Y-%m-%d")
    html_out = render_dashboard(curated, item_lookup, sources_ok, sources_failed, run_date, popular_rss)
    out_path = OUTPUT_DIR / f"{run_date}.html"
    out_path.write_text(html_out, encoding="utf-8")
    (OUTPUT_DIR / "index.html").write_text(render_archive_index(), encoding="utf-8")
    config = _config()
    (OUTPUT_DIR / "popular-rss-all.html").write_text(
        render_rss_archive(popular_rss or [], _local_zone(config), _homepage_map(config)), encoding="utf-8")
    (OUTPUT_DIR / "latest.html").write_text(html_out, encoding="utf-8")
    return out_path
