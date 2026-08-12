"""Small readers over the `game` dict the platform hands us.

`game_state` is filtered to our own view, so any field we are not entitled to
see (the opponent's inflation rate, their valuation, this round's quality) is
simply absent rather than null. Every reader here tolerates that.
"""

from __future__ import annotations

from typing import Any, Iterable

OPPOSITE = {"player_1": "player_2", "player_2": "player_1"}


def me(game: dict) -> str:
    """The player slot we are acting as: "player_1" or "player_2"."""
    state = game.get("game_state") or {}
    return state.get("current_player") or game.get("your_player") or "player_1"


def opponent_slot(game: dict) -> str:
    return OPPOSITE.get(me(game), "player_2")


def action_type(game: dict) -> str:
    return ((game.get("valid_actions") or {}).get("type")) or ""


def messages_allowed(game: dict) -> bool:
    return bool((game.get("game_state") or {}).get("messages_allowed"))


def history(game: dict) -> list[dict]:
    entries = (game.get("game_state") or {}).get("history")
    return list(entries) if isinstance(entries, Iterable) and not isinstance(entries, (str, bytes)) else []


def number(state: dict, key: str, default: float | None = None) -> float | None:
    """Read a numeric field, treating absent/None/unparseable alike."""
    value = state.get(key, None)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def rounds_left(state: dict, soft_horizon: int) -> int | None:
    """Rounds remaining including the current one, or None if unbounded.

    `horizon_known` is false for open-ended games, where `max_rounds` is absent.
    Callers that need a finite number for a concession schedule pass their own
    `soft_horizon`; callers doing backward induction want the None.
    """
    if not state.get("horizon_known", False):
        return None
    max_rounds = number(state, "max_rounds")
    if max_rounds is None:
        return None
    current = number(state, "round", 1) or 1
    return max(1, int(max_rounds) - int(current) + 1)


def progress(state: dict, soft_horizon: int) -> float:
    """How far through the game we are, in [0, 1).

    Drives every concession schedule. Open-ended games are measured against
    `soft_horizon` instead, since inflation makes stalling forever pointless
    even when the rules permit it.
    """
    current = number(state, "round", 1) or 1
    max_rounds = number(state, "max_rounds") if state.get("horizon_known", False) else None
    horizon = max_rounds if max_rounds and max_rounds > 0 else soft_horizon
    return clamp((current - 1) / max(1.0, float(horizon)), 0.0, 1.0)


def is_final_round(state: dict) -> bool:
    left = rounds_left(state, 0)
    return left is not None and left <= 1


def clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def split_exactly(total: float, my_fraction: float) -> tuple[Any, Any]:
    """Split `total` so the two gains sum to it exactly.

    Bargaining offers are rejected as invalid unless the gains sum to
    `money_to_divide`, so integral pots are split in integers and the residue of
    a fractional split is absorbed on our own side rather than re-rounded.
    """
    my_fraction = clamp(my_fraction, 0.0, 1.0)
    if float(total).is_integer():
        whole = int(round(total))
        mine = int(round(whole * my_fraction))
        mine = max(0, min(whole, mine))
        return mine, whole - mine
    theirs = round(total * (1.0 - my_fraction), 2)
    theirs = clamp(theirs, 0.0, total)
    return total - theirs, theirs
