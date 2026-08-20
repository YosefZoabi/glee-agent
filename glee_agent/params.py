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
    # ...but that 0.50 was measured with the patience cells pooled, and they do
    # not behave alike. Re-run with them split, over unbounded games only, what
    # refusing an offer in a band finally paid:
    #
    #   their delta VISIBLE and no worse than ours
    #     refused 0.50-0.55   n=206   ended 0.594  (+0.069)   0% no-deal
    #     refused 0.65-0.75   n= 94   ended 0.949  (+0.249)   0% no-deal
    #   their delta HIDDEN, ours 1.0
    #     refused 0.65-0.75   n= 93   ended 0.000  (-0.700) 100% no-deal
    #
    # Same behaviour, opposite outcome, and averaging the two is what produced a
    # single flat floor. Holding out is nearly free when we can SEE they are the
    # impatient one and ruinous when we are guessing -- which is also the honest
    # reading of the 49 games that banked $0 and put the cap in `never_demand_above`
    # in the first place: every one of them was an incomplete-information game.
    # So the floor rises only where the deltas are facts.
    # Set at the top of the evidenced band rather than its floor: the bar only
    # ever REFUSES below itself, so 0.75 declines exactly the offers the 94
    # refusals above covered, and nothing beyond them. Still under the 0.867
    # Rubinstein share for this cell, so it is not asking for more than the
    # structure supports.
    costless_hold_share_informed: float = 0.75

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
    # Raised from 0.55 after a controlled read against an arm running 0.59.
    # Complete-information bounded games went 0.550 -> 0.590 of the surplus at
    # an unchanged deal rate (96.4% -> 96.9%), and open ones 0.500 -> 0.590 for
    # 5.8 points of deal rate -- still positive once a no-deal is priced at the
    # 5th percentile it actually scores. The incomplete-information cells, which
    # this parameter cannot touch, matched across the two agents (33.6% vs
    # 34.6% bounded), which is what says the gap is the change and not the draw.
    # 0.59 -> 0.65 on a within-agent read: the same arm ran 0.59 then 0.65 over
    # consecutive chunks and the deal rate went UP, not down -- bounded 97.3% ->
    # 97.8%, open 96.2% -> 98.4% -- while the surplus taken rose 0.590 -> 0.650.
    # The incomplete-information cells, which this cannot touch, moved 33.6% ->
    # 32.5%, which is what says the comparison is sound. The edge is still
    # somewhere above here; an arm is testing 0.72.
    surplus_target: float = 0.65

    # Accept when the offer is at least this fraction of our current target
    # profit. Below 1.0 so we do not reject an offer that is one dollar shy.
    accept_slack: float = 0.9
    # Last N rounds: any positive profit beats the $0 that a no-deal pays.
    endgame_rounds: int = 2

    unbounded_soft_horizon: int = 10
    # An offer below our own value is not an offer, it is an anchor: signing it
    # pays us less than walking away. 69.4% of open-ended games open with one,
    # so a schedule that advanced on them spent most of its concessions before
    # the negotiation had started.
    #
    # Of the opponents who ever cross into a price we could sign, 64% have done
    # it by their third offer and 100% by their eighth -- and 91% of those games
    # then closed. So the first eight offers of a lowball carry no information
    # worth conceding to. Past eight, nobody has ever crossed, and continuing to
    # freeze would just hold our opening ask forever in the 52.8% of games where
    # they never come up at all, so the clock starts regardless.
    anchor_grace: int = 8
    # Fallback price scale when our own value is 0 and the opponent has not
    # offered yet, so no other number in the state can set the scale.
    default_scale: float = 100.0

    # --- Pricing against a known pool -------------------------------------
    # Valuations are not continuous. Every negotiation game we have ever played
    # draws both values from {80, 100, 120, 150} times one of three scales, and
    # 3,510 incomplete-information games contained not a single off-pool value.
    # Roles are assigned independently of the values, so the opponent sits on a
    # uniform draw over the same four rungs and a surplus exists in only 37.5%
    # of games -- which is why our 36.1% deal rate is already 96% of the
    # ceiling, and why the remaining money is in the PRICE, not the close.
    #
    # The lever: a deal is possible only when their rung is above ours (selling)
    # or below ours (buying). Conditioning on that collapses the posterior, and
    # at the rung next to the end of the pool it collapses to a single number --
    # a seller holding 120 can only ever trade with a buyer holding 150. Asking
    # just under 150 there costs nothing, because every other draw was
    # unwinnable regardless of what we asked. We currently ask 1.06 x our own
    # value and take 34.6% of that surplus.
    #
    # Measured live 2026-08-19 against an arm identical but for this flag: in
    # incomplete-information games it took 0.722 of the surplus against 0.478
    # (+3.9 sigma, n=30/35) with both sides closing 100% of the games that had
    # a surplus to close. The complete-information cells, which this flag cannot
    # reach, drifted +1.8 sigma on the same draw, so differencing that out as
    # pure luck still leaves +1.8 sigma. On by default from that run.
    rung_aware: bool = True
    # Leave this much of the target rung to the opponent so signing beats
    # walking. Their best offer reaches a median 1.06x their own valuation, so
    # they do not need much, but they do need something visible.
    # Complete-information games close at 96%+ while leaving the opponent 41%
    # of the surplus, so 6% was not a number anyone had earned. Start where we
    # still take the large majority and let the arm find the edge.
    rung_shade: float = 0.15
    # ...but not when the offer is the last word. Rejecting an ultimatum pays
    # them zero and signing pays them whatever we left, and the field does the
    # arithmetic: 216 last-word offers, 216 signed, including 10 that left them
    # only 15-30%. We were shading them 15% anyway, and 206 of those 216 handed
    # over more than HALF the surplus on offers they could not refuse.
    #
    # Bargaining already proved the same point from the other side --
    # `final_round_demand` takes 97% on the last round and the arm that tried
    # leaving 12% instead came back a null.
    #
    # Held at 1% of the room rather than literally one unit: the pool spans
    # three scales, so a flat 1 is 1.25% of the smallest rung and 0.0001% of the
    # largest, which is not the same offer at all.
    rung_last_word_shade: float = 0.01

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


# Every family is played as though the free-text channel did not exist.
#
# In bargaining and negotiation the message rides alongside a number that says
# the same thing, so dropping it costs nothing and removes a channel we were
# using to volunteer things about ourselves -- the schedule told a 0%-inflation
# opponent that "every round shrinks the pot for both of us", which is a claim
# of time pressure we do not have, made to the only side that does.
#
# Persuasion is not the same shape. Half its rounds use a `binary` channel that
# is already a bare yes/no with no text at all; the other half use `text`, where
# the message IS the move and there is no number to send instead -- an empty one
# is refilled by `safety.sanitize` rather than sent. So text mode carries the
# recommendation and nothing else, which is exactly what the binary half sends.
# Kept ON by explicit decision 2026-08-19. The seller half of persuasion is
# measurably inert -- buyers bought 0.693 of the time when we recommended and
# 0.689 when we did not, over 1,420 rounds -- but the bargaining and negotiation
# halves were never measured, and turning the channel off everywhere left no
# control to measure them with.
SEND_MESSAGES = True

BARGAINING = BargainingParams()
NEGOTIATION = NegotiationParams()
PERSUASION = PersuasionParams()
