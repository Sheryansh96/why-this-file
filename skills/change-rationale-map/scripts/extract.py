#!/usr/bin/env python3
"""
extract.py — Claude Code transcript -> graph.json.

Thin backward-compatible wrapper around rationale_map's Claude Code adapter,
kept so the documented plugin/skill CLI
(`python3 scripts/extract.py transcript.jsonl -o graph.json`) keeps working
unchanged. The real logic lives in rationale_map/adapters/claude_code.py and
rationale_map/graph.py — see AGENTS.md for the architecture.

For other agents, or to skip the intermediate graph.json file, use
rationale_map/cli.py directly (`rationale-map extract --agent ... `).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rationale_map.adapters import claude_code  # noqa: E402
from rationale_map.graph import build_graph  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Build a change-rationale graph from a Claude Code transcript")
    ap.add_argument("transcript", help="Path to .jsonl transcript file")
    ap.add_argument("-o", "--output", default="graph.json", help="Output graph JSON path")
    args = ap.parse_args()

    session = claude_code.parse(args.transcript)
    n_touches = sum(1 for _ in session.file_events())
    n_files = len({e["file"] for e in session.file_events()})
    print(f"found {n_touches} file-touch events across {n_files} files")

    graph = build_graph(session)
    with open(args.output, "w") as f:
        json.dump(graph, f, indent=2)
    print(f"wrote {args.output}  ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges)")


if __name__ == "__main__":
    main()
