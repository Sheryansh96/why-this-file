"""
graph.py — turn a normalized Session (see ir.py) into the Change Rationale
Graph: which files were touched, why, and how the touches relate.

This module is agent-neutral: it has never heard of Claude Code, Codex, or
any other tool. It only knows the Session/Turn/ToolCall/FileTouch shape
defined in ir.py. All agent-specific parsing lives in adapters/.
"""
import re
from collections import defaultdict
from pathlib import Path


def short_name(path):
    return Path(path).name if path else path


def clean_reasoning(text, max_len=280):
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return text


def build_graph(session):
    """session: ir.Session -> {"nodes": [...], "edges": [...]}"""
    touches = [
        {**t, "reasoning": clean_reasoning(t["reasoning"])}
        for t in session.file_events()
    ]
    return _build_graph_from_touches(touches)


def _build_graph_from_touches(touches):
    """
    Shared core, unchanged from the original single-agent implementation:
    nodes = files (with a reasoning timeline), edges = same-turn
    co-occurrence or one file's rationale mentioning another file's
    basename. Kept as a plain function of `touches` (not `Session`) so it's
    trivially unit-testable without constructing IR objects.
    """
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
