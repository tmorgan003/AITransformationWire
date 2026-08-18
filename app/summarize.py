"""Curate raw fetched items into briefing sections via one structured Claude call.

Grounding is structural, not just prompted: Claude selects items by item_id and writes
short commentary, but headline/source/url/published_at always come back from OUR fetched
data (see render.py), never from model output — so a fabricated source/URL is not possible.

Credentials are never stored by this app: the Anthropic SDK resolves ANTHROPIC_API_KEY (or
an `ant auth login` profile) from the environment. Set it once as a persistent env var —
there is no in-app settings form for it.
"""
import hashlib
import json
from pathlib import Path

import anthropic

from .tags import TAG_VOCAB

MODEL = "claude-sonnet-5"

PROMPT_PATH = Path(__file__).resolve().parent.parent / "daily_briefing_prompt.txt"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8").strip()

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
PENDING_ITEMS_PATH = OUTPUT_DIR / "_pending_items.json"
MANUAL_CURATED_PATH = OUTPUT_DIR / "_manual_curated.json"

CLIENT_TIMEOUT_SECONDS = 300


def _stable_id(source_name: str, headline: str) -> str:
    # Content-derived, not a sequential counter: fetches run concurrently (fetchers.py), so
    # fetch order — and therefore any positional id — differs between runs. A manually-curated
    # file written against one fetch snapshot must still resolve correctly the moment a later
    # run (which re-fetches) consumes it; a stable id is what makes that possible.
    return hashlib.sha256(f"{source_name}|{headline}".encode()).hexdigest()[:12]


def build_flat_items(items_by_category: dict[str, list[dict]]) -> tuple[list[dict], dict[str, dict]]:
    """Returns (flat_items, item_lookup) — the same shape sent to Claude, shared by the live
    API path and the no-key manual/dev-mode path so both curate identically-shaped input."""
    flat_items = []
    item_lookup: dict[str, dict] = {}
    for category, items in items_by_category.items():
        for it in items:
            item_id = _stable_id(it["source_name"], it["headline"])
            flat_items.append({
                "id": item_id,
                "category": category,
                "headline": it["headline"],
                "raw_summary": it["raw_summary"],
                "source_name": it["source_name"],
                "published_at": it["published_at"],
            })
            item_lookup[item_id] = it
    return flat_items, item_lookup


def write_pending_items(items_by_category: dict[str, list[dict]]) -> dict[str, dict]:
    """Dev mode, no API key: dump the fetched items for manual curation instead of calling
    Claude. Returns item_lookup so the caller can still render whatever curation eventually
    lands in MANUAL_CURATED_PATH."""
    flat_items, item_lookup = build_flat_items(items_by_category)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PENDING_ITEMS_PATH.write_text(json.dumps(flat_items, indent=2), encoding="utf-8")
    return item_lookup


def load_manual_curated(item_lookup: dict[str, dict]) -> dict | None:
    """Dev mode: if a manually-produced curation (matching _schema()) is waiting at
    MANUAL_CURATED_PATH, consume it (rename so a stale copy can't be reused silently) and
    return it. Returns None if nothing is waiting."""
    if not MANUAL_CURATED_PATH.exists():
        return None
    curated = json.loads(MANUAL_CURATED_PATH.read_text(encoding="utf-8"))
    MANUAL_CURATED_PATH.replace(MANUAL_CURATED_PATH.with_suffix(".consumed.json"))
    for key in _empty_result():
        curated.setdefault(key, [] if key != "questions" else [])
    curated["community_pulse"] = curated.get("community_pulse", [])[:5]
    curated["top_signal"] = curated.get("top_signal", [])[:5]
    curated["questions"] = curated.get("questions", [])[:3]
    return curated


def curate(items_by_category: dict[str, list[dict]]) -> tuple[dict, dict[str, dict]]:
    """Returns (curated_json, item_lookup) where item_lookup maps id -> raw item."""
    flat_items, item_lookup = build_flat_items(items_by_category)

    if not flat_items:
        return _empty_result(), item_lookup

    client = anthropic.Anthropic(timeout=CLIENT_TIMEOUT_SECONDS)
    with client.messages.stream(
        model=MODEL,
        max_tokens=15000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": "Fetched items:\n" + json.dumps(flat_items, indent=2),
        }],
        output_config={"format": {"type": "json_schema", "schema": _schema()}},
    ) as stream:
        response = stream.get_final_message()
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined the request (stop_reason=refusal, category={getattr(response.stop_details, 'category', None)})")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Claude response truncated at max_tokens before finishing the briefing JSON")
    text = next(b.text for b in response.content if b.type == "text")
    curated = json.loads(text)
    curated["community_pulse"] = curated.get("community_pulse", [])[:5]
    curated["top_signal"] = curated.get("top_signal", [])[:5]
    curated["questions"] = curated.get("questions", [])[:3]
    return curated, item_lookup


def _empty_result() -> dict:
    return {k: [] for k in ("top_signal", "frontier_labs", "dev_tools", "enterprise_ai", "journalism",
                             "enterprise_platforms", "research_digest", "community_pulse")} | {"questions": []}


def _item_block(extra: dict | None = None) -> dict:
    props = {
        "item_id": {"type": "string"},
        "summary": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string", "enum": TAG_VOCAB}},
    }
    required = ["item_id", "summary", "tags"]
    if extra:
        props.update(extra)
        required.extend(extra.keys())
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


def _item_array(extra: dict | None = None) -> dict:
    return {"type": "array", "items": _item_block(extra)}


def _schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "top_signal": _item_array({"why_it_matters": {"type": "string"}, "notable_for_toolset": {"type": "boolean"}}),
            "frontier_labs": _item_array(),
            "dev_tools": _item_array({"notable_for_toolset": {"type": "boolean"}}),
            "enterprise_ai": _item_array(),
            "journalism": _item_array(),
            "enterprise_platforms": _item_array(),
            "research_digest": _item_array(),
            "community_pulse": _item_array(),
            "questions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["top_signal", "frontier_labs", "dev_tools", "enterprise_ai", "journalism",
                     "enterprise_platforms", "research_digest", "community_pulse", "questions"],
        "additionalProperties": False,
    }
