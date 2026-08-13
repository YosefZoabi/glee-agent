"""Bilateral trade: concede along a schedule, never below our own valuation.

The seller's payoff is `price - seller_value` and the buyer's is
`buyer_value - price`, so any price strictly between the two valuations is a
deal both sides prefer to walking away. Two regimes:

* Complete information -- both valuations are visible, so the zone of agreement
  is known exactly. We open just inside the opponent's limit and concede toward
  an even split of the surplus. If the seller values the item above the buyer
  there is no such zone, and walking away immediately is both the right outcome
  and a free concurrency slot for the next game.

* Incomplete information -- only our own valuation is visible. We anchor at a
  multiple of it and concede toward a thin margin, which is the same schedule
  with the opponent's limit replaced by a guess.

In both regimes the accept rule is the same: take the offer when it beats what
this round's schedule says we are still holding out for, and in the last rounds
take any positive profit, because a no-deal pays $0 and $0 is the bottom of the
percentile scale our rating is built from.
"""

from __future__ import annotations

from ..gamestate import (
    OPPOSITE,
    clamp,
    history,
    is_final_round,
    me as my_slot,
    messages_allowed,
    number,
    progress,
    rounds_left,
)
from ..params import NEGOTIATION as P


def _role(state: dict, slot: str) -> str:
    return state.get(f"{slot}_role") or ("seller" if slot == "player_1" else "buyer")


def _profit(role: str, price: float, my_value: float) -> float:
    return price - my_value if role == "seller" else my_value - price


def _scale(state: dict, my_value: float | None) -> float:
    """A positive number to size margins against.

    Our own valuation normally sets the scale, but some configurations draw a
    valuation of 0, and a multiple of 0 is 0. The opponent's standing offer is
    the next best hint at what this product is worth.
    """
    if my_value and my_value > 0:
        return float(my_value)
    offered = number(state.get("last_offer") or {}, "price", None)
    if offered:
        return abs(offered)
    return P.default_scale


def _target_price(state: dict, slot: str, role: str) -> float:
    """The price we are holding out for this round."""
    my_value = number(state, f"{slot}_value", 0.0) or 0.0
    opponent_value = number(state, f"{OPPOSITE[slot]}_value", None)
    # On the final round there is no schedule left to run: this price is the
    # last word, and rejecting it pays $0. A one-round game is final on round 1,
    # where `progress` is still 0 -- so ask the horizon, not the clock.
    t = 1.0 if is_final_round(state) else progress(state, P.unbounded_soft_horizon)

    if opponent_value is not None:
        # Known zone of agreement: open just inside their limit, concede to the
        # midpoint. Shading matters -- a price at exactly their valuation leaves
        # them zero profit and no reason to sign.
        span = opponent_value - my_value
        best = opponent_value - P.zopa_shade * span
        fair = (my_value + opponent_value) / 2.0
        return best + (fair - best) * t

    scale = _scale(state, my_value)
    if role == "seller":
        opening = my_value + (P.seller_open_multiple - 1.0) * scale
        floor = my_value + (P.seller_floor_multiple - 1.0) * scale
    else:
        opening = my_value - (1.0 - P.buyer_open_multiple) * scale
        floor = my_value - (1.0 - P.buyer_floor_multiple) * scale
    weight = (1.0 - t) ** P.concession_exponent
    return floor + (opening - floor) * weight


def _no_zone_of_agreement(state: dict, slot: str) -> bool:
    """True only when both valuations are visible and no price can pay both."""
    seller_value = number(state, "player_1_value", None)
    buyer_value = number(state, "player_2_value", None)
    if seller_value is None or buyer_value is None:
        return False
    return seller_value > buyer_value


def _my_last_price(game: dict, slot: str) -> float | None:
    """The last price we ourselves put on the table, if any.

    Used to keep our concessions monotone: drifting back up after conceding
    reads as bad faith and restarts the negotiation we were trying to close.
    """
    for entry in reversed(history(game)):
        for candidate in (entry.get("counteroffer"), entry.get("offer")):
            if isinstance(candidate, dict) and candidate.get("from_player") == slot:
                price = number(candidate, "price", None)
                if price is not None:
                    return price
    return None


def _bounded_price(game: dict, state: dict, slot: str, role: str, target: float) -> float:
    """Our target, clipped so it never loses money or un-concedes."""
    my_value = number(state, f"{slot}_value", 0.0) or 0.0
    previous = _my_last_price(game, slot)
    if role == "seller":
        target = max(target, my_value)          # never sell below our own value
        if previous is not None:
            target = min(target, previous)      # asks only ever come down
    else:
        target = min(target, my_value)          # never pay above our own value
        if previous is not None:
            target = max(target, previous)      # bids only ever go up
    return round(target, 2)


def _make_offer(game: dict) -> dict:
    state = game["game_state"]
    slot = my_slot(game)
    role = _role(state, slot)
    price = _bounded_price(game, state, slot, role, _target_price(state, slot, role))
    action = {"product_price": price}
    if messages_allowed(game):
        action["message"] = _offer_message(role, progress(state, P.unbounded_soft_horizon))
    return action


def _make_decision(game: dict) -> dict:
    state = game["game_state"]
    slot = my_slot(game)
    role = _role(state, slot)
    my_value = number(state, f"{slot}_value", 0.0) or 0.0
    offered = number(state.get("last_offer") or {}, "price", None)

    if _no_zone_of_agreement(state, slot):
        return {"decision": "WalkAway"}
    if offered is None:
        return {"decision": "RejectOffer"}

    gain = _profit(role, offered, my_value)
    left = rounds_left(state, P.unbounded_soft_horizon)
    final = is_final_round(state)

    # Out of road: any positive profit beats the $0 a no-deal pays.
    if final or (left is not None and left <= P.endgame_rounds):
        if gain > 0:
            return {"decision": "AcceptOffer"}
        if final:
            # No counteroffer exists on the last round; rejecting ends the game.
            return {"decision": "RejectOffer"}

    target = _target_price(state, slot, role)
    if gain >= _profit(role, target, my_value) * P.accept_slack:
        return {"decision": "AcceptOffer"}

    counter = _bounded_price(game, state, slot, role, target)
    # If our own counter would be worse for us than what is already on the
    # table, the negotiation is over -- just take the offer.
    if _profit(role, counter, my_value) <= gain:
        return {"decision": "AcceptOffer"}

    action = {"decision": "RejectOffer", "product_price": counter}
    if messages_allowed(game):
        action["message"] = _counter_message(role, progress(state, P.unbounded_soft_horizon))
    return action


def _offer_message(role: str, t: float) -> str:
    if role == "seller":
        return (
            "That is my price for this one. I would rather close now than trade "
            "rounds -- tell me if it works."
        )
    return "That is what this is worth to me. Happy to close at that number today."


def _counter_message(role: str, t: float) -> str:
    if t > 0.6:
        return "I have moved as far as this is worth to me. Let us close here."
    if role == "seller":
        return "Below my line, but here is a number I can actually sign."
    return "Above what I can justify. Here is where I can go."


def play(game: dict) -> dict:
    if (game.get("valid_actions") or {}).get("type") == "offer":
        return _make_offer(game)
    return _make_decision(game)
