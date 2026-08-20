from pathlib import Path

from rationale_map.adapters import claude_code
from rationale_map.graph import build_graph

FIXTURE = Path(__file__).parent.parent / "samples" / "sample_transcript_claude.jsonl"

EXPECTED_FILES = [
    "/repo/app/config.py",
    "/repo/app/middleware.py",
    "/repo/app/routes.py",
    "/repo/app/app_init.py",
    "/repo/tests/test_rate_limit.py",
]


def test_parses_expected_turns_and_files():
    session = claude_code.parse(FIXTURE)
    assert session.agent == "claude-code"
    # turn 0: initial request through the first test write; turn 1: the bugfix follow-up
    assert len(session.turns) == 2
    assert "rate limiting" in session.turns[0].user_request
    assert "client_id" in session.turns[1].user_request

    files = {e["file"] for e in session.file_events()}
    assert files == set(EXPECTED_FILES)


def test_captures_rationale_immediately_preceding_each_call():
    session = claude_code.parse(FIXTURE)
    events = list(session.file_events())
    # config.py is touched twice: a Read (reasoning: why we're looking), then
    # an Edit (reasoning: why we're changing it) — rationale should track
    # whichever call it actually preceded, not just "first touch of file".
    read_touch = next(e for e in events if e["file"] == "/repo/app/config.py" and e["action"] == "read")
    write_touch = next(e for e in events if e["file"] == "/repo/app/config.py" and e["action"] == "write")
    assert "look at how config is currently structured" in read_touch["reasoning"]
    assert "RATE_LIMIT_DEFAULT" in write_touch["reasoning"]


def test_captures_tool_result():
    session = claude_code.parse(FIXTURE)
    write_call = next(
        c for t in session.turns for c in t.tool_calls
        if c.files_touched and c.files_touched[0].path == "/repo/app/middleware.py"
    )
    assert write_call.result is not None
    assert write_call.result.output == "file written"


def test_routes_py_touched_in_both_turns_write_then_fix():
    session = claude_code.parse(FIXTURE)
    events = [e for e in session.file_events() if e["file"] == "/repo/app/routes.py"]
    assert [e["turn"] for e in events] == [0, 1]
    assert events[0]["action"] == "write"
    assert events[1]["action"] == "write"


def test_end_to_end_graph_shape_matches_known_good_output():
    session = claude_code.parse(FIXTURE)
    graph = build_graph(session)
    assert len(graph["nodes"]) == 5
    assert len(graph["edges"]) == 9
    node_ids = {n["id"] for n in graph["nodes"]}
    assert node_ids == set(EXPECTED_FILES)
