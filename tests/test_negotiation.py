import pytest

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
