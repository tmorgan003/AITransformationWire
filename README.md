# AI Transformation Wire

A locally-hosted daily briefing dashboard for an AI Transformation Office. It fetches AI/tech news from ~100 RSS feeds, curates the signal into themed sections with Claude, and renders it as a static, editorial-style HTML dashboard — no cloud hosting, no email delivery, no database server. Everything runs on your machine.

## What it does

- **Fetches** every configured RSS/Atom feed concurrently, going back up to 5 days for the daily briefing (Popular RSS keeps its own 14-day window). The raw fetch is cached (see [Fetch caching](#fetch-caching)) so re-running the pipeline after a code change doesn't re-hit every feed.
- **Curates** the fetched items into a daily briefing with one structured call to Claude — sorted into `top_signal`, `frontier_labs`, `dev_tools`, `enterprise_ai`, `journalism`, `enterprise_platforms`, `research_digest`, and `community_pulse`, plus a handful of discussion questions.
- **Tags** every item (`Claude Code`, `Devin`, `Windsurf`, `Agents`, `LLMs`, `Coding Tools`, `Enterprise`, `Funding`, `Safety & Policy`, `Research`, `Open Source`, `Robotics`, `Hardware`, `Data & Infra`) so the dashboard can be filtered client-side.
- **Renders** a wire-service-style dashboard (red masthead, Archivo type, color-coded content "beats") with a sticky tag filter, per-article source/via tags, and a two-week archive.
- Also runs a **Popular AI RSS Feeds** section that updates purely mechanically (keyword-tagged, no Claude call) so refreshing it never costs anything.

## Requirements

- Python 3.11+ (tested on 3.14)
- Windows, macOS, or Linux — no OS-specific dependencies beyond `tzdata` (installed automatically via `requirements.txt`, needed on Windows since it has no OS tz database)
- An [Anthropic API key](https://console.anthropic.com/) for live curation (optional — see [Dev mode](#dev-mode-no-api-key) below)

## Setup

```bash
pip install -r requirements.txt
```

Set your API key as a **persistent environment variable** — the app never stores it in a file, and there is no in-app settings form for it by design.

**Windows (PowerShell):**
```powershell
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
```
(Restart your terminal after setting it.)

**macOS/Linux:** add to your shell profile:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Running it

**Run the briefing pipeline** (fetch → curate → render):
```bash
python -m app.run
```
This writes `output/{today's date}.html`, updates `output/index.html` (archive), `output/latest.html` (today's briefing), and `output/popular-rss-all.html` (2-week RSS backlog).

**Start the local web server:**
```bash
python -m app.server
```
Then open **http://127.0.0.1:8787**:

| Route | Page |
|---|---|
| `/` | Today's briefing (latest run) |
| `/archive` | Index of past briefings, sorted by the date each one covers |
| `/output/popular-rss-all.html` | Full 2-week Popular RSS backlog |
| `/settings` | API key status, manual "run briefing now" button, full source list |

The Settings page's "Run briefing now" button runs `app.run` in a background thread — no need to touch the CLI day-to-day.

### Scheduling it (Windows Task Scheduler)

`run_dashboard.bat` runs the pipeline headless — point a scheduled task at it for an unattended daily refresh (e.g. 4am):

```powershell
$action = New-ScheduledTaskAction -Execute "C:\path\to\run_dashboard.bat"
$trigger = New-ScheduledTaskTrigger -Daily -At 4am
Register-ScheduledTask -TaskName "AITransformationDailyBriefing" -Action $action -Trigger $trigger
```

## Dev mode (no API key)

If `ANTHROPIC_API_KEY` isn't set, `app.run` never calls the Claude API. Instead it:

1. Fetches everything as normal and writes the flat item list to `output/_pending_items.json`.
2. Checks for `output/_manual_curated.json` — if present (matching the same schema Claude would return), it's consumed (renamed to `_manual_curated.consumed.json`) and rendered exactly like a live run.
3. If neither exists yet, it renders an empty briefing (Popular RSS section still populates — that path never touches Claude either way).

This lets you develop and preview the full UI — layout, tagging, filtering — without spending anything on API calls, by hand-authoring (or having an agent author) a curated JSON file that follows the schema in `app/summarize.py`'s `_schema()`.

## Configuration

Everything lives in **`config.json`** at the project root — no code changes needed to add, remove, or re-tier a source:

```json
{
  "timezone": "America/Chicago",
  "freshness_hours": 336,
  "sections": ["top_signal", "frontier_labs", "dev_tools", "enterprise_ai", "journalism", "enterprise_platforms", "research_digest", "community_pulse"],
  "popular_rss_feeds": [ { "name": "...", "url": "...", "homepage": "..." } ],
  "sources": {
    "frontier_labs": [ { "name": "...", "url": "...", "homepage": "..." } ],
    "dev_tools": [ ... ],
    "enterprise_ai": [ ... ],
    "journalism": [ ... ],
    "enterprise_platforms": [ ... ],
    "research_digest": [ ... ],
    "community_pulse": [ ... ]
  }
}
```

- `freshness_hours` — how far back the **daily briefing** pipeline (Claude-curated sections) looks for fresh items. Currently 120 hours (5 days).
- The **Popular RSS** section uses its own fixed 14-day window (`fetchers.MAX_ENTRY_AGE_DAYS`), independent of `freshness_hours`.

## Fetch caching

Fetching ~100 RSS sources is the slow, network-bound part of a run. `app.run` caches the raw fetch result to `cache/fetch_cache.json` and reuses it on the next run instead of re-fetching, as long as the cache is younger than `freshness_hours` — once it's older than that, it can no longer contain anything within the briefing's own freshness window anyway, so a live re-fetch happens automatically.

This means:
- Iterating on `render.py`, `summarize.py`, the prompt, or anything else code-side re-runs instantly against the same cached data — no network calls.
- The pipeline naturally re-fetches on its own roughly every `freshness_hours` (5 days by default), rather than needing a daily schedule.
- To force a live re-fetch sooner (e.g. you know new sources were added to `config.json`), run `python -m app.run --refresh` or set `FORCE_REFRESH=1`.

`cache/` is gitignored — it's local, disposable, and rebuilt automatically.
- Every source entry needs a `homepage` — it's used both for the clickable per-article source tag and the Settings/Resources source listing.
- Sites without a working native RSS feed fall back to a scoped Google News query (`...+when:14d&hl=en-US&gl=US&ceid=US:en`).

The system prompt sent to Claude lives in **`daily_briefing_prompt.txt`** at the project root — edit it directly, no code change or redeploy needed.

## Architecture

```
app/
  fetchers.py    concurrent RSS/Atom fetch (ThreadPoolExecutor), thumbnail extraction, keyword tagging
  tags.py        shared tag vocabulary + keyword-matching heuristic (used by fetchers.py for the AI-free Popular RSS tags)
  summarize.py   builds the flat item list, calls Claude with a JSON-schema-constrained structured output, dev-mode split-phase curation
  store.py       SQLite (db/dashboard.db) — cross-day dedup, run history
  render.py      renders all HTML pages: today, archive index, popular-rss archive, shared CSS/nav
  run.py         orchestrator: fetch -> filter -> dedup -> summarize -> render -> log (one failure never blocks a briefing from shipping)
  server.py      stdlib http.server app: serves the dashboard + settings page, runs briefings on demand
config.json                all fetch sources + timing config
daily_briefing_prompt.txt  the literal Claude system prompt (single source of truth)
run_dashboard.bat          entry point for Task Scheduler
db/, logs/, output/        generated at runtime — gitignored
```

**Design notes:**
- **Stable item IDs.** Fetches run concurrently, so completion order isn't deterministic between runs. Item IDs are a content hash (`sha256(source_name + headline)`), not a positional counter — so a curated file (dev-mode or otherwise) always resolves to the right article even after a re-fetch.
- **Grounding is structural.** Claude selects items by `item_id` and writes commentary; headline/source/URL always come from our own fetched data in `render.py`, never from model output — a fabricated source or URL isn't possible.
- **No client-side dependencies.** The dashboard's tag filter is a small inline `<script>`; there's no build step, bundler, or JS framework anywhere in the project.

## Security notes

- `ANTHROPIC_API_KEY` is read from the environment only (`anthropic.Anthropic()` with no explicit key). There is no settings file, form, or code path that writes it to disk.
- `.gitignore` excludes `db/`, `output/`, `logs/`, and local artifacts — only source code and `config.json` (which contains no secrets, only public feed URLs) are meant to be committed.
