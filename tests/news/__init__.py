"""Deterministic offline news backend tests; no provider requests."""
from pathlib import Path
import sys

# Match the standalone legacy runner, including execution from outside the root.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
