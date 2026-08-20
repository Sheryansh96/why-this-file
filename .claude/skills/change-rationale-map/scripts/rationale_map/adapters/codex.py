"""
adapters/codex.py — parse an OpenAI Codex CLI session rollout
(~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl) into the normalized IR.

Schema below was verified against real rollout files produced by installed
Codex CLI versions 0.39.0 through 0.70.0-alpha.4 (inspected directly, not
guessed from docs — Codex CLI ships no formal transcript schema doc). It
changed once in that range, and this adapter handles both shapes:

Every line: {"timestamp": <iso8601>, "type": <str>, "payload": {...}}

Top-level `type`:
    session_meta    one-time header (cwd, cli_version, git info) — ignored
    turn_context    per-turn sandbox/model metadata — ignored
    event_msg       a duplicate, UI-facing stream (payload.type one of
                     token_count/agent_reasoning/agent_message/user_message/
                     turn_aborted) that mirrors response_item content for
                     display purposes — ignored; response_item is authoritative
    response_item   the actual conversation content — payload.type is:
        "message"                  role user/assistant, content is a list of
                                    {"type": "input_text"|"output_text", "text"}
        "reasoning"                assistant chain-of-thought; payload.summary
                                    is a list of {"type","text"} — this is
                                    often the *only* prose Codex emits before
                                    a tool call, so it's treated as rationale
                                    text exactly like an assistant message
        "function_call"            payload.name (seen: "shell", "shell_command",
                                    "update_plan"), payload.arguments (a JSON
                                    string), payload.call_id
        "function_call_output"     tool result, payload.call_id + payload.output
        "custom_tool_call"         payload.name (seen: "apply_patch"),
                                    payload.call_id, payload.input — this is
                                    the RAW patch text, not JSON-encoded
                                    (unlike function_call's arguments)
        "custom_tool_call_output"  tool result, payload.call_id + payload.output
        "ghost_snapshot"           internal git snapshot bookkeeping — ignored

File-touch detection, in order of reliability:
    1. custom_tool_call named "apply_patch": its own patch format
       ("*** Update File: ...", "*** Add File: ...", "*** Delete File: ...")
       is unambiguous.
    2. function_call named "shell"/"shell_command"/"exec_command"/"bash"/
       "local_shell": no dedicated edit tool, so file touches are inferred
       from common shell write idioms (sed -i, cat >, tee, mv, cp). This is
       best-effort — a session that edits files through an unrecognized
       shell pattern won't show up here.
"""
import json
import re

from ..ir import FileTouch, Session, ToolCall, ToolResult, Turn

PATCH_FILE_RE = re.compile(r"^\*\*\* (Update|Add|Delete) File: (.+)$", re.MULTILINE)
SHELL_WRITE_RE = re.compile(
    r"(?:sed -i[^\s]*\s+\S+\s+|>>?\s*|tee\s+(?:-a\s+)?|mv\s+\S+\s+|cp\s+\S+\s+)([^\s|;&<>]+\.\w+)"
)
SHELL_READ_RE = re.compile(r"\b(?:cat|less|head|tail)\s+([^\s|;&<>]+\.\w+)")
SHELL_TOOL_NAMES = {"shell", "shell_command", "exec_command", "bash", "local_shell"}


def load_rollout(path):
    lines = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return lines


def _decode_shell_arguments(args_str):
    try:
        parsed = json.loads(args_str)
    except (json.JSONDecodeError, TypeError):
        return args_str if isinstance(args_str, str) else ""
    if isinstance(parsed, dict) and "command" in parsed:
        cmd = parsed["command"]
        return " ".join(cmd) if isinstance(cmd, list) else str(cmd)
    return args_str if isinstance(args_str, str) else ""


def _touches_from_apply_patch(patch_text):
    return [
        FileTouch(path=fpath.strip(), action="write")
        for _action_word, fpath in PATCH_FILE_RE.findall(patch_text or "")
    ]


def _touches_from_shell(args_str):
    text = _decode_shell_arguments(args_str)
    out = [FileTouch(path=m.strip(), action="write") for m in SHELL_WRITE_RE.findall(text)]
    if not out:
        m = SHELL_READ_RE.search(text)
        if m:
            out.append(FileTouch(path=m.group(1), action="read"))
    return out


def _message_text(payload):
    texts = []
    for block in payload.get("content", []) or []:
        if isinstance(block, dict) and block.get("type") in ("input_text", "output_text", "text"):
            texts.append(block.get("text", ""))
    return " ".join(t for t in texts if t)


def _reasoning_text(payload):
    texts = []
    for block in payload.get("summary", []) or []:
        if isinstance(block, dict):
            texts.append(block.get("text", ""))
    return " ".join(t for t in texts if t)


def parse(path) -> Session:
    raw_lines = load_rollout(path)

    results_by_id = {}
    for raw in raw_lines:
        if raw.get("type") != "response_item":
            continue
        payload = raw.get("payload", {})
        if payload.get("type") in ("function_call_output", "custom_tool_call_output"):
            call_id = payload.get("call_id")
            results_by_id[call_id] = ToolResult(
                call_id=call_id,
                output=payload.get("output"),
                timestamp=raw.get("timestamp"),
            )

    session = Session(agent="codex", source=str(path))
    turn = None
    pending_reasoning = ""

    for raw in raw_lines:
        if raw.get("type") != "response_item":
            continue
        payload = raw.get("payload", {})
        ptype = payload.get("type")
        timestamp = raw.get("timestamp")

        if ptype == "message":
            role = payload.get("role")
            text = _message_text(payload)
            if role == "user":
                turn = Turn(index=len(session.turns), user_request=text or None)
                session.turns.append(turn)
            elif role == "assistant":
                if turn is None:
                    turn = Turn(index=0)
                    session.turns.append(turn)
                if text:
                    turn.assistant_responses.append(text)
                    pending_reasoning = text
            continue

        if ptype == "reasoning":
            text = _reasoning_text(payload)
            if text:
                pending_reasoning = text
            continue

        if ptype not in ("function_call", "custom_tool_call"):
            continue
        if turn is None:
            turn = Turn(index=0)
            session.turns.append(turn)

        name = payload.get("name", "")
        call_id = payload.get("call_id")
        files_touched = []
        if ptype == "custom_tool_call" and name == "apply_patch":
            files_touched = _touches_from_apply_patch(payload.get("input", ""))
        elif ptype == "function_call" and name in SHELL_TOOL_NAMES:
            files_touched = _touches_from_shell(payload.get("arguments", ""))
        if not files_touched:
            continue

        turn.tool_calls.append(ToolCall(
            name=name,
            call_id=call_id,
            timestamp=timestamp,
            rationale=pending_reasoning,
            files_touched=files_touched,
            result=results_by_id.get(call_id),
        ))

    return session
