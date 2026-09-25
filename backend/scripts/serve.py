"""Launcher used by the launchd agent (ops/co.soclose.elninowatch.plist).

Why not `uv run uvicorn ...` directly: macOS privacy protection (TCC) blocks a
launchd-spawned process from ~/Documents unless that exact binary was granted
access. uv (and uv's own Python) were not, so launchd failed with EX_CONFIG
before the app started. Homebrew's Python already holds that grant on this Mac,
so the agent runs this file with a venv built on it (outside Documents, see
start.sh), and this launcher does the chdir + log redirection itself.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def main() -> None:
    (ROOT / "data").mkdir(exist_ok=True)
    log = open(ROOT / "data" / "elnino.log", "ab", buffering=0)  # noqa: SIM115 -- lives with the process
    os.dup2(log.fileno(), 1)
    os.dup2(log.fileno(), 2)
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    import uvicorn

    port = int(os.environ.get("PORT", "8911"))
    uvicorn.run("app.main:app", host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
