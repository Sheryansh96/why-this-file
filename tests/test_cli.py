import json
from pathlib import Path

import pytest

from rationale_map.cli import build_parser, sniff_agent

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


@pytest.mark.parametrize("fixture,expected", [
    ("sample_transcript_claude.jsonl", "claude-code"),
    ("sample_transcript_codex.jsonl", "codex"),
    ("sample_transcript_cursor.json", "cursor"),
])
def test_sniff_agent_identifies_each_fixture(fixture, expected):
    assert sniff_agent(SAMPLES / fixture) == expected


def test_sniff_agent_skips_leading_control_lines(tmp_path):
    # real Claude Code session files prepend several non-conversation
    # control lines ({"type":"mode",...}, {"type":"bridge-session",...})
    # before the first actual message — detection must look past them.
    f = tmp_path / "real_shaped.jsonl"
    f.write_text(
        '{"type":"mode","mode":"normal","sessionId":"x"}\n'
        '{"type":"permission-mode","permissionMode":"auto","sessionId":"x"}\n'
        '{"type":"user","message":{"role":"user","content":[{"type":"text","text":"hi"}]}}\n'
    )
    assert sniff_agent(f) == "claude-code"


def test_sniff_agent_returns_none_for_unrecognized_input(tmp_path):
    junk = tmp_path / "junk.txt"
    junk.write_text("not json at all\njust some log lines\n")
    assert sniff_agent(junk) is None


def test_analyze_auto_detects_agent_without_a_flag(tmp_path):
    html_path = tmp_path / "map.html"
    args = build_parser().parse_args([
        "analyze", str(SAMPLES / "sample_transcript_claude.jsonl"), "-o", str(html_path),
    ])
    args.func(args)
    assert html_path.exists()


def test_analyze_exits_cleanly_when_agent_cannot_be_detected(tmp_path, capsys):
    junk = tmp_path / "junk.txt"
    junk.write_text("not a transcript")
    args = build_parser().parse_args(["analyze", str(junk), "-o", str(tmp_path / "map.html")])
    with pytest.raises(SystemExit) as exc_info:
        args.func(args)
    assert exc_info.value.code == 2
    assert "couldn't detect" in capsys.readouterr().err
