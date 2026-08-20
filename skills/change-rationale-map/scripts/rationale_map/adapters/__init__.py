"""
Adapter registry. Each adapter module exposes one function:

    parse(path) -> ir.Session

To add support for another coding agent, write a new adapter module with a
`parse(path)` function and register it here. See AGENTS.md for the full
checklist (what "authoritative schema" means, how to avoid guessing).
"""
from . import claude_code, codex, cursor

ADAPTERS = {
    "claude-code": claude_code.parse,
    "codex": codex.parse,
    "cursor": cursor.parse,
}
