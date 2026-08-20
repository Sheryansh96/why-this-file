from pathlib import Path

from rationale_map.adapters import codex
from rationale_map.graph import build_graph

FIXTURE = Path(__file__).parent.parent / "samples" / "sample_transcript_codex.jsonl"

EXPECTED_FILES = [
    "app/config.py",
    "app/middleware.py",
    "app/routes.py",
    "app/app_init.py",
    "tests/test_rate_limit.py",
]


def test_parses_apply_patch_touches_as_writes():
    session = codex.parse(FIXTURE)
    assert session.agent == "codex"
    events = list(session.file_events())
    apply_patch_events = [e for e in events if e["tool"] == "apply_patch"]
    assert {e["file"] for e in apply_patch_events} == set(EXPECTED_FILES)
    assert all(e["action"] == "write" for e in apply_patch_events)


def test_shell_cat_before_the_edit_is_captured_as_a_read():
    # the session opens with `cat app/config.py` (a shell_command call, no
    # apply_patch) before ever editing it — the shell-idiom fallback should
    # pick that up as a read touch on the same file.
    session = codex.parse(FIXTURE)
    events = list(session.file_events())
    read = next(e for e in events if e["file"] == "app/config.py" and e["action"] == "read")
    assert read["tool"] == "shell_command"


def test_rationale_comes_from_reasoning_summary():
    session = codex.parse(FIXTURE)
    events = list(session.file_events())
    write_touch = next(e for e in events if e["file"] == "app/config.py" and e["action"] == "write")
    assert "RATE_LIMIT_DEFAULT" in write_touch["reasoning"]


def test_captures_tool_result():
    session = codex.parse(FIXTURE)
    call = next(
        c for t in session.turns for c in t.tool_calls
        if c.files_touched and c.files_touched[0].path == "app/middleware.py"
    )
    assert call.result is not None
    assert "app/middleware.py" in call.result.output


def test_single_turn_since_fixture_has_one_user_message():
    session = codex.parse(FIXTURE)
    assert len(session.turns) == 1
    assert "rate limiting" in session.turns[0].user_request


def test_graph_shape_matches_claude_code_adapter_on_the_same_scenario():
    # different transcript format, same underlying rate-limiting scenario —
    # the graphs should agree on which files were touched.
    session = codex.parse(FIXTURE)
    graph = build_graph(session)
    node_ids = {n["id"] for n in graph["nodes"]}
    assert node_ids == set(EXPECTED_FILES)


def test_shell_command_without_apply_patch_or_recognized_write_idiom_yields_no_touch(tmp_path):
    import json
    line = {
        "timestamp": "2026-01-01T00:00:00Z", "type": "response_item",
        "payload": {"type": "function_call", "name": "shell_command",
                     "arguments": json.dumps({"command": ["bash", "-lc", "pytest -q"]}),
                     "call_id": "call_x"},
    }
    user_line = {
        "timestamp": "2026-01-01T00:00:00Z", "type": "response_item",
        "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "run tests"}]},
    }
    f = tmp_path / "rollout.jsonl"
    f.write_text(json.dumps(user_line) + "\n" + json.dumps(line) + "\n")
    session = codex.parse(f)
    assert list(session.file_events()) == []
