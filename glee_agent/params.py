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
    # ...and the same floor for an open game where delay costs us nothing. See
    # `floor_accept_share`: the walk down exists to stop a deadlock, but a
    # player who pays nothing to wait is not in one, and 0.35 was conceding the
    # only game type where refusing is genuinely free. 0.50 is the whole of what
    # is there -- 0.60 and 0.70 recover the same 4.95 pot-units in total, as do
    # accept_slack 1.05/1.10 and rounds_to_settle 1/2, so nothing further is
    # bought by reaching higher.
    free_clock_accept_floor: float = 0.50
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
    # Raising this for bounded games only was tried and did not replicate. The
    # first round measured +0.080 (+2.20s) at delta 0.95 and +0.110 (+1.61s) at
    # delta 1.0; the second, against a proper control, measured -0.015 and +0.026,
    # weighting to +0.0025 across the whole bounded half. The untouched OPEN cells
    # in that same run swung -1.84s and +1.81s, which is what a per-cell noise
    # floor looks like at n=50-100 -- and is where the original result came from.

    # How many rounds a rejection really costs before the game settles. Theory
    # says one -- reject, propose, they accept -- but the field haggles: observed
    # play took 7 rounds to move 427k -> 460k on a 1M pot while our own delta of
    # 0.9 burned 47% of the result. Rejecting is priced over this many rounds of
    # inflation, not one, which is what makes an impatient player close early.
    rounds_to_settle: int = 3
    # ...and 3 is measurably too few. Over 23,617 offers we actually refused --
    # every one a paired counterfactual, because accepting is unilateral and
    # terminal, so "sign it now" is `share * delta**(round-1)` and needs no model
    # of the opponent -- refusing stops paying far below where our bar sits:
    #
    #   d_me 0.90 open complete   break-even 0.20   bar 0.505   -0.038/refusal
    #   d_me 0.90  12  complete   break-even 0.20   bar 0.505   -0.020/refusal
    #   d_me 0.95 open complete   break-even 0.20   bar 0.624   -0.014/refusal
    #   d_me 1.00 open hidden     break-even 0.30   bar 0.500   -0.026/refusal
    #
    # No survivorship in that: a no-deal banks zero and is still counted, so the
    # games holding out lost are in the sample. The cost is -0.0055 of pot per
    # game across the whole record.
    #
    # The mechanism is our own clock, not the opponent. At delta 0.95 we sign a
    # NOMINAL 0.667 against an SPE of 0.673 -- the number we negotiate is right --
    # but we take six rounds to get there and inflation eats 23% of it, landing
    # at 0.49 where the field banks 0.64. Pricing a rejection at three rounds
    # when it really takes nine is what buys those six rounds.
    #
    # Offline, over 24,000 simulated games against configurations drawn from the
    # real mix and opponents fitted to the real field, these three together move
    # the percentile +0.031 (about +245 rating) against a +-45 noise floor
    # measured by re-running the shipped policy on six independent worlds. Each
    # response curve is monotone rather than a single lucky point, and the tuned
    # accept bar lands closer to the measured break-even in 3 of 3 cells that
    # move, and further from it in none.
    #
    # Ships OFF: it is still tuning, and tuning in this project has a long record
    # of measuring nothing. It needs its own window on the real server.
    settle_early_on: bool = False
    settle_early_rounds: int = 9
    settle_early_counter_share: float = 0.25
    settle_early_min_accept: float = 0.50
    # Accept at this multiple of our continuation value. Below 1.0 because one
    # more round of inflation is a real cost and the opponent may not concede at
    # all -- both of which are risks on the PREDICTIVE half of the bar. The
    # endgame seat used to run through here too and no longer does; it carries a
    # different risk and is priced by `endgame_sign_rate` instead.
    #
    # 0.97 -> 0.99 by request. Measured first, over 14,000 simulated games on
    # four independent worlds: 0.93/0.95 score 0.6331, and 0.97/0.99/1.00 all
    # score 0.6319 -- a spread of 0.0012 percentile, about 10 rating points,
    # against a +-45 noise floor. It is inert because after the endgame seat
    # moved out, `hold_out_value * accept_slack` is rarely the term the max
    # picks; `stonewall_threshold`, the seat, and `costless_hold_value` usually
    # bind first. Directionally it raises the bar in the delta 0.90/0.95 cells
    # where 23,617 refused offers say the bar is already too high, so if this
    # ever stops being inert it should move the other way.
    accept_slack: float = 0.99
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
    # How often the responder actually signs that final offer. The seat was
    # described as a guarantee -- they choose between our number and $0, so they
    # "have to" take it -- on the strength of four observations. Over the full
    # record it is 1,301 signed of 1,415 (91.9%), and the other 114 took the $0
    # instead. Accepting was strictly better for them in every one of those, so
    # this is not a rational response we can price away by asking for less: at an
    # ask of 0.9 they sign 90.1%, at 1.0 they sign 92.1%. Asking less buys
    # nothing.
    #
    # It matters because the endgame seat is a FLOOR under the accept bar, and a
    # floor worth 91.9% of its nominal value is not the same as one worth 100%.
    # The bar currently shaves it by `accept_slack` (0.97) instead, which is both
    # the wrong number and the wrong reason -- that discount prices "they may
    # never concede", which is exactly the risk the endgame seat does not carry.
    # The risk it does carry is this one.
    endgame_sign_rate: float = 0.919
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
    # ...and the walk-down underneath it undoes that floor almost immediately.
    # An open game is walked toward `min_accept_share` over
    # `unbounded_soft_horizon` = 12 rounds, but the game does not end at 12 -- it
    # ends at 99. Observed live at delta 1.0, open, hidden: the bar is 0.50 at
    # round 1, 0.4625 by round 4, and bottoms out at 0.35 by round 20, where it
    # then sits for seventy-nine more rounds. We took a 50/50 at round 4 of a
    # 99-round game in which waiting cost us exactly nothing.
    #
    # The walk exists because time pressure argues for signing sooner. At delta
    # 1.0 there is no time pressure until the cap, so keying it to a 12-round
    # horizon prices a deadline that is not there. With this on, a costless-delay
    # player walks against the REAL cap instead, and holds `costless_open_share`
    # until the endgame collapse takes over.
    #
    # Note what this does to the evidence against holding. Both earlier
    # measurements -- "rejecting 50-55% gained nothing" over 56 games, and the
    # 23,617-refusal break-even that put this cell at 0.30 -- score refusing
    # against what we ACTUALLY banked afterwards. With the bar collapsing to 0.35
    # by round 20, refusing was always going to look bad: the follow-through was
    # the defect. Neither result rules out holding under a policy that actually
    # holds.
    costless_open_holds_on: bool = False
    costless_open_share: float = 0.57
    # The mirror image, for the open games where waiting is NOT free. That floor
    # raises the bar for a player who pays nothing to wait; this caps it for the
    # one who does. Same measurement that produced it, run per delta over the
    # open half of the record: refusing an offer of this size or better returned
    # -0.0464 of the pot on average across 389 refusals below
    # `costless_delay_delta` (sigma -9.0), and the sign holds in every 0.025
    # band from 0.375 up and in both seats:
    #
    #   delta 0.95   0.40-0.45  -0.021    0.45-0.50  -0.036    0.50-0.55  -0.037
    #   delta 0.90   0.40-0.45  -0.081
    #   delta 1.00   every band POSITIVE, +0.004 to +0.141  <- capped out, see below
    #
    # No-deal rates in those bands run 0.0-1.8%, so this is not the usual
    # survivorship trap: the games where holding out lost are in the sample.
    # `realistic_counter_share` was fitted at 0.45 on 55 games pooled across all
    # regimes, and in the open discounted half it is simply too high -- the
    # equilibrium continuation can push the live bar past 0.50 there, which is
    # how we come to refuse offers worth more than the deal we eventually sign.
    # Only ever a ceiling, and only where delay costs us something: at
    # delta >= `costless_delay_delta` holding out genuinely pays and the cap
    # does not apply.
    discounted_hold_cap: float = 0.425
    # Ships off: this needs its own window, and three accept-bar changes have
    # already failed to replicate. Those all RAISED the bar on a 55-game fit;
    # this lowers it on 389 within-game paired observations, where accepting is
    # unilateral and terminal so the counterfactual needs no model of them.
    discounted_hold_cap_on: bool = False
    # ...and the same ceiling for the games where delay is FREE, which the one
    # above deliberately skips. At delta 1.0 holding out genuinely pays for a
    # long way -- refusing 0.30-0.40 returns +0.150 of pot, 0.40-0.50 +0.029,
    # 0.50-0.60 +0.056 -- so the cap has to sit above all of that, not at 0.425.
    # It turns over hard right after:
    #
    #   refusing >= 0.55   n=364   -0.2122 of pot   sigma  -8.9
    #   refusing >= 0.60   n=263   -0.3057 of pot   sigma  -9.9
    #   refusing >= 0.65   n=245   -0.3281 of pot   sigma -10.1
    #
    # The median round of those refusals is 38-57, so these are exactly the
    # games we drag toward the round cap. They are also where the cap actually
    # bites: at delta 1.0 only 0.44% of open games reach round 99 -- the LOWEST
    # rate of any delta -- but the average offer we had refused in them is 0.485
    # of the pot, against 0.069-0.090 at every other delta. Rare and expensive,
    # because a costless-delay player is the only one who can afford to sit on a
    # high bar forever, and `costless_hold_share` plus the equilibrium
    # continuation puts that bar at 0.7275 in the opening rounds.
    costless_hold_cap: float = 0.60
    # Ships off. This is the arm, not the default -- holding out is measurably
    # right below 0.55 and only wrong above it, so getting the level wrong turns
    # a gain into a loss. Tested on the weakest agent first.
    costless_hold_cap_on: bool = False
    # The server stops an open game dead at this round and pays BOTH sides $0.
    # It is real -- the result carries `round_cap_reached: true` -- and it is not
    # in the documentation, which says these games have no limit. The agent is
    # never told: `horizon_known` stays false, so `rounds_left` returns None all
    # the way to the end and `is_final_round` never fires. Replaying the live
    # build at round 99 it still refuses 0.34, 0.25, 0.10 and banks nothing,
    # which is strictly dominated -- at a true final round any positive offer
    # beats zero. 25 of 3,564 open games in the record ended exactly there.
    open_horizon_cap: int = 99
    # Raising this to 0.75 where their delta was VISIBLE was tried live against
    # an arm holding 0.50, and lost: 0.5527 vs 0.6056 share in the treatment
    # cell, -1.4 sigma, with all three control cells matched inside 0.005. The
    # refusal bands that motivated it were selection, not causation -- we only
    # refuse a 70% offer when the opponent is already collapsing.
    #
    # It could not have worked as built in any case: `never_demand_above` caps
    # the continuation at 0.75, which already dominated, so the accept bar moved
    # 66.5 -> 68.5. Any future attempt at this cell has to go at that cap.

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
    # ...but stop ANSWERING a sweeper with an ask he was never going to take.
    #
    # Game 12416c63: pot 1,000,000, our inflation 0%, theirs 5%, twelve rounds,
    # last word his. He repeated 199,167/800,833 on rounds 2, 4 and 6. We
    # answered 850,000 then 824,698 then 802,270 -- asks that left him 150,000
    # to 197,730 when his own standing demand was 800,833. Not one of them could
    # ever have been signed, so all three rounds were spent for nothing and we
    # took his 199,167 at round 6.
    #
    # A sweeper still has a clock. Repeating his demand costs him a round of his
    # own inflation, so anything above `his demand * his delta` beats waiting for
    # himself -- at 0.95 that is 760,791 against the 800,833 he is holding, and
    # it leaves us 239,209 instead of 199,167. Price off HIS number and HIS
    # inflation rather than our own schedule, and never ask to keep less than he
    # has already offered us, so this can only move our take upward.
    sweep_counter_on: bool = False
    # Strictly above his indifference point, since exactly at it he is free to
    # refuse. A hundredth of his discounted demand is enough to break the tie.
    sweep_counter_sweetener: float = 0.01

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

    # --- not blinking -----------------------------------------------------
    # Complete-information deals split 0.6009 of the surplus our way when THEY
    # signed our price and 0.3132 when we signed theirs, and we signed theirs in
    # half of them. Worst of all is capitulating to a stonewaller: 164 games at
    # 0.2083, reached after a median 15 rounds of holding before folding anyway.
    #
    # `opponent_has_stopped_moving` fires regardless of parity, so it can fold us
    # out of the one seat that cannot be taken from us -- and 216 of 216
    # last-word offers we have ever made were accepted. Off by default; the arm
    # flips it.
    stonewall_respects_ultimatum: bool = False
    # With both valuations visible the surplus is a known quantity, so an offer
    # can be scored against it directly instead of against a schedule. Refuse
    # anything under this fraction of it while road remains. 0.0 disables.
    known_zone_floor: float = 0.0

    # --- seats with no counterparty ---------------------------------------
    # Valuations sit on four rungs -- 80, 100, 120, 150 -- of ONE shared scale.
    # Shared is checked, not assumed: over all 5,035 complete-information games
    # on record both sides are on the same scale every single time, never once
    # crossed. A seller trades only with a buyer above them and a buyer only
    # with a seller below them, so a seller holding the TOP rung and a buyer
    # holding the BOTTOM rung have no counterparty that exists. That is
    # arithmetic on our own visible value and needs nothing about theirs, which
    # is why it survives incomplete information -- where `_no_zone_of_agreement`
    # compared two valuations, saw only one, and gave up.
    #
    # It has therefore never fired. Across 18,210 negotiation games we have sent
    # RejectOffer 83,688 times, AcceptOffer 2,410 times and WalkAway zero times,
    # while grinding these seats out to the round cap:
    #
    #   seat                    games  agreements  mean payoff  turns each
    #   seller on the top rung   1,676     16 (1.0%)   +0.0019      25.8
    #   buyer on the bottom rung 1,611      4 (0.2%)   +0.0003      26.3
    #
    # 3,287 games, 18.1% of all negotiation, 85,705 turns, for a payoff that
    # rounds to zero. None of them ever went NEGATIVE, so this is not about
    # avoiding losses -- walking pays the same zero that grinding pays. It is
    # about the 82,000 turns, because a game that ends on round 1 releases its
    # concurrency slot for a game we can actually win.
    untradable_walk_away: bool = True
    # `WalkAway` is only offered on a decision turn, so when the proposal is
    # ours we still have to name a number. Name one far outside the pool: no
    # price in it can pay us, so a serious offer is strictly wasted, while an
    # absurd one still gets signed occasionally by an opponent not checking. It
    # is a free lottery ticket on the way out -- exactly the 20 agreements above,
    # one of which paid 0.90 of our own value.
    untradable_lottery_multiple: float = 1.9

    # Identical prices in a row before we read the opponent as done negotiating
    # and take what is on the table. Replayed over every negotiation game we
    # have: at 6 it rescues the one open-ended game we ground to a 0-0 at the
    # round cap and costs nothing anywhere else, and it still costs nothing all
    # the way out to 12 -- so this sits on a plateau rather than on an edge.
    # Do not lower it to 3: that sells twelve won games for a third of what
    # they paid, because "moving slowly" and "not moving" are different things.
    stonewall_offers: int = 6
    # ...but only where refusing costs something. Two facts make the branch as
    # written a liability rather than a safeguard.
    #
    # It can ONLY fire in an open game. A bounded negotiation runs at most 10
    # rounds, so the opponent never gets `stonewall_offers` offers in -- measured
    # over the whole record it armed on a profitable price in 243 of 2234 open
    # games and in zero bounded ones. Open games are exactly where it is least
    # defensible: negotiation carries no inflation, so waiting costs nothing but
    # a queue slot, and the game does not end for another 87 rounds.
    #
    # And it overrides our own bar. In the 243 firings we took 0.0718 of our
    # valuation where the schedule said we were holding out for 0.2064, and 240
    # of them ended the game at that price. Observed live: a buyer repeated
    # 81.20 six times against a seller valuing the item at 80, and we signed for
    # 1.20 while our own target stood at 97. Repeating one number six times is
    # the whole exploit.
    #
    # With this on, the branch waits until refusing actually costs us -- the end
    # of a bounded game, or the round cap of an open one.
    #
    # run37 refused them to find out, over 5 hours against four controls. At the
    # moment the gate opens the price on the table is known, so what caving pays
    # is arithmetic rather than inference and every game is its own control --
    # which is what made 23 games enough. The controls validate the arithmetic:
    # they cave on sight, so they must bank exactly the caving number, and over
    # 173 control games the largest deviation was 2.3e-9.
    #
    #   caving would have paid   0.0604 of our valuation
    #   holding actually banked  0.1162
    #   12 games better, 11 exactly equal, 0 worse   (sign test p = 0.00049)
    #   23 of 23 closed -- no no-deals, no walk-aways
    #
    # The eleven ties are the argument. Those are games where they never moved
    # and we signed the same price at round 97-98 instead of round 12; because
    # negotiation has no discount term -- payoff is |price - value|, checked
    # against the cache -- they cost exactly nothing, and the round-cap accept
    # caught all eleven. So caving is weakly dominated: it did not win once.
    #
    # The cost is time, not money: negotiation throughput fell about 20% (96
    # games per slot against 120-130), and 0 walk-aways in 23 only bounds that
    # risk at ~12%. Ships ON.
    stonewall_needs_endgame: bool = True
    # Do not name our own rung in an ask that cannot be accepted.
    #
    # DEAD -- the premise was a survivorship artifact. Kept off, and kept here
    # with the correction, because the mechanism works and only the reason for
    # wanting it was wrong.
    #
    # The claim was that when the final price of the game is theirs our
    # second-to-last ask has no path to closing, so raising it is free. The
    # supporting number -- "they signed that ask ZERO times in 715 bounded
    # games" -- was produced by a scan that required a history entry on the
    # final round:
    #
    #     if not final_entry:
    #         continue
    #
    # A game whose deal closes on the round BEFORE the last never reaches the
    # last round and carries no such entry, so every game where the ask was
    # signed was dropped before the counting began. The statistic was zero by
    # construction and more data would never have moved it.
    #
    # Scored correctly on run37, keyed on `agreed_round == max_rounds - 1`,
    # which exists for every closed game:
    #
    #   controls   29 of 283 asks signed (10.2%)   banked 0.0436 of valuation
    #   arm         3 of  72 asks signed ( 4.2%)   banked 0.0238
    #
    # So the ask closes about a tenth of the time, the flag halves that, and it
    # banked less than all four controls (-2.5 sigma over all bounded games,
    # -0.9 on the incomplete-information subset it is meant to serve). Neither
    # margin clears this project's noise floor alone; what settles it is that
    # the reason it was supposed to be free is false.
    #
    # The mechanism itself is sound and worth reviving if a real motive appears:
    # it cut revealing asks to 10.2% against a 30.8-43.1% control band, and is
    # correctly inert when the opponent already knows our valuation. Note it
    # also only reaches the ladder path -- `_rung_price` returns before the
    # floor when `tradable_rungs` is None or empty.
    hide_rung_from_last_word: bool = False
    # A "never concede past the midpoint" rail was tried here and removed: it
    # cannot bind. The ladder parks at value + 0.85 * (nearest rung - value)
    # and the midpoint is value + 0.50 * (the same), so the ladder is already
    # the stricter of the two wherever a midpoint can be computed at all -- and
    # a midpoint needs `tradable_rungs`, which needs the pool to place us, which
    # is exactly when the ladder runs. Off-pool it returns None and there is
    # nothing to measure against either way.
    # The server stops an open negotiation at this round and pays both $0, the
    # same undocumented cap the bargaining family has. 547 of 2234 open games
    # in the record -- 24.5% -- ended exactly there.
    open_horizon_cap: int = 99


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
    # How far above the buyer's bar to hold the posterior at the knife edge,
    # where p == tau exactly. `regime` refuses to call that market "easy"
    # because recommending everything leaves their posterior sitting ON the bar
    # and an indifferent buyer walks -- one observed game pushed all twenty
    # rounds and sold none. That reasoning is right and the correction it asks
    # for is an epsilon, but the credibility margin was answering it with a
    # half: measured over 1,849 low-quality rounds in the three p == tau cells
    # we recommended on 35-47% of them, where holding the posterior 2% clear of
    # the bar permits 90-97%. Every round we declined there is a sale handed
    # back, because a recommendation moves the buy rate from 3.6% to 89.8%.
    knife_edge_margin: float = 0.02
    # Ration the WHOLE hard market against the realised recommendation mix, the
    # way the knife edge already does, instead of against `posterior_if_caught`.
    #
    # The credibility gate is anchored at p: credibility starts at the prior and
    # only climbs as the buyer BUYS high-quality recommendations. Where p < tau
    # that anchor sits below the bar by construction, and lifting it over
    # requires more bought high rounds than a 20-round game contains. Replaying
    # the live gate over 6,390 interior low rounds, it opens on 6.3% of them --
    # and at margin 0.00 on only 9.7%, so the margin is not what binds. Three of
    # six interior configs are frozen at 0.0%: we never lie in them at all.
    #
    # The mix rule has no p anchor and a fixed point: it admits lies until
    # delivered/recommended falls back to tau, which IS the Kamenica-Gentzkow
    # constraint that the buyer's posterior sit at their bar. Replayed over the
    # same rounds it permits 16.2%, and per config it lands strictly BELOW q*
    # everywhere measured (7.3 vs 12.5, 4.0 vs 10.0, 36.6 vs 50.0, 10.1 vs 20.0,
    # 16.7 vs 25.0, 39.3 vs 80.0) -- more conservative than the optimum, never
    # over it.
    #
    # Default OFF: this needs its own arm with three controls. What it replaces
    # was justified by interior buyers punishing detected lies (56.1% -> 17.0%
    # compliance), and that finding does not survive -- quality is hidden on
    # rounds the buyer passes, so those "lies" were invisible to them. Splitting
    # by what they could actually see reverses it: lies they BOUGHT run 51.5% ->
    # 94.3%, lies they PASSED 59.1% -> 0.5%. The second column is not punishment,
    # it is the definition of a buyer who has stopped buying.
    hard_regime_rations_on_mix: bool = False
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
    # Take every recommendation in the cells where the prior sits ON the bar,
    # instead of buying two rounds and letting them decide the other eighteen.
    #
    # `explore_tolerance` already names this set exactly: p*v is at or under the
    # price (so the branch above did not fire) but within 15% of it. Four cells:
    # (1/3,3.0), (0.5,2.0), (0.8,1.2), (0.8,1.25), all with p*m between 0.96 and
    # 1.00. They are the worst cells we play. Realised percentile today, from
    # the per-game rating_delta:
    #
    #     cell            now    median    optimal   P(finish -)
    #     (1/3, 3.00)    0.405    0.266      0.599       18%
    #     (0.5, 2.00)    0.462    0.344      0.598       17%
    #     (0.8, 1.20)    0.484    0.302      0.613       12%
    #     (0.8, 1.25)    0.496    0.524      0.604       24%
    #
    # Half our (1/3,3.00) games finish in the bottom quarter. The cause is
    # structural: the belief moves only on rounds we BUY, so one unlucky draw in
    # the two explore rounds shuts the game, and shutting it stops the evidence
    # that could reopen it.
    #
    # Pressing is right because a recommendation here is a FAVOURABLE bet, not a
    # break-even one. Blind buying is break-even by construction (p*m ~ 1), but
    # we are not buying blind -- conditional on the seller recommending, the hit
    # rate q beats p, and the expected value per purchase is positive in all
    # four:
    #
    #     cell           q     good pays   bad costs   EV per buy
    #     (1/3, 3.00)  0.559     +2.00x      -1.00x      +0.677x
    #     (0.5, 2.00)  0.714     +1.00x      -1.00x      +0.428x
    #     (0.8, 1.20)  0.909     +0.20x      -1.00x      +0.091x
    #     (0.8, 1.25)  0.901     +0.25x      -1.00x      +0.126x
    #
    # So there is no argument for stopping at break-even: every further round is
    # a bet we are favoured on, in a game where more money is a better rank.
    # Stopping when clear was measured and loses -- 0.403 against 0.600 in
    # (1/3,3.00), 0.390 against 0.597 in (0.5,2.00).
    #
    # Deliberately NOT extended below `explore_tolerance`. In the five frozen
    # cells the same reasoning fails: 43-65% of the field banks exactly zero
    # there, so a zero already scores 0.44-0.49 and is close to Elo-neutral,
    # while q sits under the bar. Four of those five are a pass; the fifth,
    # (1/3,2.00), is `rationing_belief`'s.
    press_recommendations: bool = False
    # ...but stop once far enough ahead, where a purchase is thin and the
    # percentile curve has flattened. Only bites at m < `press_cap_below_m`: a
    # good buy pays just 0.2-0.25x there, so past 5x banked the variance is no
    # longer bought with anything. Swept over thresholds 0/1/2/3/5/8/none, 5x
    # was best at m=1.2 and 1.25 and "none" best at m>=2.
    press_profit_cap: float = 5.0
    press_cap_below_m: float = 1.5
    # Read the seller's rationing when no purchase has been made to read
    # instead. `_buyer_credibility` only updates on rounds we BUY, so in a cell
    # whose prior starts under the buyer's bar it never updates: we decline,
    # learn nothing, and decline for the rest of the game. Five of the fifteen
    # cells sit there -- the explore gate needs p*m >= 0.85 to take a first
    # read, and these are below it -- which is 5,355 of our 15,827 buyer games
    # banking exactly zero:
    #
    #     p      m      p*m     field buyer earns   below zero
    #     0.33   1.20   0.400        +0.0049           5.3%
    #     0.33   1.25   0.417        +0.0106           5.8%
    #     0.33   2.00   0.667        +0.1244           7.0%
    #     0.50   1.20   0.600        +0.0261           3.2%
    #     0.50   1.25   0.625        +0.0321           7.7%
    #
    # (per unit staked, measured off the opposing buyer in our own seller
    # games). The field clears zero in every one, so our zero is last place.
    #
    # `signal_posterior` computes the belief this needs and was unwired for
    # losing money -- p/rate is a CEILING, exact only if the seller praises
    # every high unit, and it had been validated only on rounds we already
    # wanted to buy. Both objections are now answered on unselected data. In
    # the six cells where p*v > price our buyer takes EVERY recommendation, so
    # the rate never touches the decision there:
    #
    #   h, the share of HIGH units the field praises, over 10 cells:  1.015
    #     (sd 0.039 -- the ceiling is essentially tight, not merely a bound)
    #   p/rate against realised quality over 28 cell-buckets:  +0.0010 (sd 0.043)
    #   the RUNNING belief, bucketed by what it held going into each round:
    #     +0.0389 (sd 0.0139) over 7 buckets, conservative in every one
    #
    # And the rationing is a strong signal, not noise: sellers praising 25% of
    # rounds come in 91.1% high, those praising 99% come in 66.4%.
    #
    # Ships off. What a replay cannot price is whether buying changes how the
    # seller plays the rest of the game, so this needs a real A/B.
    rationing_belief: bool = False
    # Surplus the rationing belief must clear, on top of the price. The estimate
    # saturates optimistically where p/rate hits its cap, so do not buy at the
    # indifference point -- but the margin is doing more work than that here.
    #
    # Four of the five frozen cells fail the ceiling test: pooled over the cell,
    # p/P(rec) sits BELOW the buyer's bar, so even a seller praising every high
    # unit would not on average offer a recommendation worth taking. Buying
    # there is a bet on picking the honest tail WITHIN the cell, which is
    # precisely the bet that sank this idea last time, and nothing in our logs
    # can confirm it. Swept over the frozen games:
    #
    #     margin   backed games   backed value   speculative   spec share
    #      0.05         799           2218           670          23%
    #      0.10         794           2204           308          12%
    #      0.15         768           2154             0           0%
    #
    # 0.15 keeps 97% of the backed value and takes the speculative exposure to
    # exactly zero, with no cell-specific code: together with `rationing_cap`
    # it puts the required belief above 0.95 in two of those cells, which is
    # unreachable by construction, and no game reaches it in the other two.
    #
    # The asymmetry settles it. Field buyers earn only +0.005 to +0.032 per unit
    # staked in the four thin cells against +0.124 in the backed one, so winning
    # the bet barely moves a percentile and losing it puts us under the 3-8% of
    # buyers who finish below zero.
    rationing_margin: float = 0.15
    # p/rate saturates at 1.0 and is optimistic by 0.03-0.08 when it does; hold
    # it below so a seller who rations hard early cannot pin the belief at
    # certainty.
    rationing_cap: float = 0.95
    # A seller who signals "no" gives up their own revenue, so the signal is
    # credible; only override it if it has proven to be noise.
    trust_negative_signal: bool = True
    # Send the text-mode recommendation as a bare "Recommended." / "Not
    # recommended." -- the same two words the binary half of these games sends
    # as a yes/no -- instead of the pitch with track record and arithmetic.
    #
    # The server draws the channel per game, roughly half `binary` and half
    # `text`, and it is drawn independently of the opponent, so the two halves
    # face the same buyers. Our sell rate does not survive the crossing:
    #
    #     v/price   binary    text     text - binary
    #       1.2     0.3381   0.2336       -0.1044
    #       2.0     0.6686   0.5103       -0.1583
    #       3.0     0.7987   0.6203       -0.1784
    #       4.0     0.8654   0.7377       -0.1276
    #
    # Same direction in every band, n=459-1001 per cell. And text is not simply
    # harder: the field sells MORE in text than in binary (0.8887 against our
    # buyer, versus 0.8492). It is harder only for us. In text games where blind
    # buying already pays we sell 0.7286 against the field's 0.8887 -- the only
    # cell in persuasion where we lose to the field at all.
    #
    # The reading is that a large part of the field matches on tokens rather
    # than reading prose, so a recommendation that arrives as a sentence does
    # not arrive at all. Our own buyer is the same shape: `_is_positive` matches
    # a hand-written list of 38 negative phrases.
    #
    # Whether a buyer answers "Recommended." the way it answers "yes" is THEIR
    # move, so no replay can price this and it ships off, behind a real A/B.
    bare_recommendation: bool = False


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
