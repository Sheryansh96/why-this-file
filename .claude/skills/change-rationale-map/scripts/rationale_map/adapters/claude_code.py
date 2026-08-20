"""
adapters/claude_code.py — parse a Claude Code session transcript
(~/.claude/projects/*.jsonl) into the normalized IR (see ir.py).

Transcript shape: each line is
    {"type": "user"|"assistant", "message": {"role", "content": [...]}, "timestamp": ...}
Assistant content blocks are {"type": "text", ...} (reasoning/prose) or
{"type": "tool_use", "id", "name", "input"} (a tool call). Tool results
come back as a *user*-role message whose content is a single
{"type": "tool_result", "tool_use_id", "content"} block.

A real user message (not a tool_result) starts a new turn.
"""
import json

from ..ir import FileTouch, Session, ToolCall, ToolResult, Turn

FILE_TOOLS = {"Edit", "Write", "MultiEdit", "Read", "NotebookEdit"}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def load_transcript(path):
    events = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def _file_path(tool_input):
    if not isinstance(tool_input, dict):
        return None
    return tool_input.get("file_path") or tool_input.get("notebook_path")


def _is_tool_result_only(content):
    return isinstance(content, list) and len(content) > 0 and all(
        isinstance(b, dict) and b.get("type") == "tool_result" for b in content
    )


def parse(path) -> Session:
    raw_events = load_transcript(path)

    # first pass: collect tool_result content keyed by tool_use_id, since
    # results arrive as a later, separate message.
    results_by_id = {}
    for raw in raw_events:
        msg = raw.get("message", {})
        if msg.get("role") != "user":
            continue
        for block in msg.get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                content = block.get("content")
                if not isinstance(content, str):
                    content = json.dumps(content) if content is not None else None
                results_by_id[block.get("tool_use_id")] = ToolResult(
                    call_id=block.get("tool_use_id"),
                    output=content,
                    timestamp=raw.get("timestamp"),
                )

    session = Session(agent="claude-code", source=str(path))
    turn = None
    # Persists across assistant messages within a turn, not just within one
    # message: real sessions routinely narrate in one assistant message
    # ("Let me look at X...") and then issue tool calls in several
    # subsequent, text-free assistant messages — text and tool_use rarely
    # share a single message the way the original hand-written sample
    # fixture assumed. Resetting this per-message (as an earlier version of
    # this adapter did) silently dropped almost all rationale on real
    # transcripts. It only resets at a turn boundary (a new user message).
    pending_reasoning = ""

    for raw in raw_events:
        msg = raw.get("message", {})
        role = msg.get("role")
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue

        if role == "user" and not _is_tool_result_only(content):
            text = " ".join(
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
            turn = Turn(index=len(session.turns), user_request=text or None)
            session.turns.append(turn)
            pending_reasoning = ""
            continue

        if role != "assistant":
            continue
        if turn is None:
            turn = Turn(index=0)
            session.turns.append(turn)

        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                pending_reasoning = block.get("text", "")
                turn.assistant_responses.append(pending_reasoning)
            elif btype == "tool_use":
                name = block.get("name")
                if name not in FILE_TOOLS:
                    continue
                fpath = _file_path(block.get("input", {}))
                if not fpath:
                    continue
                call_id = block.get("id")
                turn.tool_calls.append(ToolCall(
                    name=name,
                    call_id=call_id,
                    timestamp=raw.get("timestamp"),
                    rationale=pending_reasoning,
                    files_touched=[FileTouch(
                        path=fpath,
                        action="write" if name in WRITE_TOOLS else "read",
                    )],
                    result=results_by_id.get(call_id),
                ))

    return session
