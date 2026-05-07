# codebase-agent

Semantic codebase search and convention-aware code generation for Claude Code.
Index your project once — Claude will search it, understand its patterns, and follow your conventions automatically when creating new files.

---

## Install

**1. Clone the repo**

```bash
git clone https://github.com/YOUR_USERNAME/codebase-agent.git
cd codebase-agent
```

**2. Set up Python environment** (requires Python 3.10+)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**3. Add API keys** — create a `.env` file at the repo root:

```bash
OPENAI_API_KEY=sk-...        # required — used for embeddings
DEEPSEEK_API_KEY=sk-...      # required — used for answers
```

> Prefer Claude over DeepSeek? Add `ANTHROPIC_API_KEY=sk-ant-...` and `LLM_PROVIDER=anthropic` instead.

**4. Register the plugin marketplace**

```
/plugin marketplace add YOUR_USERNAME/codebase-agent
```

**5. Install the plugin**

```
/plugin install codebase-agent-plugin@YOUR_USERNAME/codebase-agent
```

---

## Quickstart

Open Claude Code in any project and say:

```
index this project
```

That's it. Once indexed, just ask naturally:

```
how does authentication work?
find the Button component
create a new settings page
```

---

## Commands

| Say this               | Or type this                     | What it does               |
| ---------------------- | -------------------------------- | -------------------------- |
| `check project status` | `/codebase-agent:status`         | Is this project indexed?   |
| `index this project`   | `/codebase-agent:index`          | Index current project      |
| `index from scratch`   | `/codebase-agent:index --reset`  | Re-index after big changes |
| anything               | `/codebase-agent:ask [question]` | Ask about the codebase     |

---

## How it works

Each project gets its own isolated database stored at `.codebase-agent/` inside your project folder — automatically gitignored. Opening Claude Code in a different project gives you a fresh context for that project.
