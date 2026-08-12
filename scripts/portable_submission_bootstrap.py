"""Initialize the mutable runtime for the Windows portable submission."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.container_submission_bootstrap import bootstrap


if __name__ == "__main__":
    bootstrap()
