from rationale_map.ir import FileTouch, Session, ToolCall, Turn


def test_file_events_flattens_in_order_across_turns_and_calls():
    session = Session(agent="test", source="x", turns=[
        Turn(index=0, tool_calls=[
            ToolCall(name="a", rationale="r1", files_touched=[FileTouch("f1.py", "write")]),
            ToolCall(name="b", rationale="r2", files_touched=[
                FileTouch("f2.py", "write"), FileTouch("f3.py", "read"),
            ]),
        ]),
        Turn(index=1, tool_calls=[
            ToolCall(name="c", rationale="r3", files_touched=[FileTouch("f1.py", "read")]),
        ]),
    ])

    events = list(session.file_events())
    assert [e["file"] for e in events] == ["f1.py", "f2.py", "f3.py", "f1.py"]
    assert [e["order"] for e in events] == [1, 2, 3, 4]
    assert [e["turn"] for e in events] == [0, 0, 0, 1]
    assert events[1]["action"] == "write"
    assert events[2]["action"] == "read"
    assert events[3]["reasoning"] == "r3"


def test_file_events_empty_session():
    assert list(Session(agent="test", source="x").file_events()) == []
