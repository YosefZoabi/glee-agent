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
        # No rounds left to shade toward: take the midpoint, which they will sign.
        assert action["product_price"] == pytest.approx(70.0)


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
