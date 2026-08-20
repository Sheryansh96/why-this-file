import json
from pathlib import Path

from rationale_map.cli import build_parser

SAMPLES = Path(__file__).parent.parent / "samples"


def test_extract_then_render_end_to_end(tmp_path):
    graph_path = tmp_path / "graph.json"
    html_path = tmp_path / "map.html"

    args = build_parser().parse_args([
        "extract", "--agent", "claude-code",
        str(SAMPLES / "sample_transcript_claude.jsonl"), "-o", str(graph_path),
    ])
    args.func(args)
    graph = json.loads(graph_path.read_text())
    assert len(graph["nodes"]) == 5

    args = build_parser().parse_args(["render", str(graph_path), "-o", str(html_path), "-t", "test"])
    args.func(args)
    html = html_path.read_text()
    assert "Change Rationale Map" in html
    assert "cdnjs" not in html  # D3 must be inlined, not loaded externally
    assert "function d3" in html or "d3=" in html  # bundled D3 actually present


def test_map_command_produces_html_directly(tmp_path):
    html_path = tmp_path / "map.html"
    args = build_parser().parse_args([
        "map", "--agent", "codex",
        str(SAMPLES / "sample_transcript_codex.jsonl"), "-o", str(html_path), "-t", "codex test",
    ])
    args.func(args)
    assert "codex test" in html_path.read_text()


def test_extract_reports_zero_touches_without_crashing(tmp_path, capsys):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    out = tmp_path / "graph.json"
    args = build_parser().parse_args(["extract", "--agent", "cursor", str(empty), "-o", str(out)])
    args.func(args)
    graph = json.loads(out.read_text())
    assert graph == {"nodes": [], "edges": []}
    assert "no file touches detected" in capsys.readouterr().err
