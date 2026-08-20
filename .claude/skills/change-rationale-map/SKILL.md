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

1. One of the `extract_*.py` scripts parses the transcript and emits a graph
   (`graph.json`): nodes = files (with a timeline of touches + reasoning),
   edges = same-turn co-occurrence or cross-file references found in
   reasoning text. All three extractors share `build_graph`/`clean_reasoning`
   from `extract.py` so the graph shape is identical regardless of source.
2. `render.py` renders `graph.json` into a self-contained `map.html` (D3.js
   force-directed graph, dark theme, file sidebar + detail panel with the
   full reasoning timeline for the selected file). `render.py` is
   source-agnostic — it only ever reads `graph.json`.

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

## Notes

- No external Python deps. `render.py` bundles D3 (`scripts/d3.min.js`)
  inline into the generated HTML — required for the output to work when
  published as a Claude Artifact, since Artifacts block external script
  loads (only Google Fonts is allowed through their CSP).
- If the user doesn't specify an output location, write `graph.json` and
  `map.html` next to the input transcript, or in the current working
  directory if that's not writable.
- `extract_codex.py` infers file touches from `apply_patch` calls (reliable)
  or shell-idiom regexes (`sed -i`, `cat >`, `tee`, `mv`, `cp` — best-effort,
  since Codex has no dedicated Edit/Write tool). If a session shows 0
  touches, the session likely used a shell pattern the regexes don't cover.
- `extract_cursor.py` is a best-effort adapter: Cursor has no documented
  transcript schema (chat lives in a SQLite DB, and the schema has already
  changed across versions), so it tries several plausible field names
  defensively. If it finds 0 touches, open the export and check the actual
  key names against the `CANDIDATE_*` lists at the top of the script — a
  small edit, not a rewrite.
