#!/usr/bin/env python3
"""
cli.py — repo-root entry point. Run this from anywhere; it finds the
rationale_map package relative to this file, so no PYTHONPATH or install
step is required.

    ./cli.py extract --agent claude-code samples/sample_transcript_claude.jsonl -o graph.json
    ./cli.py render graph.json -o map.html -t "my session"
    ./cli.py map --agent codex samples/sample_transcript_codex.jsonl -o map.html

See AGENTS.md for the full picture.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rationale_map.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
