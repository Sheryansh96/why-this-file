# AGENTS.md

Instructions for any coding agent (Claude Code, Codex CLI, or otherwise)
working in this repository.

## Purpose

`why-this-file` turns a coding-agent session transcript into an interactive
HTML graph answering, for every file that got touched: *why*, in what
order, and how the touches relate to each other. Nodes are files; a node's
detail panel shows the reasoning text the agent produced immediately
before each tool call on that file, in chronological order. Edges are
either same-turn co-occurrence (files touched together) or a "referenced"
edge (one file's rationale text mentions another file's name).

It supports transcripts from multiple agents (Claude Code, Codex CLI,
Cursor) by parsing each into one shared, agent-neutral representation
before doing anything else. See "Architecture and data flow" below.

## Repository structure

```
rationale_map/                                  symlink -> skills/change-rationale-map/scripts/rationale_map
                                                 (lets you `import rationale_map` from repo root)
cli.py                                          repo-root CLI entry point
pyproject.toml                                  packaging + pytest config
conftest.py                                     puts repo root on sys.path for pytest

skills/change-rationale-map/                    THE CANONICAL SOURCE — everything else is a copy of this
  SKILL.md                                      Claude Code skill manifest
  scripts/
    rationale_map/                              the actual project (see below)
    extract.py, extract_codex.py,
    extract_cursor.py, render.py                thin backward-compat CLI wrappers (see "constraints")

.claude/skills/change-rationale-map/            mirror of skills/change-rationale-map/, auto-loaded
                                                 for anyone working directly in this repo (no plugin
                                                 install needed)
.claude-plugin/
  plugin.json                                   plugin manifest (points at skills/change-rationale-map)
  marketplace.json                              lets others `/plugin install` this from this repo

samples/                                        one example transcript per supported agent — used as
                                                 both a manual "try it" fixture and the pytest fixtures
tests/                                           pytest suite (see "how to run tests")
```

### `rationale_map/` package (the actual project)

```
rationale_map/
  ir.py            the normalized intermediate representation (IR) — see below
  graph.py          IR Session -> Change Rationale Graph. Agent-neutral.
  render.py         Graph -> standalone HTML (D3, inlined). Agent-neutral.
  cli.py            `extract` / `render` / `map` subcommands
  d3.min.js         vendored, so generated HTML has no external script deps
  adapters/
    __init__.py      ADAPTERS registry: {agent-name: parse-function}
    claude_code.py   Claude Code transcript -> Session
    codex.py         Codex CLI rollout -> Session
    cursor.py        Cursor chat export -> Session (best-effort, unverified — see its docstring)
```

**Why `skills/change-rationale-map/scripts/rationale_map/` and not just
`rationale_map/` at the repo root:** the Claude Code plugin is distributed
by pointing installers at `skills/change-rationale-map/` alone (see
`.claude-plugin/plugin.json`) — that subtree has to be self-contained for
`/plugin install` to work standalone, without the rest of this repo coming
along. The root-level `rationale_map` symlink and `cli.py` exist purely for
convenience when working in this repo (imports, tests, `./cli.py ...`
without a `cd`); they are not a second copy of the code.

## Architecture and data flow

```
   raw transcript                    IR                  graph.json              map.html
 (agent-specific)  --adapter.parse-->  Session  --graph.build_graph-->  {nodes,edges}  --render.render-->  HTML
```

1. **Adapter** (`adapters/<agent>.py`): the *only* place that knows an
   agent's transcript format. Exposes one function, `parse(path) ->
   ir.Session`. Nothing else in the project reads a raw transcript.
2. **IR** (`ir.py`): `Session` / `Turn` / `ToolCall` / `FileTouch` /
   `ToolResult` — see that file's docstring for the full field list. This
   is the seam between "agent-specific" and "agent-neutral" code. Adding a
   new agent means writing an adapter that produces this shape; it never
   means touching `graph.py` or `render.py`.
3. **Graph builder** (`graph.py`): `build_graph(session) -> {"nodes":
   [...], "edges": [...]}`. Only ever calls `session.file_events()`, which
   flattens the IR into an ordered stream of file touches. Has never heard
   of Claude, Codex, or Cursor.
4. **Renderer** (`render.py`): `render(graph_dict, title) -> html str`.
   Only ever reads the `{"nodes": [...], "edges": [...]}` shape. D3 is
   vendored and inlined into the output (`d3.min.js`) rather than loaded
   from a CDN — this matters if the HTML is published somewhere with a
   strict CSP (e.g. a Claude Artifact), where external script loads are
   blocked and a CDN `<script src>` silently fails.
5. **CLI** (`cli.py`): the only thing an agent needs to invoke. `analyze`
   (alias `map`) runs steps 1+3+4 in one shot and auto-detects which agent
   produced the transcript from its own shape (`cli.sniff_agent`); `extract`
   runs 1+3 alone (useful for inspecting the intermediate graph.json);
   `render` runs step 4 alone.

## How to run the project

From the repo root, agent auto-detected — no need to know it's Claude Code
or Codex ahead of time:

```bash
./cli.py analyze samples/sample_transcript_claude.jsonl -o map.html -t "my session"
./cli.py analyze samples/sample_transcript_codex.jsonl -o map.html -t "my session"
```

Or explicit, and/or split into steps:

```bash
./cli.py extract --agent claude-code samples/sample_transcript_claude.jsonl -o graph.json
./cli.py render graph.json -o map.html -t "my session"
```

`--agent`, when given, must be one of the keys in
`rationale_map/adapters/__init__.py`'s `ADAPTERS` dict (currently
`claude-code`, `codex`, `cursor`). Auto-detection (`sniff_agent`) works by
checking the transcript's own `{"type": ...}` vocabulary — Claude Code's
`user`/`assistant` line shape vs. Codex's `session_meta`/`response_item`/...
shape vs. a single JSON document (Cursor's export) — and exits with a clear
error asking for `--agent` if it can't tell.

Equivalent, if you prefer running it as a module: `python3 -m rationale_map
analyze ... `. Once packaged (`pip install -e .`), the same CLI is also
available as `why-this-file` and `rationale-map` (identical, two names for
the same entry point — see `pyproject.toml`).

The pre-refactor, single-agent scripts (`skills/change-rationale-map/scripts/extract.py`
etc.) still work exactly as documented in `SKILL.md` — they're now thin
wrappers around the same adapters/graph/render code.

## How to run tests

```bash
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

`conftest.py` puts the repo root on `sys.path` so `import rationale_map`
resolves via the symlink without an editable install. Tests live in
`tests/`, fixtures in `samples/` (one real-shaped transcript per agent,
reused as both a manual demo and a pytest fixture — no separate
`tests/fixtures/` copy).

- `tests/test_ir.py` — the IR's own behavior (`Session.file_events()`
  flattening/ordering), independent of any adapter.
- `tests/test_graph.py` — the graph builder as a pure function of a
  `touches` list (node aggregation, same-turn edges, reference edges).
- `tests/test_claude_code_adapter.py` — Claude Code adapter against
  `samples/sample_transcript_claude.jsonl`, including a known-good
  node/edge count to catch behavior drift from the pre-refactor version.
- `tests/test_codex_adapter.py` — Codex adapter against
  `samples/sample_transcript_codex.jsonl`.
- `tests/test_adapter_boundary.py` — every registered adapter, parametrized:
  each must accept its fixture and return IR `file_events()` with the
  exact required field set. This is what keeps the adapter contract honest
  as adapters are added.
- `tests/test_cli.py` — end-to-end through the actual CLI parser
  (extract→render, the combined `analyze`/`map` command, agent
  auto-detection against every fixture, and the zero-touches path).

## How to add support for another coding agent

1. **Get the real schema. Do not guess it.** Find the agent's actual
   session/transcript log format from its own tooling — e.g. inspect real
   files it writes to disk, or its source/docs if authoritative. If you
   can't find or verify the real format, say so explicitly rather than
   inventing a plausible-looking one (see "important architectural
   constraints" below for why this matters).
2. Add `rationale_map/adapters/<agent>.py` with one function,
   `parse(path) -> ir.Session`. Document the schema you found in the
   module docstring, including *how* you confirmed it (this is what
   `adapters/codex.py` does).
3. Register it in `rationale_map/adapters/__init__.py`'s `ADAPTERS` dict.
4. Add `samples/sample_transcript_<agent>.<ext>` — small, synthetic,
   shaped exactly like real output (same field names/nesting), for the
   same rate-limiting scenario the other fixtures use, so graphs are
   comparable across agents.
5. Add `tests/test_<agent>_adapter.py` following the Codex/Claude Code
   tests as a template; `tests/test_adapter_boundary.py` will
   automatically parametrize over the new agent once it's in `ADAPTERS`
   and has a fixture in `FIXTURE_BY_AGENT`.
6. Nothing else changes. If you find yourself editing `graph.py` or
   `render.py` to add agent support, stop — that's a sign the adapter
   isn't normalizing enough into the IR.

## Important architectural constraints

- **Adapters are the only agent-specific code.** `graph.py`, `render.py`,
  and `ir.py` must never import or branch on an agent name.
- **Don't fabricate transcript schemas.** `adapters/cursor.py` is
  explicitly marked unverified in its own docstring because Cursor has no
  documented transcript format and no local Cursor installation was
  available to check against — it's a best-effort guess with defensive
  fallback field names, not a confirmed parser. `adapters/codex.py`, by
  contrast, was built by inspecting real rollout files from multiple
  installed Codex CLI versions (`0.39.0` through `0.70.0-alpha.4`) and
  documents the two schema shapes found across that range. When schemas
  are uncertain, say so in the code and in conversation — a parser that
  silently returns zero touches on real input is worse than one that
  admits it might.
- **The plugin subtree must stay self-contained.** Anything under
  `skills/change-rationale-map/` has to work if that directory is copied
  out on its own (that's how `/plugin install` distributes it) — don't add
  imports that reach outside it.
- **The pre-refactor CLI surface is a compatibility contract.**
  `scripts/extract.py transcript.jsonl -o graph.json` and
  `scripts/render.py graph.json -o map.html` must keep working with the
  same arguments and same output shape; `SKILL.md` documents them
  verbatim and existing installs (plugin + repo-local skill) depend on it.
- **Keep it small.** The IR has exactly the fields listed in `ir.py`'s
  docstring, no more. Don't add a plugin system, a config file format, or
  speculative fields for agents that don't exist yet.

## Current state of agent support

- **Claude Code** — fully supported, verified against real transcript
  structure (this was the original, pre-refactor implementation).
- **Codex CLI** — fully supported, verified against real rollout files
  from multiple installed CLI versions. Known gap: file touches from a
  `shell`/`shell_command` call are inferred from common shell write idioms
  (`sed -i`, `cat >`, `tee`, `mv`, `cp`) via regex, since Codex has no
  dedicated edit tool the way Claude Code does — a session that edits
  files through an unrecognized shell pattern won't show up. `apply_patch`
  calls (the primary write path) are unaffected by this gap.
- **Cursor** — adapter exists but is unverified (see constraint above).
  What's needed for real support: either a local Cursor installation to
  export a real session from and inspect, or documentation/source from
  Cursor confirming the on-disk transcript/export shape. Until then,
  treat `adapters/cursor.py` as a template, not a working parser.
