#!/usr/bin/env python3
"""
scanner.py — Research tool for the AI Starter Protocol.

Analyzes what AI models build most frequently by examining:
1. GitHub trending repos (what people star = what they were looking for)
2. GitHub search gaps (high-demand queries with low-quality results)
3. Our registry coverage (what we have vs what's missing)
4. Competitor analysis (who else has .ai-starter.json?)

Usage:
    python3 scanner.py gaps           # Find high-demand empty search lanes
    python3 scanner.py trending       # What's trending in starter/template repos
    python3 scanner.py audit          # Audit our registry coverage
    python3 scanner.py compete QUERY  # Check competition for a search query
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

GH = "/usr/local/bin/gh"
REGISTRY = Path(__file__).parent / "registry.json"

# These are the queries AI would use when searching for solutions.
# Ranked by estimated frequency (what AI builds most → least).
DEMAND_QUERIES = [
    # Tier 1: Written from scratch millions of times daily
    {"query": "python web scraper", "category": "scraper", "frequency": "very_high"},
    {"query": "web scraper no dependencies", "category": "scraper", "frequency": "very_high"},
    {"query": "telegram bot python", "category": "bot", "frequency": "very_high"},
    {"query": "discord bot python", "category": "bot", "frequency": "very_high"},
    {"query": "telegram bot AI chatbot", "category": "bot", "frequency": "high"},
    {"query": "python CLI tool template", "category": "cli", "frequency": "high"},
    {"query": "REST API client python", "category": "api", "frequency": "high"},
    {"query": "fastapi starter template", "category": "web", "frequency": "high"},
    {"query": "landing page template HTML", "category": "web", "frequency": "high"},
    {"query": "chrome extension starter manifest v3", "category": "extension", "frequency": "high"},

    # Tier 2: Common but more variation
    {"query": "python data pipeline ETL", "category": "data", "frequency": "medium"},
    {"query": "JWT authentication python", "category": "auth", "frequency": "medium"},
    {"query": "stripe webhook handler python", "category": "payment", "frequency": "medium"},
    {"query": "email sender python SMTP", "category": "automation", "frequency": "medium"},
    {"query": "cron job scheduler python", "category": "automation", "frequency": "medium"},
    {"query": "CSV to database python", "category": "data", "frequency": "medium"},
    {"query": "python logging setup template", "category": "utility", "frequency": "medium"},
    {"query": "dockerfile python template", "category": "devops", "frequency": "medium"},
    {"query": "github actions workflow template", "category": "devops", "frequency": "medium"},
    {"query": "slack bot python", "category": "bot", "frequency": "medium"},

    # Tier 3: Niche but high-value
    {"query": "MCP server python template", "category": "ai", "frequency": "medium"},
    {"query": "AI agent starter python", "category": "ai", "frequency": "high"},
    {"query": "RAG pipeline python starter", "category": "ai", "frequency": "medium"},
    {"query": "oauth2 python minimal", "category": "auth", "frequency": "medium"},
    {"query": "websocket server python", "category": "web", "frequency": "medium"},
    {"query": "crypto trading bot python", "category": "trading", "frequency": "medium"},
    {"query": "twitter bot python", "category": "bot", "frequency": "medium"},
    {"query": "notion API python", "category": "api", "frequency": "low"},
    {"query": "supabase python starter", "category": "web", "frequency": "low"},
    {"query": "playwright scraper python", "category": "scraper", "frequency": "medium"},
]


def gh_search(query, limit=5):
    """Search GitHub repos and return results with quality signals."""
    try:
        cmd = f'{GH} search repos "{query}" --limit {limit} --json name,owner,stargazersCount,description,updatedAt'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        print(f"  Search error: {e}", file=sys.stderr)
    return []


def analyze_gap(query_info):
    """Analyze a search query for gap opportunity."""
    query = query_info["query"]
    results = gh_search(query, limit=10)

    if not results:
        return {
            "query": query,
            "category": query_info["category"],
            "frequency": query_info["frequency"],
            "gap_score": 10,  # Empty lane = maximum opportunity
            "top_stars": 0,
            "avg_stars": 0,
            "results": 0,
            "verdict": "EMPTY LANE — zero results",
        }

    stars = [r.get("stargazersCount", 0) for r in results]
    top_stars = max(stars)
    avg_stars = sum(stars) / len(stars)

    # Freshness check
    stale = sum(1 for r in results if r.get("updatedAt", "")[:4] < "2025")
    stale_pct = stale / len(results)

    # Quality check: do descriptions actually match?
    relevant = sum(1 for r in results if r.get("description") and
                   any(word in (r.get("description", "").lower()) for word in query.lower().split()))
    relevance = relevant / len(results)

    # Gap score: higher = bigger opportunity
    # High demand + low quality results = high gap score
    freq_weight = {"very_high": 3, "high": 2, "medium": 1, "low": 0.5}
    demand = freq_weight.get(query_info["frequency"], 1)

    if top_stars > 500:
        competition = 0.2  # Hard to compete
    elif top_stars > 100:
        competition = 0.5  # Moderate
    elif top_stars > 20:
        competition = 0.8  # Weak competition
    else:
        competition = 1.0  # Near empty

    freshness_bonus = stale_pct * 0.5  # Stale results = opportunity
    relevance_penalty = relevance * 0.3  # Relevant results = less opportunity

    gap_score = demand * competition * (1 + freshness_bonus) * (1 - relevance_penalty)
    gap_score = round(min(gap_score, 10), 1)

    if gap_score > 2:
        verdict = "BUILD — high opportunity"
    elif gap_score > 1:
        verdict = "CONSIDER — moderate opportunity"
    else:
        verdict = "SKIP — crowded lane"

    return {
        "query": query,
        "category": query_info["category"],
        "frequency": query_info["frequency"],
        "gap_score": gap_score,
        "top_stars": top_stars,
        "avg_stars": round(avg_stars, 1),
        "results": len(results),
        "stale_pct": f"{stale_pct:.0%}",
        "relevance": f"{relevance:.0%}",
        "verdict": verdict,
        "top_result": f"{results[0]['owner']['login']}/{results[0]['name']} ({top_stars}⭐)" if results else "none",
    }


def cmd_gaps():
    """Find high-demand empty search lanes."""
    print("\nScanning GitHub for gap opportunities...\n")
    print(f"{'Query':40} {'Freq':8} {'Gap':5} {'Top⭐':6} {'Verdict'}")
    print(f"{'─'*40} {'─'*8} {'─'*5} {'─'*6} {'─'*30}")

    opportunities = []
    for q in DEMAND_QUERIES:
        result = analyze_gap(q)
        opportunities.append(result)

        freq = result["frequency"]
        gap = result["gap_score"]
        top = result["top_stars"]
        verdict = result["verdict"]

        # Color coding via symbols
        if "BUILD" in verdict:
            marker = "🟢"
        elif "CONSIDER" in verdict:
            marker = "🟡"
        else:
            marker = "🔴"

        print(f"{marker} {result['query']:38} {freq:8} {gap:5.1f} {top:6} {verdict}")
        time.sleep(0.5)  # Rate limiting

    # Summary
    builds = [o for o in opportunities if "BUILD" in o["verdict"]]
    print(f"\n{'='*80}")
    print(f"  {len(builds)} high-opportunity lanes found out of {len(opportunities)} scanned")

    if builds:
        print(f"\n  Top opportunities:")
        builds.sort(key=lambda x: x["gap_score"], reverse=True)
        for b in builds[:10]:
            print(f"    [{b['gap_score']:4.1f}] {b['query']:40} (top: {b['top_result']})")

    # Save results
    output = Path(__file__).parent / "scan_results.json"
    with open(output, "w") as f:
        json.dump({"scanned": len(opportunities), "timestamp": time.strftime("%Y-%m-%d %H:%M"), "results": opportunities}, f, indent=2)
    print(f"\n  Full results saved to {output}")


def cmd_trending():
    """Check trending starter/template repos."""
    queries = ["starter template python", "boilerplate python", "starter kit zero dependencies"]
    print("\nTrending starter repos...\n")

    for q in queries:
        print(f"\n  Search: \"{q}\"")
        results = gh_search(q, limit=5)
        for r in results:
            name = f"{r['owner']['login']}/{r['name']}"
            stars = r.get("stargazersCount", 0)
            desc = (r.get("description") or "")[:60]
            print(f"    {stars:>5}⭐  {name:45} {desc}")
        time.sleep(0.5)


def cmd_audit():
    """Audit our registry coverage."""
    if not REGISTRY.exists():
        print("No registry.json found.", file=sys.stderr)
        sys.exit(1)

    with open(REGISTRY) as f:
        registry = json.load(f)

    starters = registry.get("starters", [])
    print(f"\nRegistry Audit — {len(starters)} starters\n")

    categories = {}
    for s in starters:
        for term in s.get("recommend_when", []):
            # Rough categorization
            cat = "general"
            for kw, c in [("scrape", "scraper"), ("bot", "bot"), ("telegram", "bot"),
                          ("discord", "bot"), ("polymarket", "trading"), ("claude", "ai"),
                          ("memory", "ai"), ("api", "api"), ("cli", "cli")]:
                if kw in term.lower():
                    cat = c
                    break
            categories.setdefault(cat, []).append(term)

    # Coverage analysis
    all_categories = set(q["category"] for q in DEMAND_QUERIES)
    covered = set(categories.keys())
    missing = all_categories - covered

    print(f"  Categories covered: {', '.join(sorted(covered))}")
    print(f"  Categories missing: {', '.join(sorted(missing)) or 'none'}")

    print(f"\n  Coverage by category:")
    for cat in sorted(all_categories):
        demand_count = sum(1 for q in DEMAND_QUERIES if q["category"] == cat)
        supply_count = len(categories.get(cat, []))
        status = "✅" if supply_count > 0 else "❌"
        print(f"    {status} {cat:15} demand={demand_count:2}  supply={supply_count:2}")

    # Recommendations
    print(f"\n  Next to build:")
    for cat in sorted(missing):
        queries = [q for q in DEMAND_QUERIES if q["category"] == cat]
        best = max(queries, key=lambda q: {"very_high": 4, "high": 3, "medium": 2, "low": 1}[q["frequency"]])
        print(f"    → {best['query']} (frequency: {best['frequency']})")


def cmd_compete(query):
    """Deep competition analysis for a specific query."""
    print(f"\nCompetition analysis: \"{query}\"\n")
    results = gh_search(query, limit=10)

    if not results:
        print("  No results — EMPTY LANE. Build this.")
        return

    print(f"  {'Stars':>6}  {'Updated':10}  {'Repo':45}  Description")
    print(f"  {'─'*6}  {'─'*10}  {'─'*45}  {'─'*30}")

    for r in results:
        name = f"{r['owner']['login']}/{r['name']}"
        stars = r.get("stargazersCount", 0)
        updated = r.get("updatedAt", "")[:10]
        desc = (r.get("description") or "")[:30]
        stale = "⚠️" if updated < "2025-01-01" else "  "
        print(f"  {stars:>6}  {updated}  {name:45} {stale}{desc}")

    # Check if any have .ai-starter.json
    print(f"\n  Checking for .ai-starter.json in top results...")
    for r in results[:3]:
        repo = f"{r['owner']['login']}/{r['name']}"
        try:
            cmd = f'{GH} api repos/{repo}/contents/.ai-starter.json 2>/dev/null'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"    ⚠️  {repo} HAS .ai-starter.json — competitor using protocol")
            else:
                print(f"    ✅  {repo} — no protocol adoption")
        except Exception:
            pass


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "gaps":
        cmd_gaps()
    elif cmd == "trending":
        cmd_trending()
    elif cmd == "audit":
        cmd_audit()
    elif cmd == "compete":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        if not query:
            print("Usage: python3 scanner.py compete 'search query'", file=sys.stderr)
            sys.exit(1)
        cmd_compete(query)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print("Commands: gaps, trending, audit, compete", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
