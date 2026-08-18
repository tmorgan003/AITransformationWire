# Components: app

[Home](../Home.md) · [Architecture](../Architecture.md)

## `app/fetchers.py`

100 lines.

**Dependencies (imports):** `calendar`, `re`, `concurrent.futures`, `datetime`, `feedparser`, `requests`, `.`

**Functions/Methods:**

| Name | Parameters | Line |
|---|---|---|
| `fetch_feed` | `name: str, url: str` | 16 |
| `_entry_image` | `entry` | 50 |
| `_entry_datetime` | `entry` | 63 |
| `_clean_summary` | `entry` | 71 |
| `fetch_all` | `sources_by_category: dict[str, list[dict]]` | 79 |

## `app/render.py`

613 lines.

**Dependencies (imports):** `html`, `json`, `datetime`, `pathlib`, `zoneinfo`, `.tags`

**Functions/Methods:**

| Name | Parameters | Line |
|---|---|---|
| `tag_filter_html` | `—` | 41 |
| `site_nav_html` | `active: str` | 65 |
| `_config` | `—` | 73 |
| `_local_zone` | `config: dict | None = None` | 80 |
| `_homepage_map` | `config: dict` | 85 |
| `_resources_html` | `config: dict` | 97 |
| `resolve_item` | `curated_item: dict, item_lookup: dict[int, dict]` | 302 |
| `_local_time` | `item: dict, tz: ZoneInfo` | 309 |
| `_media_html` | `item: dict, css_class: str, color_var: str = "signal"` | 314 |
| `_thumb_html` | `item: dict, color_var: str` | 324 |
| `_meta_html` | `item: dict, tz: ZoneInfo, homepage_map: dict[str, str], via: str` | 332 |
| `_tags_html` | `item: dict` | 343 |
| `_data_tags_attr` | `item: dict` | 351 |
| `_lead_html` | `item: dict, tz: ZoneInfo, homepage_map: dict[str, str]` | 359 |
| `_top_item_html` | `item: dict, tz: ZoneInfo, homepage_map: dict[str, str]` | 372 |
| `_item_row_html` | `item: dict, tz: ZoneInfo, color_var: str, homepage_map: dict[str, str], via: str` | 383 |
| `_raw_feed_html` | `items: list[dict], tz: ZoneInfo, homepage_map: dict[str, str]` | 396 |
| `_section_html` | `key: str, curated_items: list[dict], item_lookup: dict[int, dict], tz: ZoneInfo,
                   homepage_map: dict[str, str]` | 412 |
| `render_dashboard` | `curated: dict, item_lookup: dict[int, dict], sources_ok: list[str],
                      sources_failed: list[str], run_date: str, popular_rss: list[dict] | None = None` | 423 |
| `render_rss_archive` | `items: list[dict], tz: ZoneInfo, homepage_map: dict[str, str]` | 532 |
| `render_archive_index` | `—` | 565 |
| `prune_old_output` | `days: int = 45` | 588 |
| `write_dashboard` | `curated: dict, item_lookup: dict[int, dict], sources_ok: list[str],
                     sources_failed: list[str], popular_rss: list[dict] | None = None` | 597 |

## `app/run.py`

128 lines.

**Dependencies (imports):** `json`, `os`, `sys`, `traceback`, `datetime`, `pathlib`, `app`

**Functions/Methods:**

| Name | Parameters | Line |
|---|---|---|
| `_log` | `line: str` | 15 |
| `main` | `—` | 21 |
| `_run` | `—` | 36 |

## `app/server.py`

156 lines.

**Dependencies (imports):** `html`, `json`, `os`, `sys`, `threading`, `http.server`, `pathlib`, `urllib.parse`, `app.render`, `app`

**Classes:**

- `Handler` extends `BaseHTTPRequestHandler` — line 99

**Functions/Methods:**

| Name | Parameters | Line |
|---|---|---|
| `_sources_html` | `—` | 23 |
| `_settings_page` | `message: str = "", error: bool = False` | 46 |
| `_run_in_background` | `—` | 89 |
| `log_message` | `self, fmt, *args` | 102 |
| `_send_html` | `self, body: str, status: int = 200` | 104 |
| `_send_file` | `self, path: Path` | 110 |
| `do_GET` | `self` | 119 |
| `do_POST` | `self` | 136 |
| `main` | `—` | 146 |

## `app/store.py`

97 lines.

**Dependencies (imports):** `hashlib`, `json`, `re`, `sqlite3`, `datetime`, `pathlib`

**Functions/Methods:**

| Name | Parameters | Line |
|---|---|---|
| `connect` | `—` | 31 |
| `normalize_headline` | `headline: str` | 38 |
| `headline_hash` | `headline: str` | 47 |
| `seen_hashes` | `conn: sqlite3.Connection, lookback_days: int = 4` | 51 |
| `mark_shown` | `conn: sqlite3.Connection, items: list[dict]` | 57 |
| `prune_old` | `conn: sqlite3.Connection, days: int = 45` | 73 |
| `start_run` | `conn: sqlite3.Connection` | 80 |
| `finish_run` | `conn: sqlite3.Connection, run_id: int, sources_ok: list[str], sources_failed: list[str],
               item_count: int, errors: list[str]` | 87 |

## `app/summarize.py`

152 lines.

**Dependencies (imports):** `json`, `pathlib`, `anthropic`, `.tags`

**Functions/Methods:**

| Name | Parameters | Line |
|---|---|---|
| `build_flat_items` | `items_by_category: dict[str, list[dict]]` | 28 |
| `write_pending_items` | `items_by_category: dict[str, list[dict]]` | 49 |
| `load_manual_curated` | `item_lookup: dict[int, dict]` | 59 |
| `curate` | `items_by_category: dict[str, list[dict]]` | 75 |
| `_empty_result` | `—` | 106 |
| `_item_block` | `extra: dict | None = None` | 111 |
| `_item_array` | `extra: dict | None = None` | 129 |
| `_schema` | `—` | 133 |

## `app/tags.py`

42 lines.

**Dependencies (imports):** `re`

**Functions/Methods:**

| Name | Parameters | Line |
|---|---|---|
| `keyword_tags` | `headline: str, summary: str, limit: int = 3` | 36 |

## `app/__init__.py`

1 lines.

_No functions or classes extracted from this file (may be config, types-only, or use a pattern this scanner doesn't recognize)._

---
_Purpose and side-effect notes above are inferred from imports/calls found in source (e.g. db/network client usage implies a data or network side effect). Confirm against the actual code for anything critical._