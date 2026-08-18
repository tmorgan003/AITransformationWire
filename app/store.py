"""SQLite dedup + run history for the daily briefing."""
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "dashboard.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE NOT NULL,
    headline TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    published_at TEXT NOT NULL,
    shown_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    sources_ok TEXT,
    sources_failed TEXT,
    item_count INTEGER,
    errors TEXT
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def normalize_headline(headline: str) -> str:
    # ponytail: exact-normalized-match dedup, misses paraphrased duplicate headlines across outlets.
    # Upgrade to fuzzy/embedding similarity if cross-outlet paraphrase dupes become a real problem.
    text = headline.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def headline_hash(headline: str) -> str:
    return hashlib.sha256(normalize_headline(headline).encode()).hexdigest()


def seen_hashes(conn: sqlite3.Connection, lookback_days: int = 4) -> set[str]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
    rows = conn.execute("SELECT hash FROM items WHERE shown_at >= ?", (cutoff,)).fetchall()
    return {r[0] for r in rows}


def mark_shown(conn: sqlite3.Connection, items: list[dict]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    # upsert, not INSERT OR IGNORE: a headline that resurfaces after the lookback window must get
    # a fresh shown_at, or its dedup timestamp stays frozen at the original date forever.
    conn.executemany(
        "INSERT INTO items (hash, headline, source_name, source_url, published_at, shown_at) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(hash) DO UPDATE SET shown_at=excluded.shown_at",
        [
            (headline_hash(it["headline"]), it["headline"], it["source_name"], it["source_url"], it["published_at"], now)
            for it in items
        ],
    )
    conn.commit()


def prune_old(conn: sqlite3.Connection, days: int = 45) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn.execute("DELETE FROM items WHERE shown_at < ?", (cutoff,))
    conn.execute("DELETE FROM runs WHERE started_at < ?", (cutoff,))
    conn.commit()


def start_run(conn: sqlite3.Connection) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute("INSERT INTO runs (started_at) VALUES (?)", (now,))
    conn.commit()
    return cur.lastrowid


def finish_run(conn: sqlite3.Connection, run_id: int, sources_ok: list[str], sources_failed: list[str],
               item_count: int, errors: list[str]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE runs SET finished_at=?, sources_ok=?, sources_failed=?, item_count=?, errors=? WHERE id=?",
        (now, json.dumps(sources_ok), json.dumps(sources_failed), item_count, json.dumps(errors), run_id),
    )
    conn.commit()
