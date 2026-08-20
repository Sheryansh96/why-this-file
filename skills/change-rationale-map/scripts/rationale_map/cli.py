#!/usr/bin/env python3
"""
cli.py — single entry point for the change-rationale-map project. Any
agent (human, Claude Code, Codex, ...) can run this without reading any
other file in the project.

    rationale-map extract --agent claude-code transcript.jsonl -o graph.json
    rationale-map render graph.json -o map.html -t "my session"
    rationale-map map --agent codex rollout.jsonl -o map.html -t "my session"

`map` is extract+render combined, for the common case of "just show me the
graph." `extract`/`render` stay separate because graph.json is a useful,
inspectable artifact on its own (e.g. for the tests in tests/).
"""
import argparse
import json
import sys

from .adapters import ADAPTERS
from .graph import build_graph
from .render import render


def _build_graph(agent, transcript):
    parse = ADAPTERS[agent]
    session = parse(transcript)
    graph = build_graph(session)
    n_files = len(graph["nodes"])
    print(f"[{agent}] parsed {transcript}", file=sys.stderr)
    print(f"  {n_files} nodes, {len(graph['edges'])} edges", file=sys.stderr)
    if n_files == 0:
        print("  ! no file touches detected — see the adapter's module docstring "
              f"(adapters/{agent.replace('-', '_')}.py) for what it looks for "
              "and how to extend it.", file=sys.stderr)
    return graph


def _extract(args):
    graph = _build_graph(args.agent, args.transcript)
    with open(args.output, "w") as f:
        json.dump(graph, f, indent=2)
    print(f"wrote {args.output}", file=sys.stderr)
    return graph


def _render(args, graph_data=None):
    if graph_data is None:
        with open(args.graph) as f:
            graph_data = json.load(f)
    html = render(graph_data, title=args.title)
    with open(args.output, "w") as f:
        f.write(html)
    print(f"wrote {args.output}", file=sys.stderr)


def build_parser():
    ap = argparse.ArgumentParser(prog="rationale-map", description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="transcript -> graph.json")
    p_extract.add_argument("transcript", help="path to a session transcript")
    p_extract.add_argument("--agent", choices=sorted(ADAPTERS), required=True)
    p_extract.add_argument("-o", "--output", default="graph.json")
    p_extract.set_defaults(func=lambda a: _extract(a))

    p_render = sub.add_parser("render", help="graph.json -> map.html")
    p_render.add_argument("graph", help="path to a graph.json produced by `extract`")
    p_render.add_argument("-o", "--output", default="map.html")
    p_render.add_argument("-t", "--title", default="session")
    p_render.set_defaults(func=lambda a: _render(a))

    p_map = sub.add_parser("map", help="transcript -> map.html (extract + render)")
    p_map.add_argument("transcript", help="path to a session transcript")
    p_map.add_argument("--agent", choices=sorted(ADAPTERS), required=True)
    p_map.add_argument("-o", "--output", default="map.html")
    p_map.add_argument("-t", "--title", default="session")
    p_map.set_defaults(func=lambda a: _render(a, graph_data=_build_graph(a.agent, a.transcript)))

    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
