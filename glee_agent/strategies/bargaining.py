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
    history,
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
            # Neither side pays anything for delay (delta 1.0, which is a third
            # of the observed grid), so neither has bargaining power and the
            # model has no unique solution -- every split is an equilibrium.
            # Reading that as "we take everything" deadlocks the game, and a
            # no-deal pays $0. With no asymmetry the symmetric split is the only
            # defensible focal point.
            return 0.5
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

    Rejecting hands us the proposer's seat for whatever rounds remain, but not
    immediately: the field does not accept our counter on the spot, so the price
    of rejecting is `rounds_to_settle` rounds of our own inflation, not one.
    Charging only one round overvalues holding out, and the more impatient we
    are the worse that error gets -- which is exactly when it is most expensive.
    On the final round rejecting is worth nothing, which is what makes accepting
    a bad last offer correct.
    """
    if is_final_round(state):
        return 0.0
    delta_me, delta_opp = _deltas(state, slot)
    patience = delta_me ** max(1, P.rounds_to_settle)
    # Capped: an uncapped share of 1.0 becomes "accept nothing below 97%", which
    # is how we rejected 72% of a 1,000,000 pot forty-nine times and banked $0.
    share = min(proposer_share(delta_me, delta_opp, None), P.never_demand_above)
    return patience * share


def _final_round_is_ours(state: dict, slot: str) -> bool:
    """True when the last proposal of the game is ours to make.

    Proposers alternate, so the parity of the gap to the horizon decides it.
    Read off the live `proposer` rather than assuming player_1 opens.
    """
    if not state.get("horizon_known", False):
        return False
    max_rounds = number(state, "max_rounds", None)
    current = number(state, "round", None)
    proposer = state.get("proposer")
    if max_rounds is None or current is None or proposer not in OPPOSITE:
        return False
    gap = int(max_rounds) - int(current)
    if gap < 0:
        return False
    last = proposer if gap % 2 == 0 else OPPOSITE[proposer]
    return last == slot


def endgame_sweep(state: dict, slot: str) -> bool:
    """Should we stall to the final round and take nearly the whole pot?

    Only when both halves hold. Our inflation must be nil, so waiting is free
    and every round we burn costs us nothing. And the last proposal must be
    ours, because a responder facing the final offer is choosing between it and
    $0 -- which is what makes an almost-total demand signable.

    Lose either half and this is a bad idea: with real inflation, stalling burns
    the pot we are stalling for, and if the last word is theirs we arrive at the
    end as the responder with nothing to threaten them with.
    """
    delta_me, _ = _deltas(state, slot)
    return delta_me >= P.costless_delay_delta and _final_round_is_ours(state, slot)


def opponent_is_sweeping(game: dict, slot: str) -> bool:
    """Are they running the endgame sweep on us?

    Structural half: the last proposal is theirs, so at the end we choose
    between their token and $0, and they know it. Behavioural half: they have
    refused several of our offers while never putting a real share on the table.

    Both halves are needed. Owning the endgame is not proof anyone is exploiting
    it -- most opponents negotiate normally regardless of parity -- and being
    stubborn is not proof either. Believing it too readily is worse than missing
    it: the response is to bank crumbs, which is a catastrophe against someone
    who was about to concede.
    """
    state = game["game_state"]
    if _final_round_is_ours(state, slot) or not state.get("horizon_known", False):
        return False

    pot = number(state, "money_to_divide", 0.0) or 0.0
    if pot <= 0:
        return False

    refusals, best_offered = 0, 0.0
    for entry in history(game):
        offer = entry.get("offer") or {}
        proposer = entry.get("proposer") or offer.get("proposer")
        decision = str(entry.get("decision") or "").lower()
        if proposer == slot and decision.startswith("rej"):
            refusals += 1
        elif proposer == OPPOSITE[slot]:
            best_offered = max(best_offered, number(offer, f"{slot}_gain", 0.0) or 0.0)

    return (
        refusals >= P.sweep_evidence_rounds
        and best_offered <= pot * P.sweep_evidence_ceiling
    )


def _swept_endgame_value(state: dict, slot: str, pot: float) -> float:
    """What we actually collect if we let a sweeper run the clock out.

    Their final offer leaves us a token, and we take it because the alternative
    is $0. Discounted by our own inflation over the rounds it takes to arrive.
    """
    delta_me, _ = _deltas(state, slot)
    left = rounds_left(state, P.unbounded_soft_horizon) or 1
    return pot * P.min_opponent_share * (delta_me ** max(0, left - 1))


def stonewall_threshold(state: dict, slot: str) -> float:
    """Share of the pot worth signing, against an opponent who will not move.

    The equilibrium continuation prices rejection as "they concede next round".
    Measured over 55 games, they do not: their offers drifted a median +0.5%
    from first to last however long we waited, and our counters were accepted
    15% of the time at best. So rejecting is really a small chance our counter
    lands, and otherwise the same offer again two rounds poorer:

        reject == p*D*delta + (1 - p) * X * delta**2

    Solving for the X where accepting ties gives the bar below. It rises with
    patience, which is the right shape -- a player who pays nothing for delay
    can afford to wait, and one bleeding 20% a round cannot.
    """
    delta_me, _ = _deltas(state, slot)
    p = clamp(P.counter_success_rate, 0.0, 1.0)
    demand = P.realistic_counter_share
    denominator = 1.0 - (1.0 - p) * delta_me ** 2
    if denominator <= 1e-9:
        return demand
    return clamp(p * demand * delta_me / denominator, 0.0, 1.0)


def _make_offer(game: dict) -> dict:
    state = game["game_state"]
    slot = my_slot(game)
    money = number(state, "money_to_divide", 0.0) or 0.0
    delta_me, delta_opp = _deltas(state, slot)

    left = rounds_left(state, P.unbounded_soft_horizon)
    # The equilibrium share is a floor to protect, not an opening bid to
    # announce -- and never a reason to concede past what the field will sign.
    floor = clamp(proposer_share(delta_me, delta_opp, None), P.never_concede_below, P.never_demand_above)
    # A high opening buys a long haggle, and an impatient player cannot afford
    # one: every round of it costs us `1 - delta_me` of whatever we finally win.
    # So the more our own clock hurts, the closer we open to the floor.
    patience = delta_me ** max(1, P.rounds_to_settle)
    opening = floor + (max(P.opening_demand, floor) - floor) * patience
    weight = (1.0 - progress(state, P.unbounded_soft_horizon)) ** P.concession_exponent
    demand = floor + (opening - floor) * weight

    if left is not None:
        if left <= 1:
            # We hold the last word: rejecting pays the responder $0, so this is
            # the one round where taking most of the pot is also acceptable.
            demand = P.final_round_demand
        elif endgame_sweep(state, slot):
            # Waiting is free and the last word is ours, so these earlier offers
            # are not attempts to close -- they cost nothing to make and are pure
            # upside if taken. Ask for what we intend to take at the end.
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
        if opponent_is_sweeping(game, slot):
            # We cannot actually punish them -- walking away pays us $0 too, and
            # at the end we will take their token rather than nothing. But the
            # threat is free to make and the rules permit it, and an opponent who
            # believes it has to weigh the whole pot against waiting us out.
            action["message"] = (
                "You are running the clock down to make me take scraps at the end. "
                "I would rather book nothing than sign that, and nothing is what "
                "we both get. This offer is open now."
            )
    return action


def _make_decision(game: dict) -> dict:
    state = game["game_state"]
    slot = my_slot(game)
    money = number(state, "money_to_divide", 0.0) or 0.0
    offer = state.get("last_offer") or {}
    my_gain = number(offer, f"{slot}_gain", 0.0) or 0.0

    if endgame_sweep(state, slot):
        # Delay is free and the final proposal is ours, where their alternative
        # to signing is $0. Nothing on the table before then is worth taking
        # unless it already beats what we intend to demand at the end.
        if my_gain >= money * P.final_round_demand:
            return {"decision": "accept"}
        return {"decision": "reject"}

    if opponent_is_sweeping(game, slot):
        # The mirror image, from the losing side. Once they hold the last word
        # and have shown they will not trade for it, the fair split we are
        # holding out for is not on offer and never was -- our real choice is
        # between what is on the table now and the token they hand us at the
        # end. Take anything clearly better than that token.
        if my_gain >= _swept_endgame_value(state, slot, money) * P.sweep_accept_margin:
            return {"decision": "accept"}
        return {"decision": "reject"}

    # What rejecting is actually worth against this field -- see
    # `stonewall_threshold`. The equilibrium continuation is the theoretical
    # reference and stays available in `_continuation_value`, but pricing
    # rejection as "they concede next round" is what had us grinding games we
    # should have signed: 32.5% of the nominal split lost to delay.
    threshold = money * stonewall_threshold(state, slot)

    left = rounds_left(state, P.unbounded_soft_horizon)
    if left is None:
        # Open-ended game: no final round will ever arrive to force our hand, so
        # a threshold we hold forever is a threshold that pays $0. Observed: 50
        # consecutive rejections of a standing 65% offer, game still going at
        # round 99. Walk the bar down over the soft horizon until a real offer
        # clears it -- the opponent's patience is not evidence they will move.
        threshold += (money * P.min_accept_share - threshold) * progress(
            state, P.unbounded_soft_horizon
        )
    elif left <= P.endgame_rounds:
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
