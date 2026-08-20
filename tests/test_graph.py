from rationale_map.graph import _build_graph_from_touches, clean_reasoning, short_name


def test_short_name():
    assert short_name("/repo/app/config.py") == "config.py"
    assert short_name(None) is None


def test_clean_reasoning_collapses_whitespace_and_truncates():
    assert clean_reasoning("a   b\nc") == "a b c"
    long_text = "word " * 100
    out = clean_reasoning(long_text, max_len=20)
    assert len(out) <= 20
    assert out.endswith("…")


def _touch(file, action, turn, order, reasoning="", tool="Edit"):
    return {"file": file, "action": action, "turn": turn, "order": order, "reasoning": reasoning, "tool": tool}


def test_nodes_aggregate_touches_per_file():
    touches = [
        _touch("a.py", "write", 0, 1, "add a"),
        _touch("b.py", "write", 0, 2, "add b, references a.py"),
        _touch("a.py", "read", 1, 3, "check a again"),
    ]
    graph = _build_graph_from_touches(touches)
    by_id = {n["id"]: n for n in graph["nodes"]}
    assert set(by_id) == {"a.py", "b.py"}
    assert by_id["a.py"]["touch_count"] == 2
    assert by_id["a.py"]["actions"] == ["read", "write"]
    assert by_id["a.py"]["turns"] == [0, 1]
    assert [t["reasoning"] for t in by_id["a.py"]["timeline"]] == ["add a", "check a again"]


def test_node_with_no_reasoning_gets_placeholder():
    graph = _build_graph_from_touches([_touch("a.py", "write", 0, 1, "")])
    assert graph["nodes"][0]["rationale"] == "(no explicit reasoning captured before this tool call)"


def test_same_turn_edge_between_consecutive_files_in_a_turn():
    touches = [
        _touch("a.py", "write", 0, 1),
        _touch("b.py", "write", 0, 2),
        _touch("c.py", "write", 0, 3),
    ]
    graph = _build_graph_from_touches(touches)
    same_turn = [e for e in graph["edges"] if e["type"] == "same-turn"]
    assert {(e["source"], e["target"]) for e in same_turn} == {("a.py", "b.py"), ("b.py", "c.py")}


def test_reference_edge_when_reasoning_mentions_another_files_basename():
    touches = [
        _touch("app/a.py", "write", 0, 1, "created a.py"),
        _touch("app/b.py", "write", 1, 2, "wire in a.py here"),
    ]
    graph = _build_graph_from_touches(touches)
    ref = [e for e in graph["edges"] if e["type"] == "referenced"]
    assert ref == [{"source": "app/a.py", "target": "app/b.py", "type": "referenced", "weight": 1}]


def test_repeated_touch_of_same_file_in_a_turn_does_not_self_loop():
    touches = [
        _touch("a.py", "write", 0, 1),
        _touch("a.py", "write", 0, 2),
    ]
    graph = _build_graph_from_touches(touches)
    assert graph["edges"] == []
