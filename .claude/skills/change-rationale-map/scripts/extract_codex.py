#!/usr/bin/env python3
"""
extract_codex.py — Codex CLI rollout -> graph.json.

Thin wrapper around rationale_map's Codex adapter (rationale_map/adapters/codex.py),
which parses the real, verified Codex CLI session schema — see that module's
docstring for the schema and how it was confirmed. Kept for CLI compatibility;
see AGENTS.md for the architecture.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rationale_map.adapters import codex  # noqa: E402
from rationale_map.graph import build_graph  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Build a change-rationale graph from a Codex CLI rollout")
    ap.add_argument("rollout", help="Path to rollout-*.jsonl file")
    ap.add_argument("-o", "--output", default="graph.json", help="Output graph JSON path")
    args = ap.parse_args()

    session = codex.parse(args.rollout)
    touches = list(session.file_events())
    files = {t["file"] for t in touches}
    print(f"found {len(touches)} file-touch events across {len(files)} files")
    if not touches:
        print("  ! no file touches detected — see rationale_map/adapters/codex.py's "
              "docstring for what it looks for.", file=sys.stderr)

    graph = build_graph(session)
    with open(args.output, "w") as f:
        json.dump(graph, f, indent=2)
    print(f"wrote {args.output}  ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges)")


if __name__ == "__main__":
    main()
