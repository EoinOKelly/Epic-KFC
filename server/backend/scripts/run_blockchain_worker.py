"""Run the backend blockchain anchor worker.

Usage:
    .venv/bin/python scripts/run_blockchain_worker.py
    .venv/bin/python scripts/run_blockchain_worker.py --once
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.workers.blockchain_worker import main


if __name__ == "__main__":
    asyncio.run(main())
