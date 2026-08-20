"""
adapters/cursor.py — parse a Cursor IDE chat export into the normalized IR.

UNVERIFIED, unlike adapters/codex.py: Cursor does not write a plain,
documented transcript file. Chat data lives inside SQLite databases
(state.vscdb, keyed by bubbleId:{composerId}:{bubbleId} in cursorDiskKV),
the schema isn't officially documented, and it has already changed at least
once across Cursor versions. There is no first-party export and no local
installation of Cursor was available to inspect real data against, so this
adapter is a best-effort guess at the JSON/JSONL output of the community
`cursor-session` export tool (github.com/iksnae/cursor-session), which reads
that SQLite data. It tries several plausible field names defensively rather
than assuming one exact shape.

If it misses touches on a real export: open the export in a text editor,
find the actual key names for role/text/tool-call/file-path, and adjust the
CANDIDATE_* lists below. That's a five-minute edit, not a rewrite.

Expected input shape (a JSON array of "bubble" objects, or {"bubbles": [...]}):
    {
      "bubbleId": "...",
      "type": 1 | 2,              # 1 = user, 2 = assistant (common convention;
                                   # some exports normalize this to "role" instead)
      "text": "...",               # message / reasoning text
      "toolFormerData": {          # present on assistant bubbles that called a tool
        "name": "edit_file" | "write" | ...,
        "params": { "target_file": "...", ... }   # or "rawArgs", "path", etc.
      }
    }
"""
import json

from ..ir import FileTouch, Session, ToolCall, Turn

CANDIDATE_ROLE_KEYS = ["role", "type"]
CANDIDATE_TEXT_KEYS = ["text", "content", "message"]
CANDIDATE_TOOLDATA_KEYS = ["toolFormerData", "toolCall", "tool_call", "toolCalls"]
CANDIDATE_TOOLNAME_KEYS = ["name", "toolName", "tool"]
CANDIDATE_PARAMS_KEYS = ["params", "args", "rawArgs", "arguments", "input"]
CANDIDATE_FILEPATH_KEYS = ["target_file", "file_path", "filePath", "path", "relative_path", "relativePath"]
WRITE_TOOL_NAMES = {"edit_file", "write", "write_file", "create_file", "apply_diff", "search_replace"}
READ_TOOL_NAMES = {"read_file", "view_file", "list_dir"}


def load_export(path):
    with open(path, "r") as f:
        text = f.read().strip()
    if not text:
        return []
    data = json.loads(text)
    if isinstance(data, dict):
        for key in ("bubbles", "messages", "conversation"):
            if key in data and isinstance(data[key], list):
                return data[key]
        for v in data.values():
            if isinstance(v, list):
                return v
        return []
    if isinstance(data, list):
        return data
    return []


def _first_present(d, keys):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _is_user_bubble(bubble):
    role = _first_present(bubble, CANDIDATE_ROLE_KEYS)
    if role in ("user", 1, "1"):
        return True
    if role in ("assistant", 2, "2"):
        return False
    return None


def parse(path) -> Session:
    bubbles = load_export(path)
    session = Session(agent="cursor", source=str(path))
    turn = None

    for bubble in bubbles:
        if not isinstance(bubble, dict):
            continue

        role_is_user = _is_user_bubble(bubble)
        text = _first_present(bubble, CANDIDATE_TEXT_KEYS)
        text = text if isinstance(text, str) else None

        if role_is_user:
            turn = Turn(index=len(session.turns), user_request=text)
            session.turns.append(turn)
            continue
        if turn is None:
            turn = Turn(index=0)
            session.turns.append(turn)
        if text:
            turn.assistant_responses.append(text)

        tool_data = _first_present(bubble, CANDIDATE_TOOLDATA_KEYS)
        if not tool_data:
            continue
        tool_calls = tool_data if isinstance(tool_data, list) else [tool_data]

        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            tool_name = _first_present(call, CANDIDATE_TOOLNAME_KEYS) or ""
            params = _first_present(call, CANDIDATE_PARAMS_KEYS)
            fpath = (
                _first_present(params, CANDIDATE_FILEPATH_KEYS) if isinstance(params, dict) else None
            ) or _first_present(call, CANDIDATE_FILEPATH_KEYS)
            if not fpath:
                continue
            action = "write" if tool_name in WRITE_TOOL_NAMES else (
                "read" if tool_name in READ_TOOL_NAMES else "write"
            )
            turn.tool_calls.append(ToolCall(
                name=tool_name or "unknown",
                rationale=text or "",
                files_touched=[FileTouch(path=fpath, action=action)],
            ))

    return session
