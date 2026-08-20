"""
ir.py — the agent-neutral intermediate representation (IR) that every
transcript adapter must produce and that the graph builder consumes.

An adapter's whole job is: raw agent transcript -> Session. Nothing
downstream (graph.py, render.py) knows or cares which agent produced the
Session; it only knows this shape.

    Session
      agent: str            which adapter produced this ("claude-code", "codex", ...)
      source: str            path to the original transcript, for reference
      turns: [Turn]           one per real user message, in order

    Turn
      index: int              0-based position in the session
      user_request: str|None  the user's message text that opened this turn
      assistant_responses: [str]   assistant prose seen during this turn
      tool_calls: [ToolCall]  tool invocations made during this turn, in order

    ToolCall
      call_id: str|None       adapter-native id, for matching to a result
      name: str               raw tool/function name as the agent reported it
      timestamp: str|None     ISO8601 if the source provides one
      rationale: str           the reasoning/prose text immediately preceding
                                this call — the "why" a file was touched
      files_touched: [FileTouch]
      result: ToolResult|None

    FileTouch
      path: str
      action: "read"|"write"

    ToolResult
      call_id: str|None
      output: str|None
      timestamp: str|None

This is deliberately flat and small: just enough structure to answer "which
files, why, in what order, related how" — the four questions the graph
answers. It is not a general transcript format.
"""
from dataclasses import dataclass, field


@dataclass
class FileTouch:
    path: str
    action: str  # "read" | "write"


@dataclass
class ToolResult:
    call_id: str | None
    output: str | None
    timestamp: str | None = None


@dataclass
class ToolCall:
    name: str
    rationale: str = ""
    call_id: str | None = None
    timestamp: str | None = None
    files_touched: list[FileTouch] = field(default_factory=list)
    result: ToolResult | None = None


@dataclass
class Turn:
    index: int
    user_request: str | None = None
    assistant_responses: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class Session:
    agent: str
    source: str
    turns: list[Turn] = field(default_factory=list)

    def file_events(self):
        """
        Flatten to one record per (tool_call, file_touched) pair, in
        transcript order. This is the shape graph.py actually consumes —
        adapters build the richer Turn/ToolCall structure above because
        it's what a normalized *transcript* should look like, but the graph
        only needs a flat, ordered stream of file touches.
        """
        order = 0
        for turn in self.turns:
            for call in turn.tool_calls:
                for touch in call.files_touched:
                    order += 1
                    yield {
                        "file": touch.path,
                        "action": touch.action,
                        "tool": call.name,
                        "reasoning": call.rationale,
                        "turn": turn.index,
                        "order": order,
                        "timestamp": call.timestamp,
                    }
