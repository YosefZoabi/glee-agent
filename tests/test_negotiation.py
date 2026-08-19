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

    def test_single_round_seller_prices_to_be_accepted(self):
        action = play(negotiation_game(slot="player_1", my_value=80, round_=1, max_rounds=1))
        # The floor multiple, not the 1.9x opening anchor that lost the game.
        assert action["product_price"] < 80 * P.seller_open_multiple
        assert action["product_price"] == pytest.approx(80 * P.seller_floor_multiple)

    def test_single_round_buyer_prices_to_be_accepted(self):
        action = play(negotiation_game(slot="player_2", my_value=100, round_=1, max_rounds=1))
        assert action["product_price"] > 100 * P.buyer_open_multiple
        assert action["product_price"] == pytest.approx(100 * P.buyer_floor_multiple)

    def test_single_round_offer_is_still_profitable(self):
        seller = play(negotiation_game(slot="player_1", my_value=80, round_=1, max_rounds=1))
        assert seller["product_price"] > 80
        buyer = play(negotiation_game(slot="player_2", my_value=100, round_=1, max_rounds=1))
        assert buyer["product_price"] < 100

    def test_final_round_of_a_long_game_prices_the_same_way(self):
        # Not a special case for max_rounds == 1: any last word is a last word.
        action = play(negotiation_game(slot="player_1", my_value=80, round_=6, max_rounds=6))
        assert action["product_price"] == pytest.approx(80 * P.seller_floor_multiple)

    def test_a_real_horizon_still_opens_high(self):
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

    def test_off_by_default(self):
        assert P.rung_aware is False

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
