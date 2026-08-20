import pytest

from glee_agent.params import NEGOTIATION as P
from glee_agent.strategies.negotiation import play
from tests.fixtures import negotiation_game


class TestOffers:
    def test_seller_never_asks_below_its_own_value(self):
        for round_ in range(1, 7):
            action = play(negotiation_game(slot="player_1", my_value=40, round_=round_))
            assert action["product_price"] >= 40

    def test_buyer_never_bids_above_its_own_value(self):
        for round_ in range(1, 7):
            action = play(negotiation_game(slot="player_2", my_value=100, round_=round_))
            assert action["product_price"] <= 100

    def test_seller_concedes_over_time(self):
        early = play(negotiation_game(slot="player_1", my_value=40, round_=1))["product_price"]
        late = play(negotiation_game(slot="player_1", my_value=40, round_=5))["product_price"]
        assert late < early

    def test_complete_information_opens_just_inside_the_opponents_limit(self):
        action = play(negotiation_game(slot="player_1", my_value=40, opponent_value=100, round_=1))
        # Under the buyer's maximum, but only just -- and well clear of our own.
        assert 90 < action["product_price"] < 100

    def test_asks_only_ever_come_down(self):
        # Re-anchoring upward after a concession restarts the negotiation.
        history = [{"round": 1, "offer": {"price": 55.0, "from_player": "player_1"}, "decision": "RejectOffer"}]
        action = play(negotiation_game(slot="player_1", my_value=40, round_=2, history=history))
        assert action["product_price"] <= 55.0

    def test_message_omitted_when_the_game_forbids_them(self):
        assert "message" not in play(negotiation_game(messages_allowed=False))


class TestDecisions:
    def _offer(self, price, **kwargs):
        return negotiation_game(
            action_type="decision",
            last_offer={"price": price, "from_player": "player_2", "round": 1},
            **kwargs,
        )

    def test_seller_rejects_an_unprofitable_price(self):
        action = play(self._offer(20, slot="player_1", my_value=40, round_=1))
        assert action["decision"] == "RejectOffer"
        assert action["product_price"] >= 40

    def test_seller_accepts_a_generous_price(self):
        assert play(self._offer(200, slot="player_1", my_value=40))["decision"] == "AcceptOffer"

    def test_thin_profit_beats_no_deal_on_the_last_round(self):
        action = play(self._offer(41, slot="player_1", my_value=40, round_=6, max_rounds=6))
        assert action["decision"] == "AcceptOffer"

    def test_final_round_rejection_carries_no_counteroffer(self):
        # There is no round left to counter into; a bare rejection ends the game.
        action = play(self._offer(10, slot="player_1", my_value=40, round_=6, max_rounds=6))
        assert action == {"decision": "RejectOffer"}

    def test_walks_away_when_no_price_can_pay_both(self):
        # Seller values it above the buyer: no trade is the correct outcome.
        action = play(self._offer(45, slot="player_1", my_value=60, opponent_value=40))
        assert action["decision"] == "WalkAway"

    def test_buyer_side_reads_its_own_direction(self):
        assert play(self._offer(95, slot="player_2", my_value=100, round_=1))["decision"] == "RejectOffer"
        assert play(self._offer(5, slot="player_2", my_value=100))["decision"] == "AcceptOffer"

    @pytest.mark.parametrize("slot,my_value", [("player_1", 40), ("player_2", 100)])
    def test_never_counters_into_a_loss(self, slot, my_value):
        for round_ in range(1, 7):
            action = play(self._offer(50, slot=slot, my_value=my_value, round_=round_))
            price = action.get("product_price")
            if price is None:
                continue
            assert price >= my_value if slot == "player_1" else price <= my_value


class TestTakeItOrLeaveIt:
    """Regression: game 65487191, a 1-round game, opened at 1.9x value and paid $0.

    `progress` is (round - 1) / horizon, so round 1 of a 1-round game scores 0 --
    the very start of the concession schedule -- even though it is also the last
    word. The horizon, not the clock, has to decide.
    """

    def test_single_round_seller_prices_to_be_accepted(self, schedule_only):
        action = play(negotiation_game(slot="player_1", my_value=80, round_=1, max_rounds=1))
        # The floor multiple, not the 1.9x opening anchor that lost the game.
        assert action["product_price"] < 80 * P.seller_open_multiple
        assert action["product_price"] == pytest.approx(80 * P.seller_floor_multiple)

    def test_single_round_buyer_prices_to_be_accepted(self, schedule_only):
        action = play(negotiation_game(slot="player_2", my_value=100, round_=1, max_rounds=1))
        assert action["product_price"] > 100 * P.buyer_open_multiple
        assert action["product_price"] == pytest.approx(100 * P.buyer_floor_multiple)

    def test_single_round_offer_is_still_profitable(self, schedule_only):
        seller = play(negotiation_game(slot="player_1", my_value=80, round_=1, max_rounds=1))
        assert seller["product_price"] > 80
        buyer = play(negotiation_game(slot="player_2", my_value=100, round_=1, max_rounds=1))
        assert buyer["product_price"] < 100

    def test_final_round_of_a_long_game_prices_the_same_way(self, schedule_only):
        # Not a special case for max_rounds == 1: any last word is a last word.
        action = play(negotiation_game(slot="player_1", my_value=80, round_=6, max_rounds=6))
        assert action["product_price"] == pytest.approx(80 * P.seller_floor_multiple)

    def test_a_real_horizon_still_opens_high(self, schedule_only):
        # The fix must not flatten the schedule everywhere.
        action = play(negotiation_game(slot="player_1", my_value=80, round_=1, max_rounds=6))
        assert action["product_price"] > 80 * 1.5

    def test_single_round_complete_information_splits_the_zone(self):
        action = play(
            negotiation_game(slot="player_1", my_value=40, opponent_value=100, round_=1, max_rounds=1)
        )
        # No rounds left to shade toward, so the schedule runs to its terminus.
        # That used to be the midpoint (70.0); it is now `surplus_target` of the
        # zone, because a schedule ending on an even split is aiming at the
        # median outcome by construction. Still comfortably signable: at 73 the
        # buyer keeps 27 of a 60-wide zone against 0 for refusing.
        assert action["product_price"] == pytest.approx(40 + P.surplus_target * 60)
        assert 40 < action["product_price"] < 100


class TestAStandingOfferFromSomeoneWhoHasStoppedNegotiating:
    """Regression: 85bd702f, an open-ended game we ground to 0-0 at round 99.

    Our cost 800,000, their value 1,000,000. They offered 815,000 -- worth
    15,000 to us -- in round 2 and then repeated it, to the cent, forty-nine
    times. We held 900,000 just as long, and the round cap paid us both nothing.
    A bounded game has the endgame rule to stop this; an open-ended one never
    runs out of road, so the stopping condition has to come from them.

    The bar is deliberately "unchanged to the cent". 3ee13da4 is the same
    configuration, the same opening and the same 900,000 hold by us, and it paid
    100,000 -- because that buyer crept 806,000 -> 810,937 and then signed our
    price at round 69. Replayed over every negotiation game we have, a
    six-offer bar rescues the first and costs nothing on the second; a
    three-offer bar sells twelve won games for a third of what they paid.
    """

    def _game(self, price, repeats, **kwargs):
        history = [
            {"round": r, "offer": {"price": price, "from_player": "player_2", "round": r},
             "decision": "RejectOffer", "decided_by": "player_1"}
            for r in range(1, repeats + 1)
        ]
        return negotiation_game(
            action_type="decision", slot="player_1", my_value=800_000,
            round_=repeats + 1, max_rounds=None, history=history,
            last_offer={"price": price, "from_player": "player_2", "round": repeats + 1},
            **kwargs,
        )

    def test_takes_the_offer_once_they_have_stopped_moving(self):
        assert play(self._game(815_000, 8))["decision"] == "AcceptOffer"

    def test_holds_out_while_they_are_still_moving(self):
        # One cent of movement is still movement: this is the 3ee13da4 shape,
        # and holding out is what paid 100,000 there.
        creeping = [
            {"round": r, "offer": {"price": 806_000 + r * 500, "from_player": "player_2", "round": r},
             "decision": "RejectOffer", "decided_by": "player_1"}
            for r in range(1, 9)
        ]
        game = negotiation_game(
            action_type="decision", slot="player_1", my_value=800_000,
            round_=9, max_rounds=None, history=creeping,
            last_offer={"price": 810_500, "from_player": "player_2", "round": 9},
        )
        assert play(game)["decision"] == "RejectOffer"

    def test_a_short_run_of_repeats_is_not_enough(self):
        assert play(self._game(815_000, 2))["decision"] == "RejectOffer"

    def test_never_takes_a_stonewalled_offer_that_loses_money(self):
        # They can repeat 790,000 as long as they like; it is still below cost.
        assert play(self._game(790_000, 20))["decision"] == "RejectOffer"

    def test_zero_profit_is_not_positive_profit(self):
        # Their price parked exactly on our valuation pays the same as walking.
        assert play(self._game(800_000, 20))["decision"] == "RejectOffer"

    def test_our_own_repeated_price_does_not_count_as_theirs(self):
        # We were repeating 900,000 just as stubbornly; only their side counts.
        ours = [
            {"round": r, "offer": {"price": 900_000, "from_player": "player_1", "round": r},
             "decision": "RejectOffer", "decided_by": "player_2"}
            for r in range(1, 12)
        ]
        game = negotiation_game(
            action_type="decision", slot="player_1", my_value=800_000,
            round_=12, max_rounds=None, history=ours,
            last_offer={"price": 815_000, "from_player": "player_2", "round": 12},
        )
        assert play(game)["decision"] == "RejectOffer"


class TestTheScheduleNoLongerAimsAtTheMedian:
    """Chunks 12-14, 1,628 games: complete-info deals sat on exactly 50.0%.

    The schedule terminated on `(my_value + opponent_value) / 2`, and a policy
    that ends on an even split is aiming at the median by construction -- which
    is why those games scored at the 50th percentile, with 42% of them landing
    on 50.0% to the cent.

    Holding out was measured to pay at every level, with no no-deal risk:
    rejecting 30-40% of the surplus ended at a median 50.0%, rejecting 40-50%
    ended at 59.2%, rejecting 50-60% ended at 63.8%, and 0% of those games ended
    in a zero. Failing to close here is structural, not caused by firmness: of
    735 zeros only 5 (1%) ever had a profitable offer on the table.
    """

    def _final_price(self, *, role, my_value, opponent_value):
        slot = "player_1" if role == "seller" else "player_2"
        return play(negotiation_game(
            slot=slot, my_value=my_value, opponent_value=opponent_value,
            round_=1, max_rounds=1,
        ))["product_price"]

    def test_the_seller_lands_above_the_midpoint(self):
        price = self._final_price(role="seller", my_value=40, opponent_value=100)
        assert price > 70.0
        assert price == pytest.approx(40 + P.surplus_target * 60)

    def test_the_buyer_lands_below_the_midpoint(self):
        # Symmetric: `span` is negative for a buyer, so the same share moves the
        # price the other way. Getting this backwards would concede MORE.
        price = self._final_price(role="buyer", my_value=100, opponent_value=40)
        assert price < 70.0
        assert price == pytest.approx(100 - P.surplus_target * 60)

    def test_both_roles_capture_the_same_share_of_surplus(self):
        seller = self._final_price(role="seller", my_value=40, opponent_value=100) - 40
        buyer = 100 - self._final_price(role="buyer", my_value=100, opponent_value=40)
        assert seller == pytest.approx(buyer)
        assert seller / 60 == pytest.approx(P.surplus_target)

    def test_it_still_leaves_them_a_reason_to_sign(self):
        # The whole zone must never be taken -- they need positive profit or
        # refusing costs them nothing.
        for mv, ov in ((40, 100), (8000, 15000), (800_000, 1_000_000)):
            price = self._final_price(role="seller", my_value=mv, opponent_value=ov)
            assert mv < price < ov

    def test_the_endgame_still_takes_any_positive_profit(self):
        # The safety net is untouched: on the last round a thin profit beats $0.
        game = negotiation_game(
            action_type="decision", slot="player_1", my_value=8000,
            opponent_value=15000, round_=10, max_rounds=10,
            last_offer={"price": 8100, "from_player": "player_2", "round": 10},
        )
        assert play(game)["decision"] == "AcceptOffer"


class TestRungAwarePricing:
    """Valuations come from a four-rung pool, so the opponent is not unknown.

    Every negotiation game draws both valuations from {80, 100, 120, 150} times
    one of three scales -- 3,510 incomplete-information games contained zero
    off-pool values. Roles are assigned independently of the values, so a deal
    exists only when their rung is above ours selling, or below ours buying.
    Conditioning on that is what turns "unknown opponent" into a short list.
    """

    def _offer(self, role, value, round_=1, max_rounds=10, history=None):
        slot = "player_1" if role == "seller" else "player_2"
        game = negotiation_game(slot=slot, my_value=value, round_=round_,
                                max_rounds=max_rounds, history=history or [])
        return play(game)["product_price"]

    def test_on_by_default(self):
        # Guards the SHIPPED default. An arm that deliberately flips the
        # switch is expected to fail exactly this one test and nothing else.
        # Shipped on 2026-08-19 on +3.9 sigma of surplus in the cell it acts on.
        assert P.rung_aware is True

    def test_a_seller_one_rung_down_knows_the_buyer_exactly(self, rung_aware):
        # Holding 120, the only buyer we can ever trade with holds 150. Every
        # other draw pays zero whatever we ask, so we ask against 150.
        price = self._offer("seller", 120.0)
        assert 120.0 < price < 150.0
        assert price > 140.0                      # aimed at 150, not at our own value

    def test_a_buyer_one_rung_up_knows_the_seller_exactly(self, rung_aware):
        price = self._offer("buyer", 100.0)
        assert 80.0 < price < 100.0
        assert price < 90.0                       # aimed at 80, not at our own value

    def test_it_scales_with_the_pool(self, rung_aware):
        small = self._offer("seller", 120.0)
        large = self._offer("seller", 1_200_000.0)
        assert large == pytest.approx(small * 10_000.0, rel=1e-6)

    def test_the_ladder_walks_down_as_rounds_pass(self, rung_aware):
        early = self._offer("seller", 80.0, round_=1)
        late = self._offer("seller", 80.0, round_=8)
        assert late < early                       # asks only ever come down

    def test_an_untradable_seat_falls_back_to_the_schedule(self, rung_aware):
        # A seller already holding the top rung can never meet a richer buyer.
        # There is nothing to price for, so the ordinary schedule takes over
        # rather than the ladder inventing a target that does not exist.
        from glee_agent.strategies.negotiation import tradable_rungs
        state = negotiation_game(slot="player_1", my_value=150.0)["game_state"]
        assert tradable_rungs(state, "player_1", "seller") == []
        assert self._offer("seller", 150.0) > 150.0

    def test_an_off_pool_value_falls_back_to_the_schedule(self, rung_aware):
        from glee_agent.strategies.negotiation import pool_position
        assert pool_position(137.0) is None
        assert self._offer("seller", 137.0) > 137.0

    def test_the_last_offer_never_un_concedes(self, rung_aware):
        # The final round picks the best-expected-value rung, which can sit
        # above where the ladder had already walked to. Monotonicity has to
        # win: raising the ask on the one round that cannot be redone is how
        # a won game becomes a zero.
        history = [{"offer": {"from_player": "player_1", "price": 97.0, "round": 8}}]
        price = self._offer("seller", 80.0, round_=10, max_rounds=10, history=history)
        assert price <= 97.0

    def test_we_still_leave_them_a_reason_to_sign(self, rung_aware):
        # Pricing at exactly their valuation pays them nothing and buys a refusal.
        assert self._offer("seller", 120.0) < 150.0
        assert self._offer("buyer", 100.0) > 80.0


class TestTheChannelIsNotUsed:
    """We price as though the free-text channel were not there."""

    def test_an_offer_carries_no_message(self, messages_off):
        assert "message" not in play(negotiation_game(messages_allowed=True))

    def test_a_counter_carries_no_message(self, messages_off):
        action = play(negotiation_game(
            action_type="decision", slot="player_1", my_value=100.0, round_=2,
            messages_allowed=True,
            last_offer={"price": 90.0, "from_player": "player_2", "round": 1},
        ))
        assert "message" not in action

    def test_the_builders_still_work_if_the_judgement_is_reversed(self, messages_on):
        assert "message" in play(negotiation_game(messages_allowed=True))


class TestTheLastWordIsAnUltimatum:
    """Rejecting our last offer pays them zero, so it is sliced to a crumb.

    Measured over every last-word offer we have made: 216 sent, 216 signed,
    including ten that left the opponent only 15-30%. The shade that protects a
    mid-game offer buys nothing on a round they cannot answer.
    """

    def _ask(self, role, value, round_, max_rounds, **kw):
        slot = "player_1" if role == "seller" else "player_2"
        return play(negotiation_game(slot=slot, my_value=value, round_=round_,
                                     max_rounds=max_rounds, **kw))["product_price"]

    def test_a_selling_ultimatum_lands_just_under_a_rung(self, rung_aware):
        price = self._ask("seller", 100.0, 10, 10)
        assert 149.0 < price < 150.0          # just inside the 150 buyer, not 15% under

    def test_a_buying_ultimatum_lands_just_over_a_rung(self, rung_aware):
        price = self._ask("buyer", 150.0, 10, 10)
        assert 100.0 < price < 101.0

    def test_the_crumb_scales_with_the_pool(self, rung_aware):
        assert 1_490_000 < self._ask("seller", 1_000_000.0, 10, 10) < 1_500_000

    def test_a_tie_breaks_toward_the_rung_more_opponents_can_sign(self, rung_aware):
        # A buyer on 120 has two live rungs and they tie exactly on expected
        # value: the extra profit of aiming at 80 cancels the extra chance of
        # aiming at 100. Breaking that toward 80 asks the ONE seller who could
        # sign it for almost everything and writes off the other half of the
        # pool on the round that cannot be redone.
        assert 100.0 < self._ask("buyer", 120.0, 10, 10) < 101.0

    def test_the_ultimatum_may_ask_more_than_the_offer_before_it(self, rung_aware):
        # The mid-game ladder walks DOWN through the rungs while refusals are
        # still affordable, so by the last round it can sit below the rung with
        # the best expected value. Stepping back up there is correct and is not
        # the un-conceding bug: a last offer is priced on what it is worth, not
        # on what we happened to ask before it. The field bears it out -- 216
        # last-word offers, 216 signed.
        assert self._ask("seller", 100.0, 9, 10) < self._ask("seller", 100.0, 10, 10)

    def test_a_mid_game_offer_keeps_its_shade(self, rung_aware):
        # The crumb is for the ultimatum only: with rounds still in hand a
        # refusal is affordable and the field refuses thin offers 78% of the time.
        assert self._ask("seller", 120.0, 3, 10) < 149.0


class TestTheClockTicksOnTheirSilence:
    """Open-ended games: concede because they stopped moving, not because time passed.

    They run to round 99 while our schedule was spent by round 11. Holding a
    price costs nothing -- they improve on 65-70% of rounds however long we
    stonewall, and the move grows from +31% after two rounds to +64% after
    twelve -- while their own stall is the real signal: after four repeats only
    9.9% ever concede again, after eight 5.8%.
    """

    def _ask(self, their_prices, my_value=80.0):
        hist = [{"offer": {"price": p, "from_player": "player_2", "round": i + 1}}
                for i, p in enumerate(their_prices)]
        game = negotiation_game(
            slot="player_1", my_value=my_value, round_=len(their_prices) + 1,
            max_rounds=None, history=hist,
            last_offer={"price": their_prices[-1], "from_player": "player_2",
                        "round": len(their_prices)})
        return play(game)["product_price"]

    def test_we_do_not_move_while_they_are_still_moving(self, rung_aware):
        early = self._ask([90])
        late = self._ask([90, 95, 100, 105, 110, 115, 120, 125])
        assert late == early          # eight rounds in and not a cent conceded

    def test_a_long_stall_walks_us_down_the_ladder(self, rung_aware):
        assert self._ask([90] * 8) < self._ask([90] * 2)

    def test_conceding_tracks_stalled_rounds_not_elapsed_rounds(self, rung_aware):
        # Same round number, opposite behaviour from them.
        moving = self._ask([90, 95, 100, 105, 110, 115, 120, 125])
        stalled = self._ask([90, 90, 90, 90, 90, 90, 90, 90])
        assert stalled < moving

    def test_an_opening_lowball_does_not_spend_the_schedule(self, rung_aware):
        # 69.4% of open-ended games open below our own value. Signing there pays
        # less than walking, so those rounds are theatre, not negotiation.
        assert self._ask([10] * 6) == self._ask([10])

    def test_the_anchor_phase_is_free(self, rung_aware):
        # Four rounds of lowball then a real offer must leave us exactly where we
        # would have been had the real offer come first.
        assert self._ask([10, 10, 10, 10] + [90] * 6) == self._ask([90] * 6)

    def test_a_permanent_lowballer_does_not_freeze_us_forever(self, rung_aware):
        # 52.8% never cross. Holding the opening ask for all 99 rounds against
        # them would trade a bad price for no price, so the grace runs out.
        assert self._ask([10] * 14) < self._ask([10] * 6)

    def test_a_bounded_game_still_runs_on_its_deadline(self, rung_aware):
        # The deadline there is real, so the round number stays the clock.
        hist = [{"offer": {"price": 90, "from_player": "player_2", "round": i + 1}}
                for i in range(5)]
        early = play(negotiation_game(slot="player_1", my_value=80.0, round_=2,
                                      max_rounds=10, history=hist[:1]))["product_price"]
        late = play(negotiation_game(slot="player_1", my_value=80.0, round_=8,
                                     max_rounds=10, history=hist))["product_price"]
        assert late < early


class TestTheLadderFitsTheRoundsLeft:
    """A rung refused costs one round -- but only while another round exists.

    The clock alone can leave us priced at the top rung with the game about to
    end, which is how incomplete-information deal rates ended up at 0.28-0.39
    against a 0.377 ceiling. So the walk also has a floor set by rounds actually
    remaining: with `usable` rounds there is time for at most `usable` more
    rungs, and the rest are skipped.
    """

    def _ask(self, round_, max_rounds, my_value=80.0):
        hist = [{"offer": {"price": 10, "from_player": "player_2", "round": i + 1}}
                for i in range(round_)]
        return play(negotiation_game(
            slot="player_1", my_value=my_value, round_=round_, max_rounds=max_rounds,
            history=hist,
            last_offer={"price": 10, "from_player": "player_2", "round": round_},
        ))["product_price"]

    def test_a_short_game_starts_partway_down_the_ladder(self):
        # Four rounds and three rungs: opening at the top cannot be walked off
        # in time, so it opens lower.
        assert self._ask(1, 4) < self._ask(1, 10)

    def test_a_long_game_still_opens_at_the_top(self):
        assert self._ask(1, 10) == self._ask(2, 10)

    def test_the_cheapest_rung_is_reached_before_the_endgame(self):
        # Whatever the horizon, we are on the most signable rung with rounds to
        # spare rather than discovering it on the last one.
        for mr in (4, 6, 10):
            assert self._ask(mr - 1, mr) < self._ask(1, mr) or mr == 4
