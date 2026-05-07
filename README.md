# codebase-agent

A Claude Code plugin that gives Claude semantic understanding of any codebase.

Index once — Claude searches your code by meaning, understands your project's patterns, and follows your conventions when creating new files.

## Install

See [codebase-agent-plugin/README.md](codebase-agent-plugin/README.md) for full install instructions.

**Quick version:**

```bash
# 1. Clone and set up
git clone https://github.com/YOUR_USERNAME/codebase-agent.git
cd codebase-agent
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Add API keys to .env
cp .env.example .env
# edit .env with your keys

# 3. Register in Claude Code
/plugin marketplace add YOUR_USERNAME/codebase-agent
/plugin install codebase-agent-plugin@YOUR_USERNAME/codebase-agent
```

## Project structure

```
codebase-agent/
  mcp_server.py          ← MCP server (auto-started by the plugin)
  reader.py              ← file reader and filter
  chunker.py             ← splits code into semantic chunks
  embedder.py            ← OpenAI embedding wrapper
  vectordb.py            ← ChromaDB wrapper
  indexer.py             ← Phase 2a: embed + store chunks
  clusterer.py           ← Phase 2b: cluster + name patterns
  patterns.py            ← file summary generation
  requirements.txt
  .env.example
  codebase-agent-plugin/ ← Claude Code plugin
    .claude-plugin/
      plugin.json
    skills/
    commands/
    hooks/
    mcp.json
```

## How it works

1. **Index** — reads your codebase, splits it into chunks, embeds them via OpenAI, discovers patterns via clustering, stores everything in `.codebase-agent/` inside your project
2. **Search** — embeds your question, finds the most semantically similar chunks
3. **Answer** — sends retrieved chunks + your question to the LLM
4. **Create** — retrieves your project's patterns before generating any new file

## Requirements

- Python 3.10+
- OpenAI API key (embeddings)
- DeepSeek or Anthropic API key (answers)
- Claude Code v2.0+
