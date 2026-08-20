#!/usr/bin/env python3
"""
extract_codex.py — Parse an OpenAI Codex CLI session rollout (.jsonl) and
build the same Change Rationale Graph that extract.py builds for Claude
Code transcripts.

Codex CLI writes sessions to:
    ~/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<uuid>.jsonl

Each line is: {"timestamp": ..., "type": ..., "payload": {...}}
Relevant "type" values:
    session_meta     — one-time header, ignored here
    turn_context     — per-turn metadata, ignored here
    response_item    — the actual conversation content, payload.type is:
        "message"              — role user/assistant/developer, content
                                  is a list of {"type":"input_text"|
                                  "output_text", "text": ...}
        "function_call"        — payload.name (e.g. "shell", "apply_patch"),
                                  payload.arguments (JSON string), call_id
        "function_call_output" — tool result, keyed by call_id (unused here,
                                  we only need what was touched and why)

Codex's shell-based tool calling means there's no dedicated "Edit"/"Write"
tool like Claude Code has — file touches are inferred from the command
text: apply_patch's own patch format ("*** Update File: ...", "*** Add
File: ...", "*** Delete File: ...") is the reliable signal; a fallback
regex catches common file-editing shell idioms (sed -i, cat >, tee, mv,
cp) for sessions that shell out directly instead of using apply_patch.

Usage:
    python extract_codex.py rollout.jsonl -o graph.json
"""
import json
import re
import argparse
import sys
from pathlib import Path

# reuse the graph builder + helpers from extract.py
sys.path.insert(0, str(Path(__file__).parent))
from extract import build_graph, clean_reasoning  # noqa: E402

PATCH_FILE_RE = re.compile(r"^\*\*\* (Update|Add|Delete) File: (.+)$", re.MULTILINE)
# crude fallback: shell idioms that write to a file, capturing the path
SHELL_WRITE_RE = re.compile(
    r"(?:sed -i[^\s]*\s+\S+\s+|>>?\s*|tee\s+(?:-a\s+)?|mv\s+\S+\s+|cp\s+\S+\s+)([^\s|;&<>]+\.\w+)"
)
FILE_EXT_RE = re.compile(r"\b[\w./-]+\.\w{1,8}\b")


def load_rollout(path):
    lines = []
    with open(path, "r") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"  ! skipping malformed line {line_no}", file=sys.stderr)
    return lines


def _decode_arguments(args_str):
    """
    `arguments` is a JSON-encoded string (standard OpenAI function-calling
    shape) — decode it once to get real newlines/quotes back, and pull out
    the text we actually want to scan (patch body or shell command).
    """
    try:
        parsed = json.loads(args_str)
    except (json.JSONDecodeError, TypeError):
        return args_str  # already-plain text, or malformed — scan as-is

    if isinstance(parsed, dict):
        if "input" in parsed:  # apply_patch shape
            return parsed["input"]
        if "command" in parsed:  # shell shape: list or string
            cmd = parsed["command"]
            return " ".join(cmd) if isinstance(cmd, list) else str(cmd)
    return args_str


def touches_from_apply_patch(args_str):
    """Extract (action, file) pairs from an apply_patch call's patch text."""
    text = _decode_arguments(args_str)
    out = []
    for action_word, fpath in PATCH_FILE_RE.findall(text):
        out.append((fpath.strip(), "write"))
    return out


def touches_from_shell(args_str):
    """Best-effort: look for common file-writing shell idioms."""
    text = _decode_arguments(args_str)
    out = []
    for fpath in SHELL_WRITE_RE.findall(text):
        out.append((fpath.strip(), "write"))
    # cat/read-style commands: treat mentioned files as reads if nothing
    # else matched, so at least the file shows up in the graph
    if not out:
        m = re.search(r"\b(?:cat|less|head|tail)\s+([^\s|;&<>]+\.\w+)", text)
        if m:
            out.append((m.group(1), "read"))
    return out


def extract_events(raw_lines):
    turn_index = -1
    touches = []
    order_counter = 0
    pending_reasoning = ""

    for raw in raw_lines:
        if raw.get("type") != "response_item":
            continue
        payload = raw.get("payload", {})
        ptype = payload.get("type")

        if ptype == "message":
            role = payload.get("role")
            content = payload.get("content", [])
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") in ("input_text", "output_text", "text"):
                    texts.append(block.get("text", ""))
            joined = " ".join(t for t in texts if t)

            if role == "user":
                turn_index += 1
            elif role == "assistant" and joined:
                pending_reasoning = joined

        elif ptype == "function_call":
            name = payload.get("name", "")
            args_str = payload.get("arguments", "")
            if not isinstance(args_str, str):
                args_str = json.dumps(args_str)

            file_touches = []
            if "apply_patch" in name or "*** Update File:" in args_str or "*** Add File:" in args_str:
                file_touches = touches_from_apply_patch(args_str)
            elif name in ("shell", "exec_command", "bash", "local_shell"):
                file_touches = touches_from_shell(args_str)

            for fpath, action in file_touches:
                order_counter += 1
                touches.append({
                    "file": fpath,
                    "action": action,
                    "tool": name,
                    "reasoning": clean_reasoning(pending_reasoning) if pending_reasoning else "",
                    "turn": max(turn_index, 0),
                    "order": order_counter,
                })

    return touches


def main():
    ap = argparse.ArgumentParser(description="Build a change-rationale graph from a Codex CLI rollout")
    ap.add_argument("rollout", help="Path to rollout-*.jsonl file")
    ap.add_argument("-o", "--output", default="graph.json", help="Output graph JSON path")
    args = ap.parse_args()

    raw = load_rollout(args.rollout)
    print(f"loaded {len(raw)} rollout lines")

    touches = extract_events(raw)
    files = set(t["file"] for t in touches)
    print(f"found {len(touches)} file-touch events across {len(files)} files")
    if not touches:
        print("  ! no file touches detected — this session may not have used apply_patch or "
              "recognizable shell write idioms. See the fallback regexes in this script if your "
              "session used a different pattern.", file=sys.stderr)

    graph = build_graph(touches)
    with open(args.output, "w") as f:
        json.dump(graph, f, indent=2)
    print(f"wrote {args.output}  ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges)")


if __name__ == "__main__":
    main()
