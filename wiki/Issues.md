# Issues

[Home](Home.md) · [Architecture](Architecture.md)

Flagged by static pattern matching. 1 active finding(s).

| Severity | Category | File | Line | Summary | Suggested Fix | CWE / OWASP |
|---|---|---|---|---|---|---|
| Low | Possible Dead Code | `app/server.py` | 1 | No other scanned file resolves a relative import to this file (real path resolution, including index.js/__init__.py fallback — dynamic imports or consumers outside this repo would not be detected). | Confirm whether this file is still used (check dynamic imports, build tooling, or external consumers) and remove it if not. | — |