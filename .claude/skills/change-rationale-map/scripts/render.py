#!/usr/bin/env python3
"""
render.py — graph.json -> standalone map.html.

Thin wrapper around rationale_map.render (agent-neutral: only ever reads
graph.json). Kept for CLI compatibility; see AGENTS.md for the architecture.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rationale_map.render import render  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Render a change-rationale graph.json into a standalone HTML visualization")
    ap.add_argument("graph", help="Path to graph.json produced by extract.py")
    ap.add_argument("-o", "--output", default="map.html", help="Output HTML path")
    ap.add_argument("-t", "--title", default="session", help="Short label shown in the header")
    args = ap.parse_args()

    with open(args.graph) as f:
        graph_data = json.load(f)

    html = render(graph_data, title=args.title)
    with open(args.output, "w") as f:
        f.write(html)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
