#!/usr/bin/env python3
"""
extract.py — Parse a Claude Code session transcript (.jsonl) and build a
"Change Rationale Graph": which files were touched, why (the agent's own
reasoning text right before the tool call), and how touches relate to
each other (same-turn co-occurrence, or one file's rationale referencing
another file by name).

Usage:
    python extract.py transcript.jsonl -o graph.json
"""
import json
import re
import argparse
import sys
from pathlib import Path
from collections import defaultdict

FILE_TOOLS = {"Edit", "Write", "MultiEdit", "Read", "NotebookEdit"}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def load_transcript(path):
    events = []
    with open(path, "r") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"  ! skipping malformed line {line_no}", file=sys.stderr)
    return events


def file_path_from_input(tool_name, tool_input):
    if not isinstance(tool_input, dict):
        return None
    return tool_input.get("file_path") or tool_input.get("notebook_path")


def short_name(path):
    return Path(path).name if path else path


def clean_reasoning(text, max_len=280):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return text


def extract_events(raw_events):
    """
    Walk the transcript in order. Each user message (real user input, not a
    tool_result) starts a new "turn". Within a turn, assistant messages may
    contain text (reasoning) followed by one or more tool_use blocks that
    touch files. We pair each file-touch with the most recent reasoning text
    seen in that same assistant message (or turn, if the tool call had no
    adjacent text).
    """
    turn_index = -1
    touches = []  # list of dicts: file, action, tool, reasoning, turn, order
    order_counter = 0

    for raw in raw_events:
        msg = raw.get("message", {})
        role = msg.get("role")
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue

        is_tool_result_only = all(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in content
        ) and len(content) > 0

        if role == "user" and not is_tool_result_only:
            turn_index += 1
            continue

        if role != "assistant":
            continue

        pending_reasoning = ""
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                pending_reasoning = block.get("text", "")
            elif btype == "tool_use":
                name = block.get("name")
                if name in FILE_TOOLS:
                    fpath = file_path_from_input(name, block.get("input", {}))
                    if fpath:
                        order_counter += 1
                        touches.append({
                            "file": fpath,
                            "action": "write" if name in WRITE_TOOLS else "read",
                            "tool": name,
                            "reasoning": clean_reasoning(pending_reasoning) if pending_reasoning else "",
                            "turn": max(turn_index, 0),
                            "order": order_counter,
                        })
                        # reasoning consumed by first tool call after it;
                        # subsequent calls in the same block share it too,
                        # but we don't clear it — often one explanation
                        # covers a small batch of edits.
    return touches


def build_graph(touches):
    nodes = {}
    for t in touches:
        f = t["file"]
        if f not in nodes:
            nodes[f] = {
                "id": f,
                "label": short_name(f),
                "touches": [],
                "actions": set(),
                "turns": set(),
            }
        nodes[f]["touches"].append(t)
        nodes[f]["actions"].add(t["action"])
        nodes[f]["turns"].add(t["turn"])

    # finalize node summaries
    node_list = []
    for f, n in nodes.items():
        reasons = [tt["reasoning"] for tt in n["touches"] if tt["reasoning"]]
        node_list.append({
            "id": f,
            "label": n["label"],
            "touch_count": len(n["touches"]),
            "actions": sorted(n["actions"]),
            "turns": sorted(n["turns"]),
            "rationale": reasons[0] if reasons else "(no explicit reasoning captured before this tool call)",
            "all_rationales": reasons,
            "timeline": [
                {"turn": tt["turn"], "action": tt["action"], "tool": tt["tool"], "reasoning": tt["reasoning"]}
                for tt in sorted(n["touches"], key=lambda x: x["order"])
            ],
        })

    # edges: same-turn co-occurrence
    edge_weights = defaultdict(int)
    by_turn = defaultdict(list)
    for t in touches:
        by_turn[t["turn"]].append(t["file"])

    for turn, files in by_turn.items():
        seen_order = []
        for f in files:
            if f not in seen_order:
                seen_order.append(f)
        for i in range(len(seen_order) - 1):
            a, b = seen_order[i], seen_order[i + 1]
            if a != b:
                edge_weights[(a, b, "same-turn")] += 1

    # edges: reasoning of file B references file A's basename
    basenames = {f: short_name(f) for f in nodes}
    for t in touches:
        if not t["reasoning"]:
            continue
        for other_f, bn in basenames.items():
            if other_f == t["file"]:
                continue
            if bn and bn in t["reasoning"]:
                edge_weights[(other_f, t["file"], "referenced")] += 1

    edges = [
        {"source": a, "target": b, "type": typ, "weight": w}
        for (a, b, typ), w in edge_weights.items()
    ]

    return {"nodes": node_list, "edges": edges}


def main():
    ap = argparse.ArgumentParser(description="Build a change-rationale graph from a Claude Code transcript")
    ap.add_argument("transcript", help="Path to .jsonl transcript file")
    ap.add_argument("-o", "--output", default="graph.json", help="Output graph JSON path")
    args = ap.parse_args()

    raw = load_transcript(args.transcript)
    print(f"loaded {len(raw)} transcript lines")

    touches = extract_events(raw)
    print(f"found {len(touches)} file-touch events across {len(set(t['file'] for t in touches))} files")

    graph = build_graph(touches)
    with open(args.output, "w") as f:
        json.dump(graph, f, indent=2)
    print(f"wrote {args.output}  ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges)")


if __name__ == "__main__":
    main()
