#!/usr/bin/env python3
"""
extract_cursor.py — Parse a Cursor IDE chat export and build the same
Change Rationale Graph that extract.py builds for Claude Code transcripts.

IMPORTANT CAVEAT: unlike Claude Code (~/.claude/projects/*.jsonl) and Codex
CLI (~/.codex/sessions/**/rollout-*.jsonl), Cursor does NOT write a plain,
documented transcript file. Chat data lives inside SQLite databases
(state.vscdb, keyed by bubbleId:{composerId}:{bubbleId} in cursorDiskKV),
and the schema has already changed at least once across Cursor versions
(a breaking migration shipped in Cursor 3.0, April 2026). There's no
first-party export.

This script is a best-effort adapter for the JSON/JSONL output of the
community `cursor-session` export tool (github.com/iksnae/cursor-session),
which reads that SQLite data and exports it. Because Cursor's underlying
schema isn't officially documented, this parser tries several plausible
field names defensively rather than assuming one exact shape — if it
misses touches on your export, open the export in a text editor, find
the actual key names for role/text/tool-call/file-path, and adjust the
CANDIDATE_* lists below. That's a five-minute edit, not a rewrite.

Expected input shape (a JSON array of "bubble" objects, or {"bubbles": [...]}):
    {
      "bubbleId": "...",
      "type": 1 | 2,              # 1 = user, 2 = assistant (common convention;
                                   # some exports normalize this to "role" instead)
      "text": "...",               # message / reasoning text
      "toolFormerData": {          # present on assistant bubbles that called a tool
        "name": "edit_file" | "write" | ...,
        "params": { "target_file": "...", ... }   # or "rawArgs", "path", etc.
      }
    }

Usage:
    # first, export your Cursor session, e.g.:
    #   cursor-session export --format json --session <id> -o session.json
    python extract_cursor.py session.json -o graph.json
"""
import json
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract import build_graph, clean_reasoning  # noqa: E402

CANDIDATE_ROLE_KEYS = ["role", "type"]
CANDIDATE_TEXT_KEYS = ["text", "content", "message"]
CANDIDATE_TOOLDATA_KEYS = ["toolFormerData", "toolCall", "tool_call", "toolCalls"]
CANDIDATE_TOOLNAME_KEYS = ["name", "toolName", "tool"]
CANDIDATE_PARAMS_KEYS = ["params", "args", "rawArgs", "arguments", "input"]
CANDIDATE_FILEPATH_KEYS = ["target_file", "file_path", "filePath", "path", "relative_path", "relativePath"]
WRITE_TOOL_NAMES = {"edit_file", "write", "write_file", "create_file", "apply_diff", "search_replace"}
READ_TOOL_NAMES = {"read_file", "view_file", "list_dir"}


def load_export(path):
    with open(path, "r") as f:
        data = json.load(f)
    if isinstance(data, dict):
        for key in ("bubbles", "messages", "conversation"):
            if key in data and isinstance(data[key], list):
                return data[key]
        # maybe it's a dict of composerId -> list
        for v in data.values():
            if isinstance(v, list):
                return v
        return []
    if isinstance(data, list):
        return data
    return []


def first_present(d, keys):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return None


def is_user_bubble(bubble):
    role = first_present(bubble, CANDIDATE_ROLE_KEYS)
    if role in ("user", 1, "1"):
        return True
    if role in ("assistant", 2, "2"):
        return False
    return None  # unknown — caller should treat cautiously


def extract_file_path(params):
    if not isinstance(params, dict):
        return None
    return first_present(params, CANDIDATE_FILEPATH_KEYS)


def extract_events(bubbles):
    turn_index = -1
    touches = []
    order_counter = 0
    pending_reasoning = ""
    unresolved_role_count = 0

    for bubble in bubbles:
        if not isinstance(bubble, dict):
            continue

        role_is_user = is_user_bubble(bubble)
        if role_is_user is None:
            unresolved_role_count += 1

        if role_is_user:
            turn_index += 1
            continue

        text = first_present(bubble, CANDIDATE_TEXT_KEYS)
        if text and isinstance(text, str):
            pending_reasoning = text

        tool_data = first_present(bubble, CANDIDATE_TOOLDATA_KEYS)
        if not tool_data:
            continue
        if isinstance(tool_data, list):
            tool_calls = tool_data
        else:
            tool_calls = [tool_data]

        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            tool_name = first_present(call, CANDIDATE_TOOLNAME_KEYS) or ""
            params = first_present(call, CANDIDATE_PARAMS_KEYS)
            fpath = extract_file_path(params) or extract_file_path(call)
            if not fpath:
                continue
            action = "write" if tool_name in WRITE_TOOL_NAMES else (
                "read" if tool_name in READ_TOOL_NAMES else "write"
            )
            order_counter += 1
            touches.append({
                "file": fpath,
                "action": action,
                "tool": tool_name or "unknown",
                "reasoning": clean_reasoning(pending_reasoning) if pending_reasoning else "",
                "turn": max(turn_index, 0),
                "order": order_counter,
            })

    if unresolved_role_count:
        print(f"  ! {unresolved_role_count} bubbles had no recognizable role field — "
              f"turn boundaries may be inaccurate. Check CANDIDATE_ROLE_KEYS in this script "
              f"against your export's actual field names.", file=sys.stderr)

    return touches


def main():
    ap = argparse.ArgumentParser(description="Build a change-rationale graph from a Cursor chat export")
    ap.add_argument("export", help="Path to a Cursor session export (JSON, from e.g. cursor-session)")
    ap.add_argument("-o", "--output", default="graph.json", help="Output graph JSON path")
    args = ap.parse_args()

    bubbles = load_export(args.export)
    print(f"loaded {len(bubbles)} bubbles")

    touches = extract_events(bubbles)
    files = set(t["file"] for t in touches)
    print(f"found {len(touches)} file-touch events across {len(files)} files")
    if not touches:
        print("  ! no file touches detected. This adapter guesses field names since Cursor's "
              "export schema isn't officially documented — open your export file, find the real "
              "key names for tool calls and file paths, and update the CANDIDATE_* lists at the "
              "top of this script.", file=sys.stderr)

    graph = build_graph(touches)
    with open(args.output, "w") as f:
        json.dump(graph, f, indent=2)
    print(f"wrote {args.output}  ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges)")


if __name__ == "__main__":
    main()
