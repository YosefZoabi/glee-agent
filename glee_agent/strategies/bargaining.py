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
badly wrong against the field, which converges near an even split. So the live
policy anchors on the parity-free infinite-horizon share, which is what actually
measures bargaining power (a patient player earns more).

What parity does buy us is a guarantee, and that is a different thing from a
prediction. If the last proposal of the game is ours, we can always refuse
everything and make it: the responder is then choosing between our number and
$0. `endgame_hold_value` prices that -- it is worth nearly the whole pot to a
player who pays nothing for delay and nearly nothing to one bleeding 20% a
round, because getting there costs our own inflation for every round we wait.
It needs no assumption about how the opponent plays, which is what separates it
from the finite-horizon recursion. Parity is also stable within a game: proposers
alternate, so if the last word is ours on one of our turns it is ours on all of
them, and the demand does not oscillate.

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
from ..params import BARGAINING as P, SEND_MESSAGES

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
    value = patience * share
    left = rounds_left(state, 0)
    if left is not None and left > 1:
        # The infinite-horizon share says a player who pays nothing for delay
        # can hold out for everything -- and a deadline is exactly what makes
        # that false. Games 7159f219 and 9bb27d9e: our delta 1.0, twelve rounds,
        # and the last proposal THEIRS. The parity-free bar held at 73% while
        # our real continuation was 22% falling to 5%, so we turned down 72% of
        # the pot at round 10 and took the 2% they offered at round 12, where
        # refusing pays $0. Past the deadline the recursion is not a stylised
        # alternative to the closed form, it is the answer.
        value = min(value, delta_me * proposer_share(delta_me, delta_opp, left - 1))
    return value


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


def _rounds_until_our_last_proposal(state: dict, slot: str) -> int | None:
    """Rounds we must wait to reach the final proposal, when it is ours.

    None when the horizon is unknown or the last word belongs to them, i.e.
    whenever there is no such proposal to wait for.
    """
    if not _final_round_is_ours(state, slot):
        return None
    max_rounds = number(state, "max_rounds", None)
    current = number(state, "round", None)
    if max_rounds is None or current is None:
        return None
    return max(0, int(max_rounds) - int(current))


def endgame_hold_value(state: dict, slot: str) -> float:
    """Share of the pot we can GUARANTEE by riding to our own final proposal.

    Whoever makes the last offer picks what the responder gets against $0, so
    `final_round_demand` is signable there -- observed four times out of four.
    They cannot take that seat away from us, so this is a floor under our
    continuation value that holds against any opponent, however stubborn.

    The price of collecting it is our own inflation for every round we wait,
    which is what makes this worth almost the whole pot at delta 1.0 and worth
    less than nothing at delta 0.8 across eleven rounds. That is why it is only
    ever a floor: `max` against the other bars discards it when waiting costs
    more than the seat is worth, so an impatient player still closes early.

    This is the endgame sweep generalised. `endgame_sweep` is the special case
    where delay is free, and keeps its own path because it can hold out for the
    full demand from round one rather than a discounted version of it.
    """
    wait = _rounds_until_our_last_proposal(state, slot)
    if wait is None:
        return 0.0
    delta_me, _ = _deltas(state, slot)
    return clamp(P.final_round_demand * delta_me ** wait, 0.0, P.final_round_demand)


def hold_out_value(state: dict, slot: str) -> float:
    """The best share we can defend by refusing what is on the table.

    Two independent claims, whichever is larger:

    * the endgame seat, when the last proposal is ours -- a guarantee;
    * the equilibrium continuation, when the opponent's inflation rate is
      actually visible to us -- a prediction, and only made when the deltas are
      facts rather than a guess. Under incomplete information `_deltas` fills
      the opponent's in with our own, and betting a raised accept bar on that
      guess is how you turn a signed deal into a no-deal.

    Both are floors, never ceilings: the caller takes `max` with the evidence
    derived bar, so this can only ever make us hold out longer than before, and
    never make us sign for less.
    """
    equilibrium = 0.0
    if state.get("complete_information", False) and number(
        state, _DELTA_KEY[OPPOSITE[slot]], None
    ) is not None:
        equilibrium = _continuation_value(state, slot)

    return max(endgame_hold_value(state, slot), equilibrium, costless_hold_value(state, slot))


def costless_hold_value(state: dict, slot: str) -> float:
    """What simply waiting is worth when waiting is free and the clock is open.

    Neither of the other two claims can be made in an open-ended game whose
    opponent delta we cannot see: there is no final proposal to hold and no
    equilibrium to compute. That left a player with no inflation at all
    defending the flat evidence bar, which is measurably too low -- see
    `costless_hold_share` for the numbers.

    Deliberately NOT discounted by `accept_slack`. That discount prices one more
    round of our own inflation against the chance the opponent never moves, and
    here the first term is exactly zero -- which is the whole reason this floor
    exists. Applying it anyway pulled the bar to 47.4% and went on signing the
    48% offers this was written to refuse.
    """
    delta_me, _ = _deltas(state, slot)
    if delta_me < P.costless_delay_delta or rounds_left(state, 0) is not None:
        return 0.0
    return P.costless_hold_share


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
    # Seeing that they are the patient one is not a reason to hand them the pot.
    # 0.8 is the bottom of the delta grid, so a visible opponent is almost always
    # more patient than us there, the equilibrium share collapses to the clamp,
    # and we open lower than we would have if we could not see it at all.
    # Measured on the same delta and horizon, complete information against
    # hidden: -5.7% and -5.0% in chunk 9, -6.4% in chunk 12, while every delta
    # at 0.9 and above gained from the extra information. Bargaining took zero
    # no-deals in 521 games, so the risk of asking for more is not the binding
    # constraint -- being talked out of asking is. Never demand less than we
    # would against an opponent assumed to be our own twin.
    # ...but only where we can actually hold the line. With a known horizon the
    # endgame forces a resolution and the extra demand sticks: delta 0.8 with
    # their clock visible went 38.0% -> 41.4%. With an OPEN horizon and an
    # impatient agent it backfired, 44.4% -> 37.5%, because the accept bar at
    # delta 0.8 is 11.8% -- we opened high enough to push them past round one
    # and then signed whatever they countered with, settling a round later for
    # less. Do not demand what the accept bar will not defend.
    if rounds_left(state, 0) is not None:
        floor = max(
            floor,
            clamp(proposer_share(delta_me, delta_me, None),
                  P.never_concede_below, P.never_demand_above),
        )
    # Never offer to keep less than we would insist on as the responder, or we
    # spend the leverage on our own turn that we were holding out for on theirs.
    floor = max(floor, hold_out_value(state, slot))
    # A high opening buys a long haggle, and an impatient player cannot afford
    # one: every round of it costs us `1 - delta_me` of whatever we finally win.
    # So the more our own clock hurts, the closer we open to the floor.
    patience = delta_me ** max(1, P.rounds_to_settle)
    opening = floor + (max(P.opening_demand, floor) - floor) * patience
    weight = (1.0 - progress(state, P.unbounded_soft_horizon)) ** P.concession_exponent
    demand = floor + (opening - floor) * weight

    # A haggle we cannot afford is not worth opening. See `closing_offer_delta`:
    # the field does not move and does not price-shop, so the only thing our
    # inflated opening buys is the round of inflation it takes them to counter.
    # Never below what we would hold out for as the responder, which leaves the
    # complete-information cells where we are the patient side untouched.
    # Open horizons only. Chunk 13 measured the opposite sign in the two
    # regimes: raising the opening took bounded delta-0.8 games 38.0% -> 41.4%
    # and open ones 44.4% -> 37.5%. A known horizon forces a resolution and the
    # extra demand sticks; an open one lets the haggle run, which is the cycle
    # this closes. Do not spend a measured gain to buy an unmeasured one.
    # ...and only where the haggle is actually worthless. A visible patience
    # edge is a claim we can hold: seeing that they inflate faster than we do
    # pays a median 0.63-0.75 of the pot in exactly these cells, against the
    # 0.44 the field counters with elsewhere. Closing early there would hand
    # back the one advantage complete information buys, so when `hold_out_value`
    # already clears the closing share we leave the schedule alone entirely.
    closing = (
        delta_me <= P.closing_offer_delta
        and rounds_left(state, 0) is None
        and hold_out_value(state, slot) < P.closing_offer_share
    )
    if closing:
        demand = min(demand, max(P.closing_offer_share, P.never_concede_below))

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
        elif left <= P.endgame_rounds and not _final_round_is_ours(state, slot):
            # They hold the last word. Make an offer worth signing.
            demand = min(demand, P.endgame_demand_cap)
    demand = clamp(demand, 0.0, 1.0 - P.min_opponent_share)

    mine, theirs = split_exactly(money, demand)
    if slot == "player_1":
        action = {"alice_gain": mine, "bob_gain": theirs}
    else:
        action = {"alice_gain": theirs, "bob_gain": mine}
    if SEND_MESSAGES and messages_allowed(game):
        # The endgame branches above can overwrite `demand` outright, so the
        # closing message is only honest if the closing rule is still what set
        # the number we are actually sending.
        action["message"] = _offer_message(
            state, demand, closing and demand <= P.closing_offer_share + 1e-9
        )
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
    # `stonewall_threshold` for the evidence-derived bar, which prices a field
    # that mostly does not concede, and `hold_out_value` for the two cases where
    # we can do better than that: we own the last proposal, or their inflation
    # rate is on the table and says we are the patient one. Taking the larger
    # keeps every previously-signed deal signable.
    # `accept_slack` only discounts the hold-out claim, never the evidence bar,
    # so the floor cannot slip below where it stood. Without it we refused 55.0%
    # to chase a 55.2% guarantee eleven rounds away -- taking on the whole risk
    # of the wait for two tenths of a percent.
    threshold = money * max(
        stonewall_threshold(state, slot),
        hold_out_value(state, slot) * P.accept_slack,
        costless_hold_value(state, slot),
    )

    left = rounds_left(state, P.unbounded_soft_horizon)
    if left is None:
        # Open-ended game: no final round will ever arrive to force our hand, so
        # a threshold we hold forever is a threshold that pays $0. Observed: 50
        # consecutive rejections of a standing 65% offer, game still going at
        # round 99. Walk the bar down over the soft horizon until a real offer
        # clears it -- the opponent's patience is not evidence they will move.
        #
        # Strictly DOWN. Written as a plain interpolation this walks the bar UP
        # whenever it starts under `min_accept_share`, which is every impatient
        # player: at delta 0.9 the bar climbed 19.5% -> 35% and we ground
        # 92727cf1 for sixty-nine rounds to bank 274 of a 353,652 split. Time
        # pressure in an open-ended game can only ever be an argument for
        # signing sooner.
        walked = threshold + (money * P.min_accept_share - threshold) * progress(
            state, P.unbounded_soft_horizon
        )
        threshold = min(threshold, walked)
    elif left <= P.endgame_rounds and not _final_round_is_ours(state, slot):
        # Out of road: a live offer beats the $0 that running out of rounds pays.
        # Only when the road really has run out, though. If the last proposal is
        # ours we are not out of anything -- collapsing the bar here would hand
        # back the endgame seat one round before we get to sit in it.
        threshold = min(threshold, money * P.endgame_floor)
    if is_final_round(state):
        threshold = 0.0

    if my_gain >= threshold:
        return {"decision": "accept"}
    return {"decision": "reject"}


def _offer_message(state: dict, demand: float, closing: bool = False) -> str:
    round_number = int(number(state, "round", 1) or 1)
    if closing:
        # The one channel left. Our offers are accepted 4-10% of the time
        # regardless of what we ask, so the number is not what decides this --
        # the text is. Three things an LLM can act on: the split is even, the
        # offer will not improve, and countering costs them. Deliberately does
        # NOT mention our own inflation rate: an opponent told we are the
        # impatient one has every reason to wait us out.
        return (
            "I am opening at my number rather than an inflated one, so this is "
            "an even split you can sign right now. I will not beat it later -- a "
            "counter just spends a round of value we both keep by closing today."
        )
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
