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
from ..params import NEGOTIATION as P, SEND_MESSAGES


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


def _their_prices(state: dict, slot: str) -> list[float]:
    """Every price they have put to us, oldest first."""
    by_round: dict[int, float] = {}
    for entry in list(state.get("history") or []) + [{"offer": state.get("last_offer") or {}}]:
        offer = entry.get("offer") or {}
        sender = offer.get("from_player")
        if not sender or sender == slot:
            continue
        price = number(offer, "price", None)
        if price is not None:
            by_round[int(offer.get("round") or entry.get("round") or 0)] = price
    return [by_round[r] for r in sorted(by_round)]


def opponent_has_stopped_moving(state: dict, slot: str) -> bool:
    """Has their price been literally unchanged for `stonewall_offers` offers?

    Not "barely moving" -- unchanged to the cent. Games 85bd702f and 3ee13da4
    are the same configuration, the same opening, and the same 900,000 hold by
    us, and they end 0 and 100,000. The only thing that separates them is that
    one buyer sat on 815,000 from round 2 to round 99 while the other crept
    806,000 -> 810,937 and then paid our price at round 69. A tolerance wide
    enough to call the second one flat would have sold that game for 10,937.
    """
    prices = _their_prices(state, slot)
    if len(prices) < P.stonewall_offers:
        return False
    return len(set(prices[-P.stonewall_offers:])) == 1


# Valuations are drawn from four rungs on one of three scales. See
# `rung_aware` in params for the evidence; this is just the arithmetic.
RUNG_SHAPE = (80.0, 100.0, 120.0, 150.0)
RUNG_SCALES = (1.0, 100.0, 10000.0)


def pool_position(value: float | None) -> tuple[int, float] | None:
    """Which rung and scale a valuation sits on, or None if it is off-pool.

    Returns None rather than guessing: a value we cannot place is a value whose
    pool we do not know, and every caller falls back to the ordinary schedule.
    """
    if not value or value <= 0:
        return None
    for scale in RUNG_SCALES:
        for index, rung in enumerate(RUNG_SHAPE):
            if abs(value - rung * scale) <= max(1e-6, rung * scale * 1e-6):
                return index, scale
    return None


def tradable_rungs(state: dict, slot: str, role: str) -> list[float] | None:
    """Opponent valuations that could actually produce a deal, best first.

    A seller can only trade with a buyer valuing the item higher, and a buyer
    only with a seller valuing it lower, so conditioning on "a deal exists at
    all" throws away every other rung. What is left is the entire set of worlds
    worth pricing for -- in the rest we score zero whatever we do, which is
    exactly why aiming at the top of this list is free.
    """
    placed = pool_position(number(state, f"{slot}_value", None))
    if placed is None:
        return None
    index, scale = placed
    rungs = [rung * scale for rung in RUNG_SHAPE]
    live = rungs[index + 1:] if role == "seller" else rungs[:index]
    if not live:
        return []                      # the seat itself is untradable
    # Their own offers bound them further, but only loosely: measured against
    # recovered valuations their best offer runs to a median 1.06x their true
    # value, so a hard elimination would be wrong about half the time. Only
    # discard a rung the offer beats by more than that observed overshoot.
    prices = _their_prices(state, slot)
    if prices:
        if role == "seller":
            floor_ = max(prices) / 1.10
            live = [r for r in live if r >= floor_] or live
        else:
            ceiling = min(prices) * 1.10
            live = [r for r in live if r <= ceiling] or live
    return sorted(live, reverse=(role == "seller"))


def concession_clock(state: dict, slot: str, role: str) -> float:
    """How far to run the concession schedule, in [0, 1].

    A bounded game has a real deadline, so the round number is the clock and
    `progress` is right. An open-ended one has no deadline worth respecting: they
    run to round 99 while our schedule spent itself by round 11, giving the whole
    surplus away inside the first tenth of the game and then sitting at the floor
    for eighty-eight rounds.

    Measured over every open-ended game we have played, holding a price costs
    nothing. They improve their offer on 65-70% of rounds however long we have
    stonewalled -- 69.8% after two rounds, 67.5% after twelve -- and the size of
    the move GROWS with the wait, from +31% to +64%. What does carry information
    is THEM stalling: once their price has repeated four rounds running only 9.9%
    ever concede again, and after eight, 5.8%.

    So the clock ticks on their silence rather than on the round: it advances
    only on rounds their offer failed to improve, and `unbounded_soft_horizon`
    becomes "concede fully after this many stalled rounds" instead of "after this
    many rounds".
    """
    if state.get("horizon_known", False) and number(state, "max_rounds", None):
        return progress(state, P.unbounded_soft_horizon)
    prices = _their_prices(state, slot)
    if len(prices) < 2:
        return 0.0

    # Skip the opening anchor phase -- see `anchor_grace`. The clock starts on
    # their first real offer, or once the grace has run out and it is clear no
    # real offer is coming.
    my_value = number(state, f"{slot}_value", None)
    if my_value is not None:
        real = (lambda x: x > my_value) if role == "seller" else (lambda x: x < my_value)
        if not real(prices[0]):
            crossed = next((i for i, x in enumerate(prices) if real(x)), None)
            start = crossed if crossed is not None else min(len(prices) - 1, P.anchor_grace)
            prices = prices[start:]

    stalled = sum(
        1 for prev, cur in zip(prices, prices[1:])
        if not (cur > prev if role == "seller" else cur < prev)
    )
    return clamp(stalled / max(1.0, float(P.unbounded_soft_horizon)), 0.0, 1.0)


def _rung_price(state: dict, slot: str, role: str, my_value: float,
                last_word: bool) -> float | None:
    """Price aimed at one specific opponent valuation, or None to fall through.

    With rounds in hand we walk the ladder from the most valuable tradable rung
    down, because a rung refused costs only the round it took to ask. On the
    last word there is no ladder left, so we take the rung with the best
    expected value instead -- a refusal there pays zero.
    """
    live = tradable_rungs(state, slot, role)
    if live is None:
        return None
    if not live:
        return None                    # untradable seat: nothing to price for
    final = last_word or is_final_round(state)
    shade = clamp(P.rung_last_word_shade if final else P.rung_shade, 0.0, 0.5)

    def price_for(target: float) -> float:
        room = abs(target - my_value)
        return target - shade * room if role == "seller" else target + shade * room

    if final:
        # No ladder left, so take the rung with the best expected value. Aiming
        # at the k-th best of n equally likely rungs closes whenever they sit at
        # that rung OR any richer one, which is k chances in n -- asking for the
        # very top pays most per deal and closes least often, and the product is
        # what decides. Getting this backwards made the last offer jump back ABOVE
        # the one before it, un-conceding on the one round that cannot be redone.
        best, best_value = None, None
        for rank, target in enumerate(live, start=1):
            price = price_for(target)
            gain = _profit(role, price, my_value) * (rank / len(live))
            # `>=` so a tie breaks toward the LATER rung, which is the one more
            # opponents can sign. Two rungs tie whenever the extra profit of
            # aiming higher exactly cancels the extra chance of aiming lower --
            # common with two rungs live -- and breaking it toward the greedier
            # one made our last offer worse than our previous one, un-conceding
            # on the round that cannot be redone.
            if best_value is None or gain >= best_value:
                best, best_value = price, gain
        return best

    reached = int(concession_clock(state, slot, role) * len(live))

    # The clock alone can leave us priced at the top rung when the game is about
    # to end. A rung refused only costs the round it took to ask WHEN there is
    # another round -- past that it costs the whole game, and incomplete-
    # information deal rates sit at 0.28-0.39 against a 0.377 ceiling. So the
    # ladder also has a floor set by rounds actually remaining: with `usable`
    # rounds left there is time to try at most `usable` more rungs, and the rest
    # have to be skipped. This is what the `steps` variable computed here for
    # three commits and never applied.
    left = rounds_left(state, P.unbounded_soft_horizon)
    if left is not None:
        usable = max(1, left - P.endgame_rounds)
        reached = max(reached, len(live) - min(len(live), usable))
    return price_for(live[min(reached, len(live) - 1)])


def _target_price(state: dict, slot: str, role: str, last_word: bool = False) -> float:
    """The price we are holding out for this round.

    `last_word` marks the case where the number we are about to put down is the
    final offer of the game -- either because this is the last round, or because
    we are answering an offer with two rounds left, so our counter lands on the
    last round and they choose between it and nothing. Both are the end of the
    schedule, so both run it to completion.
    """
    my_value = number(state, f"{slot}_value", 0.0) or 0.0
    opponent_value = number(state, f"{OPPOSITE[slot]}_value", None)
    # On the final round there is no schedule left to run: this price is the
    # last word, and rejecting it pays $0. A one-round game is final on round 1,
    # where `progress` is still 0 -- so ask the horizon, not the clock.
    t = 1.0 if (last_word or is_final_round(state)) else concession_clock(state, slot, role)

    if opponent_value is not None:
        # Known zone of agreement: open just inside their limit, concede to the
        # midpoint. Shading matters -- a price at exactly their valuation leaves
        # them zero profit and no reason to sign.
        span = opponent_value - my_value
        best = opponent_value - P.zopa_shade * span
        # Where the schedule lands. `my_value + share * span` is our share of the
        # surplus for either role: span is positive as a seller and negative as a
        # buyer, so a larger share always moves the price our way. At 0.5 this is
        # the midpoint the schedule used to stop at -- see `surplus_target`.
        target = my_value + P.surplus_target * span
        return best + (target - best) * t

    if P.rung_aware:
        priced = _rung_price(state, slot, role, my_value, last_word)
        if priced is not None:
            return priced

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
    if SEND_MESSAGES and messages_allowed(game):
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

    # Out of road: any positive profit beats the $0 a no-deal pays. But only
    # when the road has really run out. Answering an offer means they proposed
    # this round, so the next one is ours -- and with an even number of rounds
    # left, the LAST proposal of the game is ours, where they choose between our
    # price and nothing. Taking any scrap there is selling the one seat they
    # cannot take from us. Measured over chunk 9: accepting at two rounds left
    # captured a median 27.9% of the surplus against 50.0% everywhere else.
    last_proposal_ours = left is not None and left % 2 == 0
    if final or (left is not None and left <= P.endgame_rounds and not last_proposal_ours):
        if gain > 0:
            return {"decision": "AcceptOffer"}
        if final:
            # No counteroffer exists on the last round; rejecting ends the game.
            return {"decision": "RejectOffer"}

    # An open-ended game never runs out of road, so a standing offer can be
    # refused forever. 85bd702f: their 815,000 was worth 15,000 to us and we
    # turned it down forty-nine times while they never moved a cent, and the
    # game ended 0-0 at the round cap. Once they have visibly stopped
    # negotiating, what is on the table is the whole of what is on offer.
    if gain > 0 and opponent_has_stopped_moving(state, slot):
        return {"decision": "AcceptOffer"}

    # If our counter lands on the last round, what it fetches there IS our
    # continuation value, so it prices the accept bar too -- comparing against a
    # mid-schedule number we will never actually offer would overstate what
    # holding out is worth.
    target = _target_price(state, slot, role, last_word=last_proposal_ours and left == 2)
    if gain >= _profit(role, target, my_value) * P.accept_slack:
        return {"decision": "AcceptOffer"}

    counter = _bounded_price(game, state, slot, role, target)
    # If our own counter would be worse for us than what is already on the
    # table, the negotiation is over -- just take the offer.
    if _profit(role, counter, my_value) <= gain:
        return {"decision": "AcceptOffer"}

    action = {"decision": "RejectOffer", "product_price": counter}
    if SEND_MESSAGES and messages_allowed(game):
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
