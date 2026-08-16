"""All strategy tunables in one place.

Every knob the three strategy modules read lives here, so tuning a family is a
one-file edit and the diff for a tuning experiment is legible. Nothing here
touches the network or the SDK.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BargainingParams:
    # Used for the opponent's inflation rate in incomplete-information games,
    # where `delta_2` (or `delta_1`) is absent from our view of the state.
    # `None` means "assume the opponent's is the same as ours".
    assumed_opponent_delta: float | None = None

    # Round-1 demand as a fraction of the pot. We open above the subgame-perfect
    # share and walk down to it, because the field (LLMs and humans) concedes.
    opening_demand: float = 0.85
    # Higher = hold the opening demand longer before collapsing to the SPE share.
    concession_exponent: float = 1.6
    # Never leave the opponent literally nothing -- a 0 offer reads as an insult
    # and buys a rejection we pay inflation for.
    min_opponent_share: float = 0.03

    # The equilibrium share swings wildly with the parity of the horizon: with a
    # known even number of rounds the opponent proposes last and theory says we
    # take a quarter of the pot. Against a field that converges near an even
    # split, conceding that far is a pure loss, so these two clamp the theory to
    # what the field will actually sign.
    never_concede_below: float = 0.45
    min_accept_share: float = 0.35
    # The ceiling half of the same clamp. The equilibrium share hits 1.0 whenever
    # our own delta is 1.0, whatever the opponent's is -- theory says a player who
    # pays nothing for delay can hold out for everything. No opponent signs that,
    # so believing it turns into "accept nothing below 97%" and a $0 deadlock.
    never_demand_above: float = 0.75

    # --- What rejecting is really worth ----------------------------------
    # Measured over 55 games. The equilibrium continuation assumes an opponent
    # who concedes toward it; the field does not. Their offers moved a median
    # +0.5% from first to last however long we waited (12 of 21 flat or worse),
    # and our counters were accepted 15% of the time at best. So rejecting buys
    # a small chance our counter lands and otherwise the same number again, one
    # round poorer. Accept X when X >= p*D*delta + (1-p)*X*delta^2.
    counter_success_rate: float = 0.15
    # The demand with the best observed acceptance -- our 40-49% asks landed 15%
    # of the time, everything above that essentially never.
    realistic_counter_share: float = 0.45

    # How many rounds a rejection really costs before the game settles. Theory
    # says one -- reject, propose, they accept -- but the field haggles: observed
    # play took 7 rounds to move 427k -> 460k on a 1M pot while our own delta of
    # 0.9 burned 47% of the result. Rejecting is priced over this many rounds of
    # inflation, not one, which is what makes an impatient player close early.
    rounds_to_settle: int = 3
    # Accept at this multiple of our continuation value. Slightly below 1.0
    # because one more round of inflation is a real cost and the opponent may
    # not concede at all.
    accept_slack: float = 0.97
    # With this many rounds left, a no-deal ($0, bottom-percentile) outranks any
    # theoretical gain, so we accept anything at or above `endgame_floor`.
    endgame_rounds: int = 2
    endgame_floor: float = 0.08
    # The mirror image on the offering side. Theory says the last proposer can
    # take everything, because the responder's alternative is $0 -- but an
    # opponent who rejects out of pique costs us the whole pot, so the last
    # offers stay large without being insulting.
    endgame_demand_cap: float = 0.55
    # `min_opponent_share` clamps this anyway, so 0.97 is what 0.99 already meant.
    final_round_demand: float = 0.97
    # At or above this delta, delay costs us nothing. Combined with holding the
    # last proposal it licenses the endgame sweep: stall to the final round and
    # take `final_round_demand`, because rejecting it pays the responder $0.
    # Below it, stalling burns real money and the normal schedule applies.
    costless_delay_delta: float = 0.999
    # ...and with no horizon at all there is no last proposal to hold, so the
    # sweep cannot fire and neither can the equilibrium bar, which needs the
    # opponent's delta. That left a costless-delay player defending the flat
    # `realistic_counter_share`, and 45% is measurably too low there. Across 56
    # post-fix games of exactly this shape, rejecting an offer of 40-45% ended
    # at a median 47.2% (+5.2), rejecting 45-50% ended at 49.0% (+1.7), and
    # rejecting 50-55% gained nothing -- with zero no-deals in any band. The
    # break-even sits at 50%, so that is where a player who pays nothing to wait
    # should stand. Only ever a floor: `max` against the evidence bar.
    costless_hold_share: float = 0.50

    # --- Facing a sweeper -------------------------------------------------
    # The mirror image: THEY hold the last proposal and are stalling to it. Our
    # continuation is then whatever a sweeper deigns to leave us, so holding out
    # for a fair split is holding out for something that is never coming.
    # Requires this many of our offers refused before we believe it -- an
    # ordinary stubborn negotiator must not trip it, or we capitulate to anyone
    # who says no twice.
    sweep_evidence_rounds: int = 3
    # ...and their offers must have stayed under this share of the pot. A player
    # genuinely converging toward a split is negotiating, not sweeping.
    sweep_evidence_ceiling: float = 0.35
    # Once believed: bank anything at least this much better than the token a
    # sweeper leaves at the end. Early crumbs beat late crumbs, and against a
    # patient sweeper they beat the fair split that will never be offered.
    sweep_accept_margin: float = 1.5

    # --- Closing instead of haggling --------------------------------------
    # An impatient proposer cannot afford a negotiation. Two measurements over
    # 1,469 games say so together:
    #
    #   * Our openings are accepted 4-10% of the time whether we ask 0.65 or
    #     0.85 -- the field is not price-sensitive, it is running its own
    #     schedule, so a high opening buys nothing.
    #   * The field concedes a median of +0.0000 per round (mean +0.0093, only
    #     30% of steps an improvement at all), so the haggle it buys goes
    #     nowhere.
    #
    # What actually happens in 473 games: we open ~0.66, they counter ~0.44, and
    # we sign that counter one round later. At delta 0.8 the round costs 20% of
    # the pot, so a 0.440 deal pays 0.352. We are paying a full round of interest
    # for a bid that almost never lands. Below this delta, open at a number that
    # can be signed on the spot instead.
    #
    # Only ever a `min` against the scheduled demand, floored by
    # `hold_out_value` and `never_concede_below`, so it can lower an opening but
    # can never offer to keep less than we would insist on as the responder --
    # which is what protects the complete-information cells where we are the
    # patient side and the equilibrium share is genuinely high.
    #
    # Restricted to OPEN horizons. Chunk 13 measured raising the opening as
    # +3.4 points bounded and -6.9 open, so the two regimes want opposite
    # things and only the open one is ours to fix. That leaves 281 games of the
    # 473, and keeps the bounded gain that is already banked.
    closing_offer_delta: float = 0.96
    # Just above the 0.44 the field counters with, so it reads as a near-even
    # split rather than a demand, and clears `never_concede_below` outright.
    closing_offer_share: float = 0.50

    # Open-ended games have no forced endgame; pretend one exists here so the
    # concession schedule still moves.
    unbounded_soft_horizon: int = 12


@dataclass(frozen=True)
class NegotiationParams:
    # Incomplete information: opening ask/bid as a multiple of our own value.
    seller_open_multiple: float = 1.9
    buyer_open_multiple: float = 0.45
    # Floor on the margin we still hold at the end of the concession schedule.
    seller_floor_multiple: float = 1.06
    buyer_floor_multiple: float = 0.94
    concession_exponent: float = 1.5

    # Complete information: shade this far inside the opponent's known limit so
    # the offer leaves them a visible reason to accept.
    zopa_shade: float = 0.04
    # Where the concession schedule ENDS, as our share of the known surplus.
    # This was hard-coded at the midpoint, and a schedule that terminates on an
    # even split is by definition aiming at the median outcome -- which is
    # precisely why complete-information games score at the 50th percentile:
    # 42% of them land on exactly 50.0%.
    #
    # Measured over chunks 12-14 (1,628 games on this code), rejecting an offer
    # paid at every level with no no-deal risk: rejecting 30-40% of the surplus
    # ended at a median 50.0%, rejecting 40-50% ended at 59.2%, and rejecting
    # 50-60% ended at 63.8% -- with 0% of those games ending in a zero. Failures
    # here are structural rather than caused by holding out: of 735 zeros, only
    # 5 (1%) ever had a profitable offer on the table, and complete-information
    # games fail just 2.1% of the time.
    #
    # Set conservatively below what the 40-50% band suggests is reachable. The
    # endgame rules are untouched, so the last rounds still take any positive
    # profit rather than book a $0.
    surplus_target: float = 0.55

    # Accept when the offer is at least this fraction of our current target
    # profit. Below 1.0 so we do not reject an offer that is one dollar shy.
    accept_slack: float = 0.9
    # Last N rounds: any positive profit beats the $0 that a no-deal pays.
    endgame_rounds: int = 2

    unbounded_soft_horizon: int = 10
    # Fallback price scale when our own value is 0 and the opponent has not
    # offered yet, so no other number in the state can set the scale.
    default_scale: float = 100.0

    # Identical prices in a row before we read the opponent as done negotiating
    # and take what is on the table. Replayed over every negotiation game we
    # have: at 6 it rescues the one open-ended game we ground to a 0-0 at the
    # round cap and costs nothing anywhere else, and it still costs nothing all
    # the way out to 12 -- so this sits on a plateau rather than on an edge.
    # Do not lower it to 3: that sells twelve won games for a third of what
    # they paid, because "moving slowly" and "not moving" are different things.
    stonewall_offers: int = 6


@dataclass(frozen=True)
class PersuasionParams:
    # --- Seller -------------------------------------------------------------
    # Fraction of the Bayesian-persuasion lying budget we actually use. The full
    # budget makes the buyer exactly indifferent; an indifferent buyer who is an
    # LLM often passes anyway, so we stay under it.
    lie_budget_use: float = 0.75
    # Lying rate ramps from `lie_ramp_start` x budget early to the full budget
    # at the end, because reputation only has value while rounds remain.
    lie_ramp_start: float = 0.35
    # Used when the seller is not told v and u and so cannot compute the budget.
    blind_lie_rate: float = 0.25
    # Safety margin above the buyer's threshold. Their bar is a knife edge -- at
    # exactly tau they are indifferent, and an indifferent buyer walks -- so the
    # reputation rule holds our credibility this far clear of it while rounds
    # remain. The margin is scaled by the fraction of the game still to play, so
    # it shrinks to nothing on the last round, where there is no reputation left
    # to protect. That replaces the fixed early-honest/late-greedy ramp: the
    # aggression now falls out of what the remaining rounds are worth.
    credibility_margin: float = 0.12
    # A buyer who has refused this many recommendations we KNOW cleared their
    # rational bar is not reading our signal. Reputation with them buys nothing,
    # so there is nothing left to spend it on.
    non_buyer_evidence: int = 6

    # --- Buyer --------------------------------------------------------------
    # Strength of the prior on seller honesty, in pseudo-observations. Low =
    # adapt fast to a liar, high = forgive noise.
    belief_prior_weight: float = 4.0
    # How many rounds of watching before the seller's rationing rate is taken at
    # face value, in the same pseudo-observation units. Separate from the weight
    # above because it governs a different thing: that one is how fast a proven
    # liar loses credit, this one is how fast an unproven rationer earns it.
    # Accuracy is flat between 0 and 10 (9.1%-10.0% median error), so the choice
    # is purely how long we sit out while deciding -- and sitting out is not free
    # here, it is the entire failure being fixed. At 2 the estimate is still
    # conservative (measured bias -1.7%) and crosses a typical bar around round
    # 6 rather than round 12.
    rate_prior_weight: float = 2.0
    # Buy on a marginal expected value during the first rounds: a purchase is
    # the only way to observe quality, and that information prices every later
    # round.
    explore_rounds: int = 2
    explore_tolerance: float = 0.85
    # A seller who signals "no" gives up their own revenue, so the signal is
    # credible; only override it if it has proven to be noise.
    trust_negative_signal: bool = True


BARGAINING = BargainingParams()
NEGOTIATION = NegotiationParams()
PERSUASION = PersuasionParams()
