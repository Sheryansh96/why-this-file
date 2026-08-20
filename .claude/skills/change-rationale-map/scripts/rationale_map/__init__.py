"""
rationale_map — agent-neutral core for the Change Rationale Map project.

    adapters/*.py   agent-specific transcript -> ir.Session parsers
    ir.py           the normalized intermediate representation
    graph.py        ir.Session -> Change Rationale Graph (agent-neutral)
    render.py       graph -> standalone HTML (agent-neutral)
    cli.py          `rationale-map extract|render|map`

See AGENTS.md at the repo root for the full architecture writeup.
"""
__version__ = "0.2.0"
