# why-this-file

Turns a coding-agent session transcript into a standalone, interactive HTML
graph showing which files were touched, why (the agent's own reasoning
right before each tool call), and how the touches relate to each other
(same-turn co-occurrence, or one file's rationale referencing another file
by name).

Agent-agnostic by design: a small normalized intermediate representation
sits between agent-specific transcript parsing and the graph/rendering
logic, so adding a new agent means writing one adapter, not touching the
core. Supports **Claude Code**, **OpenAI Codex CLI** (verified against real
rollout files), and **Cursor** (best-effort, unverified — see
`AGENTS.md`). Distributed both as a Claude Code plugin/skill and as a
plain CLI any agent can run directly.

Full architecture, data flow, and "how to add another agent" writeup:
**[AGENTS.md](./AGENTS.md)**.

## Use directly (any agent, any terminal)

```bash
python3 -m venv .venv && .venv/bin/pip install pytest   # only needed to run tests
./cli.py map --agent claude-code samples/sample_transcript_claude.jsonl -o map.html -t "my session"
./cli.py map --agent codex samples/sample_transcript_codex.jsonl -o map.html -t "my session"
```

## Install as a Claude Code plugin

```
/plugin marketplace add Sheryansh96/why-this-file
/plugin install change-rationale-map@why-this-file
```

Once installed, the `change-rationale-map` skill activates automatically
when you ask Claude to visualize, map, or explain why a session touched
the files it did — or invoke it directly with the same CLI commands
documented in `SKILL.md`.

## Repo layout

- `AGENTS.md` — architecture, data flow, how to run/test, how to add an agent
- `rationale_map/` — symlink to the actual package (see AGENTS.md for why)
- `cli.py` — repo-root CLI entry point
- `.claude-plugin/marketplace.json` — marketplace catalog (lists this plugin)
- `.claude-plugin/plugin.json` — plugin manifest
- `skills/change-rationale-map/` — canonical source: the skill (`SKILL.md`)
  and the `rationale_map` package it wraps
- `.claude/skills/change-rationale-map/` — mirror, auto-loaded for anyone
  working directly in this repo (no plugin install needed)
- `samples/` — one example transcript per agent, used both as a manual demo
  and as pytest fixtures
- `tests/` — pytest suite (IR, graph builder, each adapter, the adapter
  boundary contract, and the CLI end-to-end)
