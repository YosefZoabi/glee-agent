"""The guarantee that matters most: we always submit something legal.

Five invalid moves or one missed turn clock ends the game as a no-deal, scored
at the bottom of the percentile scale -- so a bug in a strategy must cost us a
mediocre move, never a forfeited game.
"""

import pytest

from glee_agent import dispatcher
from glee_agent.safety import MAX_MESSAGE_CHARS, fallback, sanitize
from tests.fixtures import bargaining_game, negotiation_game, persuasion_game


class TestFallback:
    def test_bargaining_offer_sums_to_the_pot(self):
        action = fallback(bargaining_game(money=1000))
        assert action["alice_gain"] + action["bob_gain"] == 1000

    def test_bargaining_decision_closes_rather_than_stalls(self):
        assert fallback(bargaining_game(action_type="decision"))["decision"] == "accept"

    def test_negotiation_offer_is_priced(self):
        assert fallback(negotiation_game())["product_price"] == 40

    def test_seller_message_is_non_empty(self):
        game = persuasion_game(action_type="seller_message", slot="player_1", quality="low")
        assert fallback(game)["message"].strip()

    def test_buyer_falls_back_to_the_prior(self):
        assert fallback(persuasion_game(p=0.9, v=100, u=0, price=60))["decision"] == "yes"
        assert fallback(persuasion_game(p=0.1, v=100, u=0, price=60))["decision"] == "no"

    def test_handles_a_game_it_understands_nothing_about(self):
        assert isinstance(fallback({"game_family": "???", "valid_actions": {}}), dict)


class TestSanitize:
    def test_repairs_gains_that_miss_the_pot(self):
        game = bargaining_game(money=1000)
        action = sanitize(game, {"alice_gain": 600, "bob_gain": 300})
        assert action["alice_gain"] + action["bob_gain"] == 1000
        assert action["alice_gain"] == 600      # our own claim is what we meant

    def test_fills_in_a_missing_counterpart_gain(self):
        action = sanitize(bargaining_game(money=1000), {"alice_gain": 700})
        assert action["bob_gain"] == 300

    def test_truncates_an_over_long_message(self):
        action = sanitize(bargaining_game(), {"alice_gain": 500, "bob_gain": 500, "message": "x" * 5000})
        assert len(action["message"]) < MAX_MESSAGE_CHARS

    def test_drops_a_message_the_game_does_not_allow(self):
        game = bargaining_game(messages_allowed=False)
        assert "message" not in sanitize(game, {"alice_gain": 500, "bob_gain": 500, "message": "hi"})

    def test_keeps_the_seller_message_persuasion_requires(self):
        game = persuasion_game(action_type="seller_message", slot="player_1", quality="high")
        assert sanitize(game, {"message": "Worth it."})["message"] == "Worth it."

    def test_replaces_an_empty_seller_message(self):
        game = persuasion_game(action_type="seller_message", slot="player_1", quality="high")
        assert sanitize(game, {"message": "   "})["message"].strip()

    def test_corrects_a_decision_outside_the_allowed_set(self):
        game = negotiation_game(action_type="decision")
        game["valid_actions"]["fields"] = {"decision": ["AcceptOffer", "RejectOffer", "WalkAway"]}
        assert sanitize(game, {"decision": "accept"})["decision"] in {
            "AcceptOffer", "RejectOffer", "WalkAway"
        }

    def test_rounds_a_price_to_cents(self):
        action = sanitize(negotiation_game(), {"product_price": 41.239999})
        assert action["product_price"] == 41.24

    def test_replaces_a_non_dict_action(self):
        assert isinstance(sanitize(bargaining_game(), None), dict)


class TestDispatcher:
    @pytest.mark.parametrize(
        "game",
        [
            bargaining_game(),
            bargaining_game(action_type="decision", last_offer={"player_1_gain": 400, "player_2_gain": 600}),
            negotiation_game(),
            negotiation_game(action_type="decision", last_offer={"price": 50, "from_player": "player_2"}),
            persuasion_game(),
            persuasion_game(action_type="seller_message", slot="player_1", quality="high"),
            persuasion_game(action_type="seller_recommendation", slot="player_1", quality="low"),
        ],
    )
    def test_every_turn_produces_an_action(self, game):
        action = dispatcher.play(game)
        assert isinstance(action, dict) and action

    def test_a_raising_strategy_does_not_forfeit_the_game(self, monkeypatch):
        def explode(game):
            raise RuntimeError("bug in a strategy")

        monkeypatch.setitem(dispatcher.STRATEGIES, "bargaining", explode)
        action = dispatcher.play(bargaining_game(money=1000))
        assert action["alice_gain"] + action["bob_gain"] == 1000

    def test_an_unknown_family_does_not_forfeit_the_game(self):
        game = bargaining_game()
        game["game_family"] = "some_new_family"
        assert isinstance(dispatcher.play(game), dict)
