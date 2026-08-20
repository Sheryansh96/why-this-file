---
name: change-rationale-map
description: Build an interactive "why was this file touched" visualization from a Claude Code session transcript (.jsonl). Use when the user asks to visualize/map/explain a session's file changes, wants a "change rationale graph/map", asks "why did you touch these files" retrospectively, or wants to turn a transcript into an HTML graph of files + reasoning + turn order.
---

# Change Rationale Map

Turns a Claude Code `.jsonl` session transcript into a standalone, interactive
HTML graph showing which files were touched, why (the agent's own reasoning
text right before each tool call), and how the touches relate to each other
(same-turn co-occurrence, or one file's rationale mentioning another file's
name).

## When to use

- User wants to visualize or audit what a coding session did and why.
- User asks for a "change rationale graph/map" of a transcript.
- User wants to inspect an agent's reasoning trail file-by-file after the fact.

## How it works

Two scripts in `scripts/`, run in sequence:

1. `extract.py` — parses the transcript, pairs each file-touching tool call
   (`Edit`, `Write`, `MultiEdit`, `Read`, `NotebookEdit`) with the reasoning
   text that preceded it, and emits a graph (`graph.json`): nodes = files
   (with a timeline of touches + reasoning), edges = same-turn co-occurrence
   or cross-file references found in reasoning text.
2. `render.py` — renders `graph.json` into a self-contained `map.html` (D3.js
   force-directed graph, dark theme, file sidebar + detail panel with the
   full reasoning timeline for the selected file).

## Usage

```bash
python3 scripts/extract.py <transcript.jsonl> -o graph.json
python3 scripts/render.py graph.json -o map.html -t "<short label for header>"
```

Then open `map.html` in a browser (or send it to the user with SendUserFile).

## Notes

- The transcript must be in the standard Claude Code JSONL format: each line
  a `{"type": "user"|"assistant", "message": {"role", "content": [...]}}`
  object, tool calls as `tool_use` blocks, tool results as `tool_result`
  blocks in a following user message.
- If the user doesn't specify an output location, write `graph.json` and
  `map.html` next to the input transcript, or in the current working
  directory if that's not writable.
- No external Python deps; render.py's HTML pulls D3 from a CDN.
