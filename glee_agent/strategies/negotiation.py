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


# A stall-driven concession clock lived here: it advanced only on rounds their
# offer failed to improve, with a grace period for opening lowballs. Both were
# reverted after losing their own A/B -- open-ended deal rate 0.449 against a
# control's 0.592, -1.74 sigma, with no surplus gain to show for it.
#
# The measurements that motivated them were survivorship. "They still move 67%
# of the time however long we hold" was computed over games that CLOSED, because
# an opponent's value is only recoverable from a completed deal -- so every game
# where we held firm and they walked was invisible to it. The games the change
# would go on to lose were exactly the ones missing from the evidence for it.

def final_offer_is_theirs(state: dict, slot: str) -> bool:
    """When we price this round, will the LAST price of the game be theirs?

    Prices alternate, so the parity of the gap to the horizon decides it. False
    whenever the horizon is unknown, since then there is no last price to hold.
    """
    if not state.get("horizon_known", False):
        return False
    max_rounds = number(state, "max_rounds", None)
    current = number(state, "round", None)
    if max_rounds is None or current is None:
        return False
    return (int(max_rounds) - int(current)) % 2 == 1


def _non_revealing_floor(state: dict, slot: str, role: str) -> float | None:
    """The price below which our ask names our own rung.

    Valuations sit on a known pool, so a seller asking under the next rung up is
    a seller who cannot be standing on it -- which leaves exactly one rung it can
    be standing on. Above that line the ask is consistent with two rungs and says
    nothing.
    """
    placed = pool_position(number(state, f"{slot}_value", None))
    if placed is None:
        return None
    index, scale = placed
    rungs = [rung * scale for rung in RUNG_SHAPE]
    neighbours = rungs[index + 1:] if role == "seller" else rungs[:index]
    if not neighbours:
        return None
    return min(neighbours) if role == "seller" else max(neighbours)


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

    reached = int(progress(state, P.unbounded_soft_horizon) * len(live))

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
    price = price_for(live[min(reached, len(live) - 1)])

    # Hold the ask where two rungs could have made it, so it does not name ours.
    #
    # OFF by default and staying that way. This was built on "when the last
    # price is theirs our ask cannot close, so raising it is free", measured as
    # 0 signings in 715 games. That measurement only looked at games that
    # reached the final round, which no game does if our ask closed it a round
    # earlier -- it excluded its own counterexamples. Scored on `agreed_round`
    # instead, the ask closes 10.2% of the time (29/283) and this flag halves
    # that. See `hide_rung_from_last_word` in params for the full correction.
    if P.hide_rung_from_last_word and final_offer_is_theirs(state, slot):
        floor_ = _non_revealing_floor(state, slot, role)
        if floor_ is not None:
            price = max(price, floor_) if role == "seller" else min(price, floor_)
    return price


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
    t = 1.0 if (last_word or is_final_round(state)) else progress(state, P.unbounded_soft_horizon)

    if opponent_value is not None:
        # Known zone of agreement: open just inside their limit, concede to the
        # midpoint. Shading matters -- a price at exactly their valuation leaves
        # them zero profit and no reason to sign.
        span = opponent_value - my_value
        if last_word or is_final_round(state):
            # An ultimatum, and rejecting one pays them zero: 216 of 216 last-word
            # offers we have ever made were signed. The schedule below runs from
            # aggressive toward `surplus_target` as time passes, so t=1.0 handed
            # them the most generous price of the whole game -- 0.650 of the zone
            # on the one round they could not refuse, against 0.867 mid-game.
            # This is the same correction the rung ladder got, which measured
            # +2.68 sigma; complete-information games never received it because
            # the crumb lives in `_rung_price`, which only runs when their value
            # is hidden.
            return opponent_value - P.rung_last_word_shade * span
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


def near_the_end(state: dict) -> bool:
    """Is refusing about to stop being free?

    A bounded game ends at `max_rounds`. An open one is not really open -- the
    server stops it at `open_horizon_cap` and pays both sides $0 -- but nothing
    in the state says so, which is why this reads the round number directly
    rather than trusting `rounds_left`, which returns None all the way to the end.
    """
    left = rounds_left(state, 0)
    if left is not None:
        return left <= P.endgame_rounds
    round_number = int(number(state, "round", 1) or 1)
    return (int(P.open_horizon_cap) - round_number) <= P.endgame_rounds


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
    # Both valuations visible: score the offer against the surplus itself rather
    # than against a schedule, and refuse a thin slice outright. Bounded games
    # only -- the endgame branch above then guarantees we still take any scrap
    # once the road really has run out, which is the backstop an open-ended game
    # does not have. Complete-information deals we signed took 0.3132 of the
    # surplus against 0.6009 when they signed ours.
    opponent_value = number(state, f"{OPPOSITE[slot]}_value", None)
    bounded = bool(state.get("horizon_known", False)) and number(state, "max_rounds", None)
    if P.known_zone_floor > 0.0 and opponent_value is not None and bounded and not final:
        span = abs(opponent_value - my_value)
        if span > 0 and gain < span * P.known_zone_floor:
            counter = _bounded_price(game, state, slot, role,
                                     _target_price(state, slot, role))
            action = {"decision": "RejectOffer", "product_price": counter}
            if SEND_MESSAGES and messages_allowed(game):
                action["message"] = _counter_message(
                    role, progress(state, P.unbounded_soft_horizon))
            return action

    holds_ultimatum = (
        P.stonewall_respects_ultimatum
        and bool(state.get("horizon_known", False))
        and number(state, "max_rounds", None) is not None
        and last_proposal_ours
    )
    if gain > 0 and opponent_has_stopped_moving(state, slot) and not holds_ultimatum:
        # Only cave to a stonewaller once refusing actually costs us something.
        # The branch can only ever arm in an open game -- a bounded one is too
        # short for `stonewall_offers` of their offers to land -- and an open
        # game has no inflation and 87 rounds still to run, so "they have not
        # moved yet" is not evidence they never will. See `stonewall_needs_endgame`.
        if not P.stonewall_needs_endgame or near_the_end(state):
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
