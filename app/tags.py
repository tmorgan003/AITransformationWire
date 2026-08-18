"""Shared topic-tag vocabulary, used by both the Claude curation schema (summarize.py) and the
free keyword tagger below for the no-AI Popular RSS section — same vocabulary, so filtering
works the same way across curated and raw content.
"""
import re

# Claude Code / Devin / Windsurf lead the list on purpose — they're this role's own toolset
# (see daily_briefing_prompt.txt), so they get priority placement in the filter bar and
# priority survival when keyword_tags() truncates to `limit`.
TAG_VOCAB = [
    "Claude Code", "Devin", "Windsurf",
    "Agents", "LLMs", "Coding Tools", "Enterprise", "Funding", "Safety & Policy",
    "Research", "Open Source", "Robotics", "Hardware", "Data & Infra",
]

# ponytail: keyword/substring heuristic, not NLP — misses paraphrased subjects a real
# classifier would catch. Good enough for a free filter on RSS headlines; upgrade to an
# embedding-based tagger if mis-tags become a real problem. Dict order = priority order:
# earlier entries survive keyword_tags()'s `[:limit]` truncation first.
_KEYWORDS: dict[str, list[str]] = {
    "Claude Code": ["claude code"],
    "Devin": ["devin", "cognition labs", "cognition ai"],
    "Windsurf": ["windsurf", "codeium"],
    "Agents": ["agent", "agentic", "autonomous"],
    "LLMs": ["llm", "large language model", "gpt", "claude", "gemini", "llama", "chatbot", "transformer"],
    "Coding Tools": ["code", "coding", "developer", "ide", "copilot", "cursor"],
    "Enterprise": ["enterprise", "business", "workforce", "salesforce", "oracle", "servicenow", "b2b"],
    "Funding": ["funding", "raises", "valuation", "series a", "series b", "series c", "acquisition", "acquires", "ipo", "investment"],
    "Safety & Policy": ["safety", "regulation", "policy", "governance", "risk", "ethics", "compliance", "lawsuit"],
    "Research": ["paper", "research", "benchmark", "study", "arxiv", "reasoning"],
    "Open Source": ["open source", "open-source", "open weight"],
    "Robotics": ["robot", "robotics", "autonomous vehicle", "self-driving"],
    "Hardware": ["chip", "gpu", "nvidia", "semiconductor", "hardware", "data center", "datacenter"],
    "Data & Infra": ["data pipeline", "infrastructure", "cloud", "database", "vector store", "kubernetes"],
}


def keyword_tags(headline: str, summary: str, limit: int = 3) -> list[str]:
    text = f"{headline} {summary}".lower()
    matched = [tag for tag, words in _KEYWORDS.items() if any(re.search(re.escape(w), text) for w in words)]
    return matched[:limit]
