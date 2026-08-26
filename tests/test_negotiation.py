import pytest

from glee_agent.params import NEGOTIATION as P
from glee_agent.strategies.negotiation import play
from tests.fixtures import negotiation_game


class TestSeatsWithNoCounterparty:
    """The top rung as seller and the bottom rung as buyer cannot trade at all.

    Valuations sit on four rungs -- 80, 100, 120, 150 -- of one shared scale
    (checked over all 5,035 complete-information games on record: never once
    crossed). A seller trades only with a buyer above them, a buyer only with a
    seller below them. So these two seats have no counterparty that exists, and
    that follows from OUR value alone, which is why it survives incomplete
    information. 18.1% of our negotiation games, 85,705 turns, ~0 payoff.
    """

    SCALES = (1.0, 100.0, 10000.0)

    def _decide(self, *, slot, my_value, offer=90.0, **kw):
        return play(negotiation_game(
            action_type="decision", slot=slot, my_value=my_value, round_=2,
            last_offer={"price": offer, "from_player":
                        "player_2" if slot == "player_1" else "player_1"}, **kw))

    def test_a_seller_on_the_top_rung_walks(self):
        for scale in self.SCALES:
            action = self._decide(slot="player_1", my_value=150 * scale, offer=140 * scale)
            assert action["decision"] == "WalkAway", scale

    def test_a_buyer_on_the_bottom_rung_walks(self):
        for scale in self.SCALES:
            action = self._decide(slot="player_2", my_value=80 * scale, offer=90 * scale)
            assert action["decision"] == "WalkAway", scale

    def test_a_seller_anywhere_else_keeps_negotiating(self):
        # 80, 100 and 120 all have a rung above them, so a buyer who can pay
        # exists and the game is worth playing.
        for rung in (80, 100, 120):
            for scale in self.SCALES:
                action = self._decide(slot="player_1", my_value=rung * scale, offer=1.0)
                assert action["decision"] != "WalkAway", (rung, scale)

    def test_a_buyer_anywhere_else_keeps_negotiating(self):
        for rung in (100, 120, 150):
            for scale in self.SCALES:
                action = self._decide(slot="player_2", my_value=rung * scale,
                                      offer=1000000.0)
                assert action["decision"] != "WalkAway", (rung, scale)

    def test_a_value_off_the_pool_is_never_walked_on(self):
        # A value we cannot place is a pool we do not know. Guessing there would
        # forfeit a live game, so the schedule has to keep it.
        for odd in (37.0, 95.0, 151.0, 7.5):
            action = self._decide(slot="player_1", my_value=odd, offer=1.0)
            assert action["decision"] != "WalkAway", odd

    def test_complete_information_still_compares_the_two_values(self):
        # Both visible: no inference needed, and the rung rule must not override
        # a real zone. A seller on the top rung facing a buyer above it trades.
        action = self._decide(slot="player_1", my_value=120, opponent_value=150, offer=1.0)
        assert action["decision"] != "WalkAway"

    def test_the_parting_offer_is_priced_outside_the_pool(self):
        # WalkAway is only offered on a decision turn, so when the proposal is
        # ours we still name a number. A serious one is wasted -- no price in
        # the pool pays us -- so name one only a careless opponent signs.
        seller = play(negotiation_game(slot="player_1", my_value=150, round_=1))
        assert seller["product_price"] == round(150 * P.untradable_lottery_multiple, 2)
        buyer = play(negotiation_game(slot="player_2", my_value=80, round_=1))
        assert buyer["product_price"] == round(80 / P.untradable_lottery_multiple, 2)

    def test_the_parting_offer_still_points_the_right_way(self):
        # Absurd, but not backwards: a seller must still ask ABOVE their value
        # and a buyer bid BELOW theirs, or a careless opponent signing it costs
        # us money instead of winning a lottery.
        assert play(negotiation_game(slot="player_1", my_value=150))["product_price"] > 150
        assert play(negotiation_game(slot="player_2", my_value=80))["product_price"] < 80

    def test_a_tradable_seat_still_gets_the_real_schedule(self):
        # The lottery must not leak into games we can win.
        priced = play(negotiation_game(slot="player_1", my_value=120))["product_price"]
        assert priced < 120 * P.untradable_lottery_multiple


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
        # A one-round game is an ultimatum, so this is priced as one: refusing
        # pays them zero and 216 of 216 last-word offers we have made were
        # signed. It used to run to the midpoint (70.0), then to `surplus_target`
        # (79.0); both handed back most of a zone they could not refuse.
        assert action["product_price"] == pytest.approx(100 - P.rung_last_word_shade * 60)
        assert 40 < action["product_price"] < 100      # still leaves them a crumb


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

    def test_recognises_them_but_does_not_pay_yet(self):
        # The branch arms here -- eight identical offers, 15,000 of profit -- but
        # run37 showed paying now is never better than paying at the cap, so the
        # rescue is deferred rather than cancelled. See `stonewall_needs_endgame`.
        assert play(self._game(815_000, 8))["decision"] == "RejectOffer"

    def test_and_still_rescues_the_game_before_the_cap(self):
        # 85bd702f itself: the 0-0 this class exists to prevent. Signing 815,000
        # at round 98 banks the same 15,000 that signing at round 9 would have,
        # because negotiation has no discount term.
        assert play(self._game(815_000, 97))["decision"] == "AcceptOffer"

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

    def _final_price(self, *, role, my_value, opponent_value, round_=3, max_rounds=10):
        slot = "player_1" if role == "seller" else "player_2"
        return play(negotiation_game(
            slot=slot, my_value=my_value, opponent_value=opponent_value,
            round_=round_, max_rounds=max_rounds,
        ))["product_price"]

    def _ultimatum(self, *, role, my_value, opponent_value):
        return self._final_price(role=role, my_value=my_value,
                                 opponent_value=opponent_value, round_=1, max_rounds=1)

    def test_the_seller_lands_above_the_midpoint(self):
        price = self._final_price(role="seller", my_value=40, opponent_value=100)
        assert price > 70.0

    def test_an_ultimatum_asks_for_the_whole_zone(self):
        # A one-round game is an ultimatum: rejecting pays them zero, and 216 of
        # 216 last-word offers we have made were signed. The schedule used to run
        # from aggressive toward `surplus_target` as time passed, so it handed
        # over its MOST generous price on the round they could not refuse.
        price = self._ultimatum(role="seller", my_value=40, opponent_value=100)
        assert price == pytest.approx(100 - P.rung_last_word_shade * 60)
        buyer = self._ultimatum(role="buyer", my_value=100, opponent_value=40)
        assert buyer == pytest.approx(40 + P.rung_last_word_shade * 60)

    def test_the_buyer_lands_below_the_midpoint(self):
        # Symmetric: `span` is negative for a buyer, so the same share moves the
        # price the other way. Getting this backwards would concede MORE.
        price = self._final_price(role="buyer", my_value=100, opponent_value=40)
        assert price < 70.0

    def test_both_roles_capture_the_same_share_of_surplus(self):
        seller = self._final_price(role="seller", my_value=40, opponent_value=100) - 40
        buyer = 100 - self._final_price(role="buyer", my_value=100, opponent_value=40)
        assert seller == pytest.approx(buyer)
        assert seller / 60 > 0.5           # above the midpoint, both seats alike

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


class TestNotBlinking:
    """Both flags ship OFF; the arm turns them on. Guards the default too."""

    def _arm(self, monkeypatch, **kw):
        import dataclasses
        from glee_agent import params
        from glee_agent.strategies import negotiation
        monkeypatch.setattr(negotiation, "P",
                            dataclasses.replace(params.NEGOTIATION, **kw))

    def _stonewalled(self, my_value=100.0, their=None, round_=8, max_rounds=10):
        # They have repeated the same price for six offers running.
        hist = [{"offer": {"price": 110.0, "from_player": "player_2", "round": r}}
                for r in range(1, 8)]
        return negotiation_game(
            action_type="decision", slot="player_1", my_value=my_value,
            opponent_value=their, round_=round_, max_rounds=max_rounds, history=hist,
            last_offer={"price": 110.0, "from_player": "player_2", "round": 7})

    def test_both_flags_ship_off(self):
        from glee_agent import params
        assert params.NEGOTIATION.stonewall_respects_ultimatum is False
        assert params.NEGOTIATION.known_zone_floor == 0.0

    def test_by_default_we_no_longer_fold_to_a_stonewaller(self):
        # Round 8 of 10 leaves three rounds, so refusing is still free.
        assert play(self._stonewalled())["decision"] == "RejectOffer"

    def test_but_we_do_fold_once_the_clock_is_real(self):
        assert play(self._stonewalled(round_=9))["decision"] == "AcceptOffer"

    # The three below test OTHER flags, so they pin `stonewall_needs_endgame`
    # back off: with it on, the endgame gate decides these games before the flag
    # under test gets a say, and the test would pass for the wrong reason.

    def test_the_arm_holds_the_ultimatum_instead(self, monkeypatch):
        # Two rounds left of ten with them proposing: the last word is ours, and
        # 216 of 216 last-word offers we have made were accepted.
        self._arm(monkeypatch, stonewall_respects_ultimatum=True,
                  stonewall_needs_endgame=False)
        assert play(self._stonewalled(round_=9))["decision"] != "AcceptOffer"

    def test_the_arm_still_folds_when_the_last_word_is_theirs(self, monkeypatch):
        self._arm(monkeypatch, stonewall_respects_ultimatum=True,
                  stonewall_needs_endgame=False)
        game = self._stonewalled(round_=8, max_rounds=10)
        assert play(game)["decision"] == "AcceptOffer"

    def test_the_known_zone_floor_refuses_a_thin_slice(self, monkeypatch):
        # Selling at 100 to a buyer worth 200: a price of 110 is a tenth of the
        # surplus, which is the cell we currently sign at 0.3132.
        self._arm(monkeypatch, known_zone_floor=0.45, stonewall_needs_endgame=False)
        game = self._stonewalled(my_value=100.0, their=200.0, round_=4, max_rounds=10)
        assert play(game)["decision"] == "RejectOffer"

    def test_the_known_zone_floor_still_takes_a_fair_split(self, monkeypatch):
        self._arm(monkeypatch, known_zone_floor=0.45, stonewall_needs_endgame=False)
        hist = [{"offer": {"price": 160.0, "from_player": "player_2", "round": r}}
                for r in range(1, 8)]
        game = negotiation_game(
            action_type="decision", slot="player_1", my_value=100.0,
            opponent_value=200.0, round_=4, max_rounds=10, history=hist,
            last_offer={"price": 160.0, "from_player": "player_2", "round": 3})
        assert play(game)["decision"] == "AcceptOffer"


class TestAStonewallerIsNotEvidenceUntilTheClockIsReal:
    """Regression: a buyer repeated 81.20 six times and we signed for 1.20.

    Seller valuing the item at 80, open horizon, buyer offers 81.20 on every one
    of their turns. On the sixth, `opponent_has_stopped_moving` arms and accepts
    -- overriding our own bar, which stood at a profit of 15.30 against a target
    of 97. Round 12 of a game that does not end until 99.

    The branch can only ever arm in an open game: a bounded negotiation runs at
    most 10 rounds, so the opponent never lands `stonewall_offers` offers. Over
    the record it armed on a profitable price in 243 of 2234 open games and zero
    bounded ones, taking 0.0718 of our valuation where the schedule asked 0.2064.

    run37 refused them instead, and caving lost or tied every time: 12 games
    better, 11 identical, 0 worse, 23 of 23 still closing (sign test p =
    0.00049). So `stonewall_needs_endgame` now ships ON and these tests pin
    refusal as the default; `stonewall_caves` restores the old behaviour.
    """

    def _game(self, *, round_, their_price=81.2, my_value=80.0, max_rounds=None):
        history = []
        asks = [118.4, 117.16, 114.68, 112.2, 109.72, 107.24]
        for k in range((round_ - 1) // 2):
            r = k * 2 + 1
            history.append({"round": r, "decision": "RejectOffer",
                            "offer": {"price": asks[k % len(asks)],
                                      "from_player": "player_1", "round": r}})
            history.append({"round": r + 1, "decision": "RejectOffer",
                            "offer": {"price": their_price,
                                      "from_player": "player_2", "round": r + 1}})
        state = {
            "round": round_, "max_rounds": max_rounds,
            "horizon_known": max_rounds is not None,
            "complete_information": False, "history": history,
            "last_offer": {"price": their_price, "from_player": "player_2", "round": round_},
            "player_1_role": "seller", "player_2_role": "buyer",
            "messages_allowed": False, "current_player": "player_1",
            "player_1_value": my_value,
        }
        return {"game_state": state, "your_player": "player_1", "game_family": "negotiation"}

    def test_the_shipped_default_keeps_refusing_mid_game(self):
        # Guards the SHIPPED behaviour, which run37 flipped.
        assert play(self._game(round_=12))["decision"] == "RejectOffer"

    def test_it_held_out_up_to_that_point(self):
        for round_ in (2, 4, 6, 8, 10):
            assert play(self._game(round_=round_))["decision"] == "RejectOffer", round_

    def test_it_still_refuses_much_later(self):
        # Round 40 of 99: refusing is still free, so there is still nothing to buy
        # by caving.
        assert play(self._game(round_=40))["decision"] == "RejectOffer"

    def test_but_takes_it_when_the_cap_is_in_sight(self):
        # At the real end of an open game, 1.20 beats the $0 a cap pays. This is
        # the half of run37 that cost nothing: eleven games signed the same price
        # here that caving would have signed 85 rounds earlier.
        assert play(self._game(round_=98))["decision"] == "AcceptOffer"

    def test_a_bounded_endgame_still_signs(self):
        # Rounds genuinely scarce -- the branch behaves as it always did.
        assert play(self._game(round_=10, max_rounds=10))["decision"] == "AcceptOffer"

    def test_the_old_behaviour_caved_on_the_sixth_repeat(self, stonewall_caves):
        assert play(self._game(round_=12))["decision"] == "AcceptOffer"



class TestAnAskThatCannotCloseShouldNotTalk:
    """Regression: seller at 800,000 asked 970,000 on round 9 of 10.

    No seller standing on the 1,000,000 rung would ever ask 970,000, so that
    price named us exactly. The buyer held the last word, answered 824,000, and
    we banked 24,000 against their 176,000.

    The leak is real; the fix is off. It was justified by "that ask is never
    signed anyway -- 0 times in 715 bounded games", which counted only games
    that reached the final round and so dropped every game the ask had closed a
    round earlier. Scored on `agreed_round`, the ask closes 10.2% of the time
    (29 of 283) and the flag cuts that to 4.2%, banking less than all four
    controls. These tests therefore guard the SHIPPED behaviour (leak and all)
    and pin the flag's mechanism for whenever a real motive for it turns up.
    """

    def _ask(self, *, round_, max_rounds, my_value=800000.0, slot="player_1"):
        state = {
            "round": round_, "max_rounds": max_rounds, "horizon_known": True,
            "complete_information": False, "history": [], "last_offer": None,
            "player_1_role": "seller", "player_2_role": "buyer",
            "messages_allowed": False, "current_player": slot,
        }
        state[f"{slot}_value"] = my_value
        return play({"game_state": state, "your_player": slot,
                     "game_family": "negotiation",
                     "valid_actions": {"type": "offer"}})["product_price"]

    def test_the_shipped_default_names_the_rung(self):
        # Guards the SHIPPED behaviour: 970,000 is under the 1,000,000 rung.
        assert self._ask(round_=9, max_rounds=10) < 1_000_000

    def test_the_arm_holds_at_the_rung_above(self, hide_rung):
        assert self._ask(round_=9, max_rounds=10) >= 1_000_000

    def test_it_only_applies_when_the_last_price_is_theirs(self, hide_rung):
        # Round 8 of 10: the last price is ours, so revealing costs nothing --
        # we set the final number and they take it or take zero.
        from glee_agent.strategies.negotiation import final_offer_is_theirs
        state = {"round": 8, "max_rounds": 10, "horizon_known": True}
        assert final_offer_is_theirs(state, "player_1") is False
        state["round"] = 9
        assert final_offer_is_theirs(state, "player_1") is True

    def test_the_buyer_side_reads_the_other_direction(self, hide_rung):
        # A buyer on the 150 rung must not bid ABOVE the 120 rung beneath it.
        assert self._ask(round_=9, max_rounds=10, my_value=150.0, slot="player_2") <= 120.0

    def test_an_open_horizon_is_untouched(self, hide_rung):
        # No horizon means no last price to hold, so nothing to hide from.
        state = {
            "round": 9, "max_rounds": None, "horizon_known": False,
            "complete_information": False, "history": [], "last_offer": None,
            "player_1_role": "seller", "player_2_role": "buyer",
            "messages_allowed": False, "current_player": "player_1",
            "player_1_value": 800000.0,
        }
        price = play({"game_state": state, "your_player": "player_1",
                      "game_family": "negotiation",
                      "valid_actions": {"type": "offer"}})["product_price"]
        assert price < 1_000_000

    def test_the_final_round_is_untouched(self, hide_rung):
        """On the last round the price is ours and the arm must not move it.

        Asserted against the unflagged price rather than a literal: the last
        word takes the best-expected-value rung rather than walking the ladder,
        so the number there is not the floor and hard-coding one would test the
        schedule instead of this arm.
        """
        import dataclasses
        from glee_agent import params
        from glee_agent.strategies import negotiation
        flagged = self._ask(round_=10, max_rounds=10)
        negotiation.P = dataclasses.replace(params.NEGOTIATION,
                                            hide_rung_from_last_word=False)
        try:
            plain = self._ask(round_=10, max_rounds=10)
        finally:
            negotiation.P = dataclasses.replace(params.NEGOTIATION,
                                                hide_rung_from_last_word=True)
        assert flagged == pytest.approx(plain)


class TestTheUltimatumLadder:
    """A one-shot price should sit at the top of its own acceptance band.

    The responder's valuation is one of RUNG_SHAPE x scale and they cannot trade
    past it, so acceptance is a step on four points. Measured over 2,958 of our
    own incomplete-information seller ultimatums: the deal rate is flat inside a
    band (52.7% at 1.05-1.15 x M against 51.7% at 1.15-1.20) and falls to 0.0%
    the moment the ask crosses 1.50. 74% of our asks sat strictly inside a band.
    """

    def _one_shot(self, **kw):
        kw.setdefault("action_type", "offer")
        kw.setdefault("slot", "player_1")
        kw.setdefault("max_rounds", 1)
        kw.setdefault("round_", 1)
        return negotiation_game(**kw)

    def test_the_flag_ships_off(self):
        from glee_agent import params
        assert params.NEGOTIATION.ultimatum_ladder is False
        assert params.NEGOTIATION.ultimatum_ladder_epsilon == 0.001

    def _plain(self, **kw):
        """The price the schedule sends with the ladder OFF.

        The fixture patches the module-level params, so this has to put them
        back for the call or "base" is the laddered price itself.
        """
        import dataclasses
        from glee_agent import params
        from glee_agent.strategies import negotiation
        kw.setdefault("action_type", "offer")
        kw.setdefault("slot", "player_1")
        kw.setdefault("max_rounds", 1)
        kw.setdefault("round_", 1)
        saved = negotiation.P
        negotiation.P = dataclasses.replace(params.NEGOTIATION, ultimatum_ladder=False)
        try:
            return play(negotiation_game(**kw))["product_price"]
        finally:
            negotiation.P = saved

    def _rungs(self, value):
        from glee_agent.strategies.negotiation import RUNG_SHAPE, pool_position
        index, scale = pool_position(value)
        return [r * scale for r in RUNG_SHAPE]

    def test_it_moves_the_ask_up_to_the_top_of_its_own_band(self, ultimatum_ladder):
        # The band is decided by the schedule; the ladder only takes the rest of
        # it. It never reaches for a HIGHER band, because that would trade away
        # acceptance and stop being free.
        for value in (80.0, 100.0, 120.0, 10000.0):
            base = self._plain(my_value=value)
            armed = play(self._one_shot(my_value=value))["product_price"]
            rungs = self._rungs(value)
            above = [r for r in rungs if r > base + 1e-9]
            if not above:
                continue
            assert armed > base, (value, base, armed)
            assert armed < min(above), (value, base, armed, min(above))
            assert min(above) - armed < min(above) * 0.01, (value, armed)

    def test_the_acceptance_set_is_unchanged(self, ultimatum_ladder):
        # The whole safety argument: the set of responder types that sign the
        # laddered price is identical to the set that signed the original.
        for value in (80.0, 100.0, 120.0, 8000.0, 1000000.0):
            base = self._plain(my_value=value)
            armed = play(self._one_shot(my_value=value))["product_price"]
            rungs = self._rungs(value)
            assert {r for r in rungs if r >= base} == {r for r in rungs if r >= armed}, value

    def test_the_laddered_price_stays_strictly_under_its_rung(self, ultimatum_ladder):
        # The cliff is sharp: measured, an ask a fraction ABOVE the rung is
        # signed by nobody at all (0.0% over 557 games at 1.50-1.60 x M).
        for value in (80.0, 100.0, 120.0, 10000.0, 1000000.0):
            armed = play(self._one_shot(my_value=value))["product_price"]
            assert armed not in self._rungs(value), (value, armed)

    def test_it_never_prices_at_or_under_our_own_value(self, ultimatum_ladder):
        for value in (80.0, 100.0, 120.0, 150.0, 8000.0, 1000000.0):
            out = play(self._one_shot(my_value=value))
            assert out["product_price"] > value, (value, out["product_price"])

    def test_it_leaves_multi_round_games_alone(self, ultimatum_ladder):
        # The whole safety argument is one-shot: a responder who can counter is
        # not choosing between our price and zero.
        for rounds in (2, 6, 10, None):
            armed = play(self._one_shot(my_value=100.0, max_rounds=rounds))
            plain = self._plain(my_value=100.0, max_rounds=rounds)
            assert armed["product_price"] == plain, rounds

    def test_the_top_rung_seller_is_left_to_the_walk_away_rule(self, ultimatum_ladder):
        # No rung above 150 to ladder to; `untradable_walk_away` owns that seat.
        out = play(self._one_shot(my_value=150.0))
        assert out["product_price"] > 150.0

    def test_an_off_pool_valuation_is_left_alone(self, ultimatum_ladder):
        armed = play(self._one_shot(my_value=137.0))
        plain = self._plain(my_value=137.0)
        assert armed["product_price"] == plain
