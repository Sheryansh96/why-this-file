#!/usr/bin/env python3
"""
extract_cursor.py — Cursor chat export -> graph.json.

Thin wrapper around rationale_map's Cursor adapter (rationale_map/adapters/cursor.py),
a best-effort, unverified parser — see that module's docstring for the caveat.
Kept for CLI compatibility; see AGENTS.md for the architecture.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rationale_map.adapters import cursor  # noqa: E402
from rationale_map.graph import build_graph  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Build a change-rationale graph from a Cursor chat export")
    ap.add_argument("export", help="Path to a Cursor session export (JSON, from e.g. cursor-session)")
    ap.add_argument("-o", "--output", default="graph.json", help="Output graph JSON path")
    args = ap.parse_args()

    session = cursor.parse(args.export)
    touches = list(session.file_events())
    files = {t["file"] for t in touches}
    print(f"found {len(touches)} file-touch events across {len(files)} files")
    if not touches:
        print("  ! no file touches detected. This adapter guesses field names since Cursor's "
              "export schema isn't officially documented — see rationale_map/adapters/cursor.py.",
              file=sys.stderr)

    graph = build_graph(session)
    with open(args.output, "w") as f:
        json.dump(graph, f, indent=2)
    print(f"wrote {args.output}  ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges)")


if __name__ == "__main__":
    main()
