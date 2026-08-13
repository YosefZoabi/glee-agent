"""Append-only JSONL record of every turn we play.

Worth having from the first game. Tuning needs evidence about what the field
actually does rather than what we assumed it would do, and the workshop paper
requires an "Agent Behavior Analysis" section arguing that the agent behaved the
way it was designed to -- which is a claim about logs.

One JSON object per turn, so a partially-written run is still readable and the
file can be appended to from several concurrent games without a lock.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from .config import LOG_DIR

log = logging.getLogger(__name__)

_lock = threading.Lock()
_turn_log_path: Path | None = None

# State fields worth keeping per family: enough to replay the decision without
# storing the full prompt text on every turn.
_KEEP = (
    "round", "max_rounds", "total_rounds", "horizon_known", "phase",
    "money_to_divide", "delta_1", "delta_2", "last_offer",
    # Who proposes this round. Without it the endgame-sweep conditions cannot be
    # reconstructed from the log at all, since the whole rule turns on parity.
    "proposer", "current_player",
    "player_1_role", "player_2_role", "player_1_value", "player_2_value",
    "p", "v", "u", "product_price", "current_quality", "seller_message_type",
    # The buyer's whole decision turns on this. Leaving it out made every game
    # look like a silent seller in the logs and sent one post-mortem chasing the
    # wrong fix; the seller had said "yes" on all twenty rounds.
    "seller_message",
    "complete_information", "messages_allowed",
    "seller_total_payoff", "buyer_total_payoff",
)


def configure(path: Path | None = None) -> Path:
    """Point the log at a file. Defaults to logs/turns-<UTC date>.jsonl."""
    global _turn_log_path
    if path is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        path = LOG_DIR / f"turns-{stamp}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    _turn_log_path = path
    return path


def log_turn(game: dict, action: dict) -> None:
    """Record one decision. Never raises -- logging must not cost us a game."""
    if _turn_log_path is None:
        return
    try:
        state = game.get("game_state") or {}
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "game_id": game.get("game_id"),
            "game_family": game.get("game_family"),
            "your_player": game.get("your_player"),
            "phase": game.get("phase"),
            "action_type": (game.get("valid_actions") or {}).get("type"),
            "opponent": game.get("opponent"),
            "state": {key: state[key] for key in _KEEP if key in state},
            "history_length": len(state.get("history") or []),
            "action": action,
        }
        line = json.dumps(record, default=str, ensure_ascii=False)
        with _lock:
            with _turn_log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except Exception:  # pragma: no cover - logging must never break play
        log.debug("Failed to write turn log", exc_info=True)
