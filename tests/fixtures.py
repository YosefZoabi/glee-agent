"""Builders for the `game` dicts the platform sends us.

Field names follow the documented payloads. Anything a player is not entitled to
see is left out entirely rather than set to None, which is how the real server
filters state -- so tests exercise the same absent-field paths as live play.
"""

from __future__ import annotations


def bargaining_game(
    *,
    action_type="offer",
    slot="player_1",
    money=1000,
    round_=1,
    max_rounds=6,
    delta_1=0.9,
    delta_2=0.9,
    complete_information=True,
    messages_allowed=True,
    last_offer=None,
    history=None,
):
    state = {
        "phase": "offer" if action_type == "offer" else "decision",
        "current_player": slot,
        "proposer": slot if action_type == "offer" else ("player_2" if slot == "player_1" else "player_1"),
        "round": round_,
        "money_to_divide": money,
        "delta_1": delta_1,
        "horizon_known": max_rounds is not None,
        "complete_information": complete_information,
        "messages_allowed": messages_allowed,
        "last_offer": last_offer,
        "history": history or [],
    }
    if max_rounds is not None:
        state["max_rounds"] = max_rounds
    if complete_information or slot == "player_2":
        state["delta_2"] = delta_2
    if not complete_information:
        # Only our own inflation rate is visible.
        state.pop("delta_2" if slot == "player_1" else "delta_1", None)
    return {
        "game_id": "test-bargaining",
        "game_family": "bargaining",
        "your_player": slot,
        "phase": state["phase"],
        "opponent": {"type": "hidden", "name": None},
        "game_state": state,
        "valid_actions": {"type": action_type, "fields": {}},
        "prompt": "test",
    }


def negotiation_game(
    *,
    action_type="offer",
    slot="player_1",
    my_value=40.0,
    opponent_value=None,
    round_=1,
    max_rounds=6,
    messages_allowed=True,
    last_offer=None,
    history=None,
):
    other = "player_2" if slot == "player_1" else "player_1"
    state = {
        "phase": "offer" if action_type == "offer" else "decision",
        "current_player": slot,
        "player_1_role": "seller",
        "player_2_role": "buyer",
        f"{slot}_value": my_value,
        "round": round_,
        "horizon_known": max_rounds is not None,
        "complete_information": opponent_value is not None,
        "messages_allowed": messages_allowed,
        "last_offer": last_offer,
        "history": history or [],
    }
    if max_rounds is not None:
        state["max_rounds"] = max_rounds
    if opponent_value is not None:
        state[f"{other}_value"] = opponent_value
    return {
        "game_id": "test-negotiation",
        "game_family": "negotiation",
        "your_player": slot,
        "phase": state["phase"],
        "opponent": {"type": "agent", "name": "Rival"},
        "game_state": state,
        "valid_actions": {"type": action_type, "fields": {}},
        "prompt": "test",
    }


def persuasion_game(
    *,
    action_type="buyer_decision",
    slot="player_2",
    p=0.5,
    v=100.0,
    u=0.0,
    price=60.0,
    round_=1,
    total_rounds=10,
    quality=None,
    seller_message=None,
    seller_knows_values=True,
    history=None,
):
    state = {
        "phase": "buyer_decision" if action_type == "buyer_decision" else "seller_message",
        "current_player": slot,
        "product_price": price,
        "p": p,
        "round": round_,
        "total_rounds": total_rounds,
        "seller_message_type": "text" if action_type == "seller_message" else "binary",
        "history": history or [],
        "seller_total_payoff": 0,
        "buyer_total_payoff": 0,
    }
    # The buyer always knows v and u; the seller only when configured to.
    if slot == "player_2" or seller_knows_values:
        state["v"] = v
        state["u"] = u
    if slot == "player_1" and quality is not None:
        state["current_quality"] = quality       # seller only
    if seller_message is not None:
        state["seller_message"] = seller_message
    return {
        "game_id": "test-persuasion",
        "game_family": "persuasion",
        "your_player": slot,
        "phase": state["phase"],
        "opponent": {"type": "human", "name": "someone"},
        "game_state": state,
        "valid_actions": {"type": action_type, "fields": {}},
        "prompt": "test",
    }


def persuasion_round(*, round_, message, bought, quality=None):
    """One entry of a persuasion history. Quality is revealed only on a purchase."""
    entry = {
        "round": round_,
        "seller_message": message,
        "buyer_decision": "yes" if bought else "no",
        "bought": bought,
        "seller_payoff": 0,
        "buyer_payoff": 0,
    }
    if bought and quality is not None:
        entry["quality"] = quality
    return entry
