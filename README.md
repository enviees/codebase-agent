# codebase-agent

Semantic codebase search and convention-aware code generation for Claude Code.
Index your project once — Claude will search it, understand its patterns, and follow your conventions automatically when creating new files.

---

## Install

```
/plugin install codebase-agent
```

---

## API Keys

Add these to your shell profile (`~/.zshrc` or `~/.bashrc`):

```bash
export OPENAI_API_KEY=sk-...        # required — used for embeddings
export DEEPSEEK_API_KEY=sk-...      # required — used for answers
```

Reload your shell, then restart Claude Code.

> Prefer Claude over DeepSeek? Add `ANTHROPIC_API_KEY=sk-ant-...` and `LLM_PROVIDER=anthropic` instead.

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
