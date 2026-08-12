"""Routes each incoming game to the strategy for its family.

This is the single function handed to `client.run()`. One queue and one loop
play all three families; the dispatcher is what makes that possible, and it is
also where the guarantee lives that we always return a legal move.
"""

from __future__ import annotations

import logging
from typing import Callable

from .gamelog import log_turn
from .safety import fallback, sanitize
from .strategies import bargaining, negotiation, persuasion

log = logging.getLogger(__name__)

STRATEGIES: dict[str, Callable[[dict], dict]] = {
    "bargaining": bargaining.play,
    "negotiation": negotiation.play,
    "persuasion": persuasion.play,
}


def play(game: dict) -> dict:
    """Choose our move for one turn of one game."""
    family = game.get("game_family")
    strategy = STRATEGIES.get(family)

    if strategy is None:
        log.warning("No strategy registered for game_family %r -- falling back.", family)
        action = fallback(game)
    else:
        try:
            action = strategy(game)
        except Exception:
            # A raised exception would otherwise become a turn timeout, which is
            # scored at the bottom of the percentile scale. Play on and debug
            # from the traceback afterwards.
            log.exception(
                "Strategy %s raised on game %s (round %s) -- falling back.",
                family,
                game.get("game_id"),
                (game.get("game_state") or {}).get("round"),
            )
            action = fallback(game)

    action = sanitize(game, action)
    log_turn(game, action)
    return action
