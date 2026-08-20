---
name: change-rationale-map
description: Build an interactive "why was this file touched" visualization from a coding-agent session transcript — Claude Code, OpenAI Codex CLI, or Cursor. Use when the user asks to visualize/map/explain a session's file changes, wants a "change rationale graph/map", asks "why did you touch these files" retrospectively, or wants to turn a transcript into an HTML graph of files + reasoning + turn order.
---

# Change Rationale Map

Turns a coding-agent session transcript into a standalone, interactive HTML
graph showing which files were touched, why (the agent's own reasoning text
right before each tool call), and how the touches relate to each other
(same-turn co-occurrence, or one file's rationale mentioning another file's
name).

Supports three sources, each with its own extractor, all feeding the same
renderer:

- **Claude Code** (`~/.claude/projects/*.jsonl`) — `scripts/extract.py`
- **OpenAI Codex CLI** (`~/.codex/sessions/**/rollout-*.jsonl`) — `scripts/extract_codex.py`
- **Cursor** (community export via `cursor-session`, since Cursor has no
  first-party transcript export) — `scripts/extract_cursor.py`

## When to use

- User wants to visualize or audit what a coding session did and why.
- User asks for a "change rationale graph/map" of a transcript.
- User wants to inspect an agent's reasoning trail file-by-file after the fact.
- Works for Claude Code, Codex CLI, or Cursor sessions — ask which tool
  produced the transcript if it's not obvious from the file shape (see
  "Identifying the source" below).

## How it works

The real implementation lives in `scripts/rationale_map/` (an agent-neutral
core + one adapter per agent — see the repo root's `AGENTS.md` for the full
architecture and how to add another agent). `extract.py`/`extract_codex.py`/
`extract_cursor.py`/`render.py` in this directory are thin, CLI-compatible
wrappers kept so the commands below never change:

1. An adapter (`rationale_map/adapters/<agent>.py`) parses the transcript
   into a small normalized representation, then `rationale_map/graph.py`
   turns that into a graph (`graph.json`): nodes = files (with a timeline
   of touches + reasoning), edges = same-turn co-occurrence or cross-file
   references found in reasoning text. Agent-neutral — it never branches
   on which agent produced the transcript.
2. `rationale_map/render.py` renders `graph.json` into a self-contained
   `map.html` (D3.js force-directed graph, dark theme, file sidebar +
   detail panel with the full reasoning timeline for the selected file).
   Also agent-neutral — it only ever reads `graph.json`.

## Identifying the source

- Claude Code: JSONL, each line `{"type": "user"|"assistant", "message": {"role", "content": [...]}}`.
- Codex CLI: JSONL, each line `{"timestamp", "type": "session_meta"|"turn_context"|"response_item", "payload": {...}}`.
- Cursor: a JSON array (or `{"bubbles": [...]}`) of bubble objects with `bubbleId`/`type`/`text` — only exists via a third-party export tool (`cursor-session`), not natively.

## Usage

```bash
# Claude Code
python3 scripts/extract.py <transcript.jsonl> -o graph.json

# Codex CLI
python3 scripts/extract_codex.py <rollout.jsonl> -o graph.json

# Cursor (export first with cursor-session, then:)
python3 scripts/extract_cursor.py <session.json> -o graph.json

# then, regardless of source:
python3 scripts/render.py graph.json -o map.html -t "<short label for header>"
```

Then open `map.html` in a browser (or send it to the user with SendUserFile,
or publish it as an Artifact).

There's also a single agent-neutral entry point that auto-detects which of
the three formats a transcript is, so callers don't need to know or specify
`--agent`:

```bash
python3 -m rationale_map analyze <transcript> -o map.html -t "<label>"
```

(equivalent to the per-agent commands above, chained; see the repo root's
`AGENTS.md` for the full CLI and how detection works)

## Notes

- No external Python deps. `render.py` bundles D3 (`scripts/d3.min.js`)
  inline into the generated HTML — required for the output to work when
  published as a Claude Artifact, since Artifacts block external script
  loads (only Google Fonts is allowed through their CSP).
- If the user doesn't specify an output location, write `graph.json` and
  `map.html` next to the input transcript, or in the current working
  directory if that's not writable.
- `extract_codex.py` infers file touches from `apply_patch` calls (reliable
  — this is Codex's dedicated patch tool, verified against real rollout
  files) or shell-idiom regexes (`sed -i`, `cat >`, `tee`, `mv`, `cp` —
  best-effort, since a raw shell call has no structured file-path field).
  If a session shows 0 touches, it likely edited files through a shell
  pattern the regexes don't cover.
- `extract_cursor.py` is a best-effort adapter: Cursor has no documented
  transcript schema (chat lives in a SQLite DB, and the schema has already
  changed across versions), so it tries several plausible field names
  defensively. If it finds 0 touches, open the export and check the actual
  key names against the `CANDIDATE_*` lists at the top of the script — a
  small edit, not a rewrite.
