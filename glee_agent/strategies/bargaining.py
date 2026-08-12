"""Divide the Dollar: subgame-perfect anchoring with an endgame safety net.

Two ideas carry this strategy.

1. Alternating-offer bargaining has a closed-form solution. Whoever proposes can
   keep everything except the discounted value of the responder's own future
   proposal, which gives the patient player the larger share. We compute that
   share exactly and use it as the floor we never sell below.

2. A no-deal pays $0, and $0 is the bottom of the percentile scale that sets our
   rating. The theoretical floor is therefore abandoned as the horizon closes:
   in the last rounds we take almost anything rather than book a zero.

A note on which solution we anchor to. The finite-horizon recursion swings hard
with the parity of the horizon -- whoever proposes last can take the pot, so the
equilibrium share alternates between roughly 0.25 and 0.91 as one round is added
or removed. That is correct against an opponent playing the same equilibrium and
badly wrong against the field, which converges near an even split; it would also
make our demands jump around between rounds for no reason the opponent can see.
So the live policy anchors on the parity-free infinite-horizon share, which is
what actually measures bargaining power (a patient player earns more), and
handles the last rounds -- where parity genuinely binds -- with the explicit
endgame rules instead. `proposer_share` still computes the finite case exactly;
it is the honest reference the endgame rules are calibrated against.

We never walk away. Walking away pays exactly $0, the same as running out of
rounds, so it can only ever match the worst outcome available to us.
"""

from __future__ import annotations

from ..gamestate import (
    OPPOSITE,
    clamp,
    is_final_round,
    me as my_slot,
    messages_allowed,
    number,
    progress,
    rounds_left,
    split_exactly,
)
from ..params import BARGAINING as P

# Past this many rounds the finite-horizon recursion has converged on the
# infinite-horizon fixed point, so we switch to the closed form.
_EXACT_RECURSION_LIMIT = 60

_DELTA_KEY = {"player_1": "delta_1", "player_2": "delta_2"}


def proposer_share(delta_me: float, delta_opp: float, rounds_left_: int | None) -> float:
    """Fraction of the pot the proposer keeps under subgame-perfect play.

    With one round left the proposer takes everything: the responder's
    alternative to accepting is $0. With more, the proposer must leave the
    responder exactly what the responder would get by rejecting and proposing
    next round, discounted by the responder's own inflation -- and the roles
    swap on each step back, which is why the deltas swap in the recursion.
    """
    if rounds_left_ is None or rounds_left_ > _EXACT_RECURSION_LIMIT:
        denominator = 1.0 - delta_me * delta_opp
        if denominator <= 1e-9:
            return 1.0
        return clamp((1.0 - delta_opp) / denominator, 0.0, 1.0)
    if rounds_left_ <= 1:
        return 1.0
    return clamp(1.0 - delta_opp * proposer_share(delta_opp, delta_me, rounds_left_ - 1), 0.0, 1.0)


def _deltas(state: dict, slot: str) -> tuple[float, float]:
    """Our per-round discount and the opponent's.

    Under incomplete information the opponent's is absent from our view; we
    assume it matches ours unless `assumed_opponent_delta` overrides that.
    Guessing them more patient than they are makes us concede too much, so the
    symmetric guess is the neutral default.
    """
    mine = number(state, _DELTA_KEY[slot], None)
    theirs = number(state, _DELTA_KEY[OPPOSITE[slot]], None)
    if mine is None:
        mine = 0.95
    if theirs is None:
        theirs = P.assumed_opponent_delta if P.assumed_opponent_delta is not None else mine
    return clamp(float(mine), 0.01, 1.0), clamp(float(theirs), 0.01, 1.0)


def _continuation_value(state: dict, slot: str) -> float:
    """Our share of the pot, in today's dollars, if we reject and counter.

    Rejecting costs us one round of inflation and hands us the proposer's seat
    for whatever rounds remain. On the final round it is worth nothing, which is
    what makes accepting a bad last offer correct.
    """
    if is_final_round(state):
        return 0.0
    delta_me, delta_opp = _deltas(state, slot)
    return delta_me * proposer_share(delta_me, delta_opp, None)


def _make_offer(game: dict) -> dict:
    state = game["game_state"]
    slot = my_slot(game)
    money = number(state, "money_to_divide", 0.0) or 0.0
    delta_me, delta_opp = _deltas(state, slot)

    left = rounds_left(state, P.unbounded_soft_horizon)
    # The equilibrium share is a floor to protect, not an opening bid to
    # announce -- and never a reason to concede past what the field will sign.
    floor = max(proposer_share(delta_me, delta_opp, None), P.never_concede_below)
    opening = max(P.opening_demand, floor)
    weight = (1.0 - progress(state, P.unbounded_soft_horizon)) ** P.concession_exponent
    demand = floor + (opening - floor) * weight

    if left is not None:
        if left <= 1:
            # We hold the last word: rejecting pays the responder $0, so this is
            # the one round where taking most of the pot is also acceptable.
            demand = P.final_round_demand
        elif left <= P.endgame_rounds:
            # They hold the last word. Make an offer worth signing.
            demand = min(demand, P.endgame_demand_cap)
    demand = clamp(demand, 0.0, 1.0 - P.min_opponent_share)

    mine, theirs = split_exactly(money, demand)
    if slot == "player_1":
        action = {"alice_gain": mine, "bob_gain": theirs}
    else:
        action = {"alice_gain": theirs, "bob_gain": mine}
    if messages_allowed(game):
        action["message"] = _offer_message(state, demand)
    return action


def _make_decision(game: dict) -> dict:
    state = game["game_state"]
    slot = my_slot(game)
    money = number(state, "money_to_divide", 0.0) or 0.0
    offer = state.get("last_offer") or {}
    my_gain = number(offer, f"{slot}_gain", 0.0) or 0.0

    # Hold out for the better of what theory says rejecting is worth and what
    # the field will usually agree to -- the equilibrium continuation collapses
    # to single digits on some horizon parities, which is not a real offer.
    threshold = max(
        money * _continuation_value(state, slot) * P.accept_slack,
        money * P.min_accept_share,
    )

    left = rounds_left(state, P.unbounded_soft_horizon)
    if left is not None and left <= P.endgame_rounds:
        # Out of road: a live offer beats the $0 that running out of rounds pays.
        threshold = min(threshold, money * P.endgame_floor)
    if is_final_round(state):
        threshold = 0.0

    if my_gain >= threshold:
        return {"decision": "accept"}
    return {"decision": "reject"}


def _offer_message(state: dict, demand: float) -> str:
    round_number = int(number(state, "round", 1) or 1)
    if demand >= 0.7:
        return (
            "Opening where I think the value sits. Every round we spend arguing "
            "shrinks the pot for both of us, so I would rather settle now."
        )
    if round_number > 1:
        return (
            "I have moved toward you from my last offer. Inflation is eating "
            "this for both of us -- this is a deal worth closing."
        )
    return "A split I can sign right now. Waiting only costs us both."


def play(game: dict) -> dict:
    if (game.get("valid_actions") or {}).get("type") == "offer":
        return _make_offer(game)
    return _make_decision(game)
