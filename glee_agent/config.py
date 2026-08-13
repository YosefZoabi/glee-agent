"""Environment configuration. No secrets in source, ever."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
LOG_DIR = PROJECT_ROOT / "logs"

GAME_FAMILIES = ("bargaining", "negotiation", "persuasion")
BASE_URL = "https://glee-competition.com"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Populate os.environ from a .env file. Real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def api_key() -> str:
    load_env_file()
    key = os.environ.get("GLEE_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GLEE_API_KEY is not set. Create a .env file next to main.py containing "
            "one line -- GLEE_API_KEY=glee_... -- using the key from your dashboard "
            "at https://glee-competition.com/dashboard (shown once at creation; "
            "reset it from the agent's card if it is lost). .env is gitignored."
        )
    if not key.startswith("glee_"):
        raise RuntimeError("GLEE_API_KEY does not look like a GLEE key -- expected a 'glee_' prefix.")
    return key
