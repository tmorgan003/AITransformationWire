"""Tiny local web app: serves the briefing, archive, popular-RSS, and a Settings page.

No framework — stdlib http.server is plenty for a single-user local tool.
"""
import html
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.render import CSS, OUTPUT_DIR, ROOT, site_nav_html  # noqa: E402

PORT = 8787


_run_lock = threading.Lock()
_run_state = {"running": False}


def _sources_html() -> str:
    try:
        config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "<p class='empty'>config.json could not be read.</p>"

    section = '<h2 class="beat beat-muted">Popular AI RSS Feeds<span class="note">{n} feeds</span></h2>'.format(
        n=len(config.get("popular_rss_feeds", [])))
    section += "<div class='resources'>" + "".join(
        f'<a class="chip" href="{html.escape(f.get("homepage", f["url"]))}" target="_blank" rel="noopener">{html.escape(f["name"])}</a>'
        for f in config.get("popular_rss_feeds", [])
    ) + "</div>"

    for key, feeds in config.get("sources", {}).items():
        section += f'<h2 class="beat beat-muted">{html.escape(key.replace("_", " ").title())}<span class="note">{len(feeds)} feeds</span></h2>'
        section += "<div class='resources'>" + "".join(
            f'<a class="chip" href="{html.escape(f.get("homepage", f["url"]))}" target="_blank" rel="noopener">{html.escape(f["name"])}</a>'
            for f in feeds
        ) + "</div>"

    return section


def _settings_page(message: str = "", error: bool = False) -> str:
    key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
    color = "var(--signal)" if error else "var(--green)"
    banner = f"<p style='color:{color};font-weight:600'>{html.escape(message)}</p>" if message else ""
    if _run_state["running"]:
        banner += "<p style='color:var(--amber);font-weight:600'>A briefing run is currently in progress — reload this page in a bit.</p>"

    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Settings — AI Transformation Wire</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}
.settings-form {{ max-width: 480px; margin: 18px 0 36px; }}
.settings-form label {{ display: block; font-weight: 600; font-size: 0.88rem; margin-bottom: 6px; }}
.settings-form input {{ width: 100%; padding: 10px 12px; font-size: 0.95rem; border: 1.5px solid var(--line);
  border-radius: 4px; background: var(--bg); color: var(--ink); margin-bottom: 10px; }}
.settings-form button {{ font-family: Archivo, sans-serif; font-weight: 800; font-size: 0.85rem; letter-spacing: -0.01em;
  padding: 10px 20px; border-radius: 4px; border: none; background: var(--ink); color: var(--bg); cursor: pointer; margin-right: 10px; }}
.settings-form button:hover {{ background: var(--signal); }}
.settings-form.run button {{ background: var(--signal); }}
.key-status {{ font-size: 0.88rem; color: var(--ink-soft); margin-bottom: 4px; }}
</style></head>
<body>
<header class="masthead"><h1>AI Transformation Wire</h1>
<div class="meta-row"><span class="byline">Settings</span>{site_nav_html("settings")}</div></header>

{banner}

<h2 class="beat" style="color:var(--signal)">Run the Briefing</h2>
<p class="key-status">Anthropic API key: <strong>{"found in environment" if key_set else "NOT SET — set ANTHROPIC_API_KEY as a persistent environment variable before running"}</strong></p>
<p class="key-status">Fetches every source below, curates the daily sections with Claude, and refreshes the dashboard. Takes a minute or two. There is no key form here by design — credentials live only in the environment, never in a file this app writes.</p>
<form class="settings-form run" method="post" action="/run-now">
  <button type="submit">Run briefing now</button>
</form>

<h2 class="beat beat-muted">Sources</h2>
<p class="key-status">Every feed configured in config.json, grouped the same way the daily run groups them. Add or remove sources by editing that file directly.</p>
{_sources_html()}

</body>
</html>"""


def _run_in_background() -> None:
    with _run_lock:
        _run_state["running"] = True
        try:
            from app import run as run_module
            run_module.main()
        finally:
            _run_state["running"] = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter console
        pass

    def _send_html(self, body: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def _send_file(self, path: Path) -> None:
        if not path.exists():
            self._send_html("<h1>Not found</h1><p><a href='/settings'>Run the briefing first</a>.</p>", 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(path.read_bytes())

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_file(OUTPUT_DIR / "latest.html")
        elif parsed.path == "/archive":
            self._send_file(OUTPUT_DIR / "index.html")
        elif parsed.path == "/settings":
            self._send_html(_settings_page())
        elif parsed.path.startswith("/output/"):
            name = os.path.basename(parsed.path[len("/output/"):])  # no traversal
            self._send_file(OUTPUT_DIR / name)
        elif parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self._send_html("<h1>404</h1>", 404)

    def do_POST(self):
        if self.path == "/run-now":
            if _run_state["running"]:
                self._send_html(_settings_page("A run is already in progress.", error=True))
                return
            threading.Thread(target=_run_in_background, daemon=True).start()
            self._send_html(_settings_page("Briefing run started in the background — this can take a minute or two. Reload the dashboard when it's done."))
        else:
            self._send_html("<h1>404</h1>", 404)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Serving on http://127.0.0.1:{PORT}  (dashboard: /, settings: /settings, archive: /archive)")
    server.serve_forever()


if __name__ == "__main__":
    main()
