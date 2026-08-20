#!/usr/bin/env python3
"""
cli.py — single entry point for the why-this-file project. Any agent
(human, Claude Code, Codex, ...) can run this without reading any other
file in the project.

    why-this-file analyze transcript.jsonl -o map.html
    why-this-file analyze --agent codex rollout.jsonl -o map.html -t "my session"

    # lower-level, if you want the intermediate graph.json:
    why-this-file extract --agent claude-code transcript.jsonl -o graph.json
    why-this-file render graph.json -o map.html -t "my session"

`analyze` (alias: `map`) is extract+render combined and auto-detects which
agent produced the transcript if `--agent` is omitted — the common case of
"just show me the graph, I don't care how." `extract`/`render` stay
separate because graph.json is a useful, inspectable artifact on its own
(e.g. for the tests in tests/).
"""
import argparse
import json
import sys

from .adapters import ADAPTERS
from .graph import build_graph
from .render import render

# Agent detection: a session file's own {"type": ...} vocabulary is
# disjoint enough per agent to sniff from the first parsed line, without
# needing a --agent flag for the common case. Order matters only in that
# each check must not false-positive on another agent's shape.
_CLAUDE_ROLES = {"user", "assistant"}
_CODEX_TYPES = {"session_meta", "turn_context", "response_item", "event_msg"}


_SNIFF_LINES = 50  # real Claude Code sessions prepend several non-conversation
                    # control lines ({"type":"mode",...}, {"type":"bridge-session",...},
                    # etc.) before the first actual user/assistant message, so checking
                    # only line 1 misses them — scan a window instead.


def sniff_agent(path):
    """Best-effort agent detection from a transcript's own shape. Returns
    an agent name from ADAPTERS, or None if it can't tell."""
    try:
        with open(path, "r") as f:
            content = f.read()
    except OSError:
        return None
    content = content.strip()
    if not content:
        return None

    lines = content.splitlines()
    for line in lines[:_SNIFF_LINES]:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("type") in _CODEX_TYPES and "payload" in obj:
            return "codex"
        message = obj.get("message")
        if obj.get("type") in _CLAUDE_ROLES or (
            isinstance(message, dict) and message.get("role") in _CLAUDE_ROLES
        ):
            return "claude-code"

    # nothing in the scanned window matched a known JSONL shape — try the
    # file as one whole JSON document instead. The only adapter that reads
    # a whole-file JSON document today is cursor's bubble export. A real
    # multi-line JSONL file will fail this (json.loads chokes on the
    # second top-level value), so it's a safe fallback either way.
    try:
        json.loads(content)
    except json.JSONDecodeError:
        return None
    return "cursor"


def _resolve_agent(args):
    if args.agent:
        return args.agent
    guess = sniff_agent(args.transcript)
    if guess is None:
        print(f"error: couldn't detect which agent produced {args.transcript} — pass --agent "
              f"explicitly (one of: {', '.join(sorted(ADAPTERS))})", file=sys.stderr)
        sys.exit(2)
    print(f"[detected agent: {guess}]", file=sys.stderr)
    return guess


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


def _render(args, graph_data=None):
    if graph_data is None:
        with open(args.graph) as f:
            graph_data = json.load(f)
    html = render(graph_data, title=args.title)
    with open(args.output, "w") as f:
        f.write(html)
    print(f"wrote {args.output}", file=sys.stderr)


def _add_analyze_like(sub, name, help_text):
    p = sub.add_parser(name, help=help_text)
    p.add_argument("transcript", help="path to a session transcript")
    p.add_argument("--agent", choices=sorted(ADAPTERS), default=None,
                    help="which agent produced this transcript; auto-detected from its "
                         "shape if omitted")
    p.add_argument("-o", "--output", default="map.html")
    p.add_argument("-t", "--title", default="session")
    p.set_defaults(func=lambda a: _render(a, graph_data=_build_graph(_resolve_agent(a), a.transcript)))
    return p


def build_parser():
    ap = argparse.ArgumentParser(prog="why-this-file", description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    _add_analyze_like(sub, "analyze", "transcript -> map.html, auto-detecting the source agent")
    _add_analyze_like(sub, "map", "alias for `analyze`")

    p_extract = sub.add_parser("extract", help="transcript -> graph.json, for inspecting the intermediate graph")
    p_extract.add_argument("transcript", help="path to a session transcript")
    p_extract.add_argument("--agent", choices=sorted(ADAPTERS), default=None,
                            help="which agent produced this transcript; auto-detected from its "
                                 "shape if omitted")
    p_extract.add_argument("-o", "--output", default="graph.json")
    p_extract.set_defaults(func=lambda a: _extract(a))

    p_render = sub.add_parser("render", help="graph.json -> map.html (no transcript parsing involved)")
    p_render.add_argument("graph", help="path to a graph.json produced by `extract`")
    p_render.add_argument("-o", "--output", default="map.html")
    p_render.add_argument("-t", "--title", default="session")
    p_render.set_defaults(func=lambda a: _render(a))

    return ap


def _extract(args):
    graph = _build_graph(_resolve_agent(args), args.transcript)
    with open(args.output, "w") as f:
        json.dump(graph, f, indent=2)
    print(f"wrote {args.output}", file=sys.stderr)
    return graph


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
