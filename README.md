# why-this-file

A Claude Code plugin that turns a session transcript (`.jsonl`) into a
standalone, interactive HTML graph showing which files were touched, why
(the agent's own reasoning right before each tool call), and how the
touches relate to each other (same-turn co-occurrence, or one file's
rationale referencing another file by name).

## Install

Point Claude Code at this repo as a plugin source, per the Claude Code
plugin docs, then enable the `change-rationale-map` plugin.

## Use

Once installed, the `change-rationale-map` skill activates automatically
when you ask Claude to visualize, map, or explain why a session touched
the files it did — or invoke it directly:

```
python3 skills/change-rationale-map/scripts/extract.py transcript.jsonl -o graph.json
python3 skills/change-rationale-map/scripts/render.py graph.json -o map.html -t "my session"
```

Open `map.html` in a browser, or ask Claude to publish it as an Artifact.

## Repo layout

- `.claude-plugin/plugin.json` — plugin manifest
- `skills/change-rationale-map/` — the skill (`SKILL.md` + scripts)
- `.claude/skills/change-rationale-map/` — same skill, auto-loaded for anyone
  working directly in this repo (no plugin install needed)
- `files/` — original scripts and a sample transcript, kept for reference
