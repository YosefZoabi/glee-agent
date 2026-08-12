"""Verify the key and the connection without playing a game.

`GET /api/agent/stats` is not competition-gated, so a successful response proves
the key is valid and requests are reaching the platform -- run this before the
first real session, and any time the loop starts behaving strangely.

    python tools/check_setup.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from glee_agent import config  # noqa: E402


def main() -> int:
    try:
        key = config.api_key()
    except RuntimeError as error:
        print(f"FAIL  {error}")
        return 2
    print(f"OK    key loaded ({key[:9]}...{key[-4:]})")

    try:
        from glee_sdk import GleeClient
    except ImportError:
        print("FAIL  glee-sdk is not installed. Run: pip install -r requirements.txt")
        return 2

    try:
        stats = GleeClient(api_key=key).stats()
    except Exception as error:
        print(f"FAIL  could not reach the platform: {type(error).__name__}: {error}")
        return 1

    print(f"OK    authenticated as {stats.get('agent_name')} ({stats.get('agent_id')})")
    print(f"      active games: {stats.get('active_games', 0)}")
    scores = stats.get("scores") or {}
    if not scores:
        print("      no completed games yet -- every family starts at 1000")
    for family in config.GAME_FAMILIES:
        entry = scores.get(family)
        if entry:
            # This is the display rating: shrunk toward 1000 by g/(g+30), so it
            # reads low until the game count builds up.
            print(f"      {family:<12} {entry.get('rating'):>8.1f}  ({entry.get('games_played')} games)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
