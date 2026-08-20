"""Make `import rationale_map` work under pytest without an install step."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
