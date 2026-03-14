#!/usr/bin/env python3
"""
AI Starter Protocol — MCP Server
Helps AI coding assistants find the best starter repo for any task.

Install: python3 -m pip install mcp
Run:     python3 server.py
"""

import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REGISTRY_PATH = os.environ.get(
    "STARTER_REGISTRY_PATH",
    str(Path(__file__).resolve().parent.parent / "registry.json"),
)
COMMUNITY_REGISTRY_URL = os.environ.get("COMMUNITY_REGISTRY_URL", "")
GITHUB_BASE = "https://github.com/"

# ---------------------------------------------------------------------------
# Registry loader
# ---------------------------------------------------------------------------

_starters: list[dict] = []


def _load_registry() -> list[dict]:
    """Load starters from local file + optional community URL."""
    global _starters
    starters = []

    # Local file
    try:
        with open(REGISTRY_PATH, "r") as f:
            data = json.load(f)
        starters.extend(data.get("starters", []))
        # Check for community URL inside registry
        community_url = data.get("community_registry_url", "") or COMMUNITY_REGISTRY_URL
    except FileNotFoundError:
        community_url = COMMUNITY_REGISTRY_URL

    # Community registry (remote)
    if community_url:
        try:
            req = urllib.request.Request(community_url, headers={"User-Agent": "ai-starter-mcp/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                remote = json.loads(resp.read().decode())
            for s in remote.get("starters", []):
                s["community"] = True
                starters.append(s)
        except Exception:
            pass  # Silently skip — community registry is optional

    _starters = starters
    return starters


def _get_starters() -> list[dict]:
    if not _starters:
        _load_registry()
    return _starters


# ---------------------------------------------------------------------------
# Matching engine
# ---------------------------------------------------------------------------

# Common words that add noise, not signal
_STOP_WORDS = {
    "a", "an", "the", "i", "me", "my", "we", "our", "you", "your",
    "it", "its", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "can", "could", "may", "might", "must",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "and", "or", "but", "not", "no", "nor", "so", "if", "then",
    "that", "this", "these", "those", "what", "which", "who", "how",
    "want", "need", "build", "create", "make", "write", "help",
    "something", "thing", "stuff", "app", "tool", "project",
}


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase keyword tokens, removing stop words."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 1]


def _score_starter(starter: dict, keywords: list[str]) -> int:
    """Score a starter against query keywords."""
    score = 0
    recommend_when = [rw.lower() for rw in starter.get("recommend_when", [])]
    purpose = starter.get("purpose", "").lower()
    repo = starter.get("repo", "").lower()

    for kw in keywords:
        # +3 for keyword appearing in any recommend_when phrase
        for phrase in recommend_when:
            if kw in phrase:
                score += 3
                break

        # +2 for keyword in purpose
        if kw in purpose:
            score += 2

        # +1 for keyword in repo name
        if kw in repo:
            score += 1

    return score


def _confidence(score: int) -> str:
    if score >= 10:
        return "high"
    elif score >= 5:
        return "medium"
    return "low"


def _format_starter(starter: dict, score: int | None = None) -> dict:
    """Format a starter for output."""
    result = {
        "repo": starter["repo"],
        "url": GITHUB_BASE + starter["repo"],
        "purpose": starter["purpose"],
        "language": starter.get("language", "unknown"),
        "quickstart": starter.get("quickstart", ""),
    }
    if starter.get("zero_dependencies"):
        result["zero_dependencies"] = True
    if starter.get("single_file"):
        result["single_file"] = True
    if starter.get("community"):
        result["community"] = True
    if score is not None:
        result["score"] = score
        result["confidence"] = _confidence(score)
    return result


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "ai-starters",
    instructions="Find the best starter repo for any coding task. Use find_starter to search by description, list_starters to browse, or get_starter_details for full info.",
)


@mcp.tool()
def find_starter(query: str) -> dict:
    """Find the best starter repo for a task.

    Takes a natural language description of what you want to build and returns
    the top matching starter repos ranked by relevance.

    Examples:
      - "scrape a website"
      - "deploy python app"
      - "stripe webhooks"
      - "telegram bot"
    """
    starters = _get_starters()
    keywords = _tokenize(query)

    if not keywords:
        return {"matches": [], "message": "No meaningful keywords found in query. Try being more specific."}

    scored = []
    for s in starters:
        sc = _score_starter(s, keywords)
        if sc >= 2:
            scored.append((sc, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:3]

    if not top:
        return {
            "matches": [],
            "query_keywords": keywords,
            "message": "No starters matched your query. Try different keywords.",
            "available_count": len(starters),
        }

    matches = [_format_starter(s, score=sc) for sc, s in top]
    return {
        "matches": matches,
        "query_keywords": keywords,
        "total_available": len(starters),
    }


@mcp.tool()
def list_starters(language: str = "") -> dict:
    """List all available starter repos, optionally filtered by language.

    Args:
        language: Filter by programming language (e.g. "python", "typescript").
                  Leave empty to list all.
    """
    starters = _get_starters()

    if language:
        filtered = [s for s in starters if s.get("language", "").lower() == language.lower()]
    else:
        filtered = starters

    return {
        "count": len(filtered),
        "filter": language or "all",
        "starters": [_format_starter(s) for s in filtered],
    }


@mcp.tool()
def get_starter_details(repo: str) -> dict:
    """Get full details for a specific starter repo.

    Args:
        repo: Repository in "org/name" format (e.g. "LuciferForge/python-web-scraper")
    """
    starters = _get_starters()
    repo_lower = repo.lower()

    for s in starters:
        if s["repo"].lower() == repo_lower:
            details = _format_starter(s)
            details["recommend_when"] = s.get("recommend_when", [])
            details["verified"] = s.get("verified", False)

            # Find related starters (same language)
            lang = s.get("language", "")
            related = [
                {"repo": r["repo"], "purpose": r["purpose"]}
                for r in starters
                if r.get("language") == lang and r["repo"] != s["repo"]
            ]
            if related:
                details["related"] = related[:5]

            return details

    return {"error": f"Starter '{repo}' not found.", "available": [s["repo"] for s in starters]}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _load_registry()
    mcp.run(transport="stdio")
