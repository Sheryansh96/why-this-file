"""
Tests for the adapter boundary itself: every registered adapter must accept
a path and return an ir.Session, regardless of source format. This is what
lets graph.py and render.py stay agent-neutral.
"""
from pathlib import Path

import pytest

from rationale_map.adapters import ADAPTERS
from rationale_map.ir import Session

SAMPLES = Path(__file__).parent.parent / "samples"
FIXTURE_BY_AGENT = {
    "claude-code": SAMPLES / "sample_transcript_claude.jsonl",
    "codex": SAMPLES / "sample_transcript_codex.jsonl",
    "cursor": SAMPLES / "sample_transcript_cursor.json",
}


def test_every_adapter_has_a_fixture():
    assert set(ADAPTERS) == set(FIXTURE_BY_AGENT)


@pytest.mark.parametrize("agent", sorted(ADAPTERS))
def test_adapter_returns_a_session_with_the_right_agent_tag(agent):
    parse = ADAPTERS[agent]
    session = parse(FIXTURE_BY_AGENT[agent])
    assert isinstance(session, Session)
    assert session.agent == agent


@pytest.mark.parametrize("agent", sorted(ADAPTERS))
def test_adapter_file_events_have_the_required_shape(agent):
    parse = ADAPTERS[agent]
    session = parse(FIXTURE_BY_AGENT[agent])
    events = list(session.file_events())
    assert events, f"{agent} adapter found no file touches in its fixture"
    for e in events:
        assert set(e) == {"file", "action", "tool", "reasoning", "turn", "order", "timestamp"}
        assert e["action"] in ("read", "write")
        assert isinstance(e["turn"], int)
        assert isinstance(e["order"], int)
