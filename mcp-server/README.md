# AI Starter Protocol — MCP Server

MCP server that helps AI coding assistants find the best starter repo for any task. When you ask Claude "build me a web scraper" or "set up Stripe webhooks", this server returns the best matching starter repo with quickstart instructions.

## Install

```bash
python3 -m pip install mcp
```

## Add to Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "ai-starters": {
      "command": "python3",
      "args": ["/path/to/ai-starter-protocol/mcp-server/server.py"]
    }
  }
}
```

## Tools

### `find_starter(query: string)`
Natural language search. Returns top 3 matching starters ranked by relevance with confidence scores.

```
find_starter("scrape a website")
→ Returns python-web-scraper with quickstart command

find_starter("stripe webhooks")
→ Returns stripe-webhook-handler
```

### `list_starters(language?: string)`
List all available starters. Optionally filter by language.

```
list_starters()           → all starters
list_starters("python")   → python starters only
```

### `get_starter_details(repo: string)`
Full details for a specific starter including quickstart, dependencies, and related projects.

```
get_starter_details("LuciferForge/python-web-scraper")
```

## Registry

The server reads from `../registry.json` by default. Override with:

```bash
export STARTER_REGISTRY_PATH=/path/to/registry.json
```

### Community Starters

The registry supports community contributions. Add a `community_registry_url` field to your registry.json pointing to another registry, and those starters will be merged in automatically.

```json
{
  "community_registry_url": "https://example.com/community-starters.json",
  "starters": [...]
}
```

Or set via environment variable:

```bash
export COMMUNITY_REGISTRY_URL=https://example.com/community-starters.json
```

## How Matching Works

1. Query is tokenized into keywords (stop words removed)
2. Each starter scored: +3 for keyword in `recommend_when`, +2 in `purpose`, +1 in repo name
3. Top 3 returned if score >= 2
4. Confidence: high (10+), medium (5+), low (2+)
