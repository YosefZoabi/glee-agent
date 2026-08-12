import pytest

from glee_agent.strategies.persuasion import _seller_recommends, lie_budget, play
from tests.fixtures import persuasion_game, persuasion_round


class TestLieBudget:
    def test_matches_the_closed_form(self):
        # p=0.5, price=60, v=100, u=0 -> threshold 0.6, budget p(1-t)/(t(1-p)) = 2/3.
        assert lie_budget(0.5, 60, 100, 0) == pytest.approx(2 / 3)

    def test_unrestricted_when_the_prior_alone_justifies_buying(self):
        # The buyer buys on the prior, so no recommendation can cost us anything.
        assert lie_budget(0.8, 60, 100, 0) == 1.0

    def test_shrinks_as_the_price_approaches_the_high_value(self):
        assert lie_budget(0.5, 90, 100, 0) < lie_budget(0.5, 60, 100, 0)

    def test_zero_when_only_certainty_would_do(self):
        assert lie_budget(0.05, 99, 100, 0) == pytest.approx(0.0, abs=0.01)


class TestSeller:
    def _low(self, **kwargs):
        return persuasion_game(
            action_type="seller_recommendation", slot="player_1", quality="low", **kwargs
        )

    def test_never_talks_down_a_high_quality_product(self):
        for round_ in range(1, 11):
            game = persuasion_game(
                action_type="seller_recommendation", slot="player_1", quality="high", round_=round_
            )
            assert play(game)["decision"] == "yes"

    def test_recommends_everything_on_the_final_round(self):
        # No reputation left to protect, and the buyer has no way to retaliate.
        assert play(self._low(round_=10, total_rounds=10))["decision"] == "yes"

    def test_lies_are_rationed_early(self):
        # Deterministic per game, so the rate is measured across games.
        rate = self._lie_rate(round_=1)
        assert 0.0 < rate < 0.35

    def test_lies_more_freely_as_rounds_run_out(self):
        assert self._lie_rate(round_=8) > self._lie_rate(round_=1)

    def test_stays_under_the_budget_the_buyer_would_tolerate(self):
        assert self._lie_rate(round_=9) <= lie_budget(0.5, 60, 100, 0)

    def test_is_deterministic_for_a_given_game_and_round(self):
        game = self._low(round_=4)
        assert _seller_recommends(game) == _seller_recommends(game)

    def _lie_rate(self, *, round_, trials=400):
        recommended = 0
        for index in range(trials):
            game = self._low(round_=round_, total_rounds=10)
            game["game_id"] = f"game-{index}"
            recommended += _seller_recommends(game)
        return recommended / trials


class TestBuyer:
    def test_buys_when_the_prior_alone_clears_the_price(self):
        game = persuasion_game(p=0.7, v=100, u=0, price=60, round_=5, seller_message="yes")
        assert play(game)["decision"] == "yes"

    def test_passes_when_it_does_not(self):
        game = persuasion_game(p=0.3, v=100, u=0, price=60, round_=5, seller_message="yes")
        assert play(game)["decision"] == "no"

    def test_stops_buying_from_a_proven_liar(self):
        history = [persuasion_round(round_=r, message="yes", bought=True, quality="low") for r in range(1, 5)]
        game = persuasion_game(p=0.7, v=100, u=0, price=60, round_=5, seller_message="yes", history=history)
        assert play(game)["decision"] == "no"

    def test_keeps_buying_from_an_honest_seller(self):
        history = [persuasion_round(round_=r, message="yes", bought=True, quality="high") for r in range(1, 5)]
        game = persuasion_game(p=0.4, v=100, u=0, price=60, round_=5, seller_message="yes", history=history)
        assert play(game)["decision"] == "yes"

    def test_ignores_rounds_it_passed_on(self):
        # Quality is hidden unless we bought, so a pass carries no evidence.
        passed = [persuasion_round(round_=r, message="yes", bought=False) for r in range(1, 9)]
        with_passes = persuasion_game(p=0.7, price=60, round_=9, seller_message="yes", history=passed)
        clean = persuasion_game(p=0.7, price=60, round_=9, seller_message="yes")
        assert play(with_passes) == play(clean)

    def test_trusts_a_negative_recommendation(self):
        # Talking us out of a sale costs the seller their own revenue.
        game = persuasion_game(p=0.9, v=100, u=0, price=60, round_=5, seller_message="no")
        assert play(game)["decision"] == "no"

    def test_reads_a_negative_text_message(self):
        game = persuasion_game(
            p=0.9, v=100, u=0, price=60, round_=5,
            seller_message="Straight answer: this one is not worth the price.",
        )
        assert play(game)["decision"] == "no"

    def test_treats_an_ordinary_pitch_as_positive(self):
        game = persuasion_game(
            p=0.7, v=100, u=0, price=60, round_=5,
            seller_message="I have looked this one over and I am happy to put my name on it.",
        )
        assert play(game)["decision"] == "yes"

    def test_pays_a_little_for_information_in_the_first_rounds(self):
        # Buying is the only way to observe quality, and that read prices the
        # rest of the game -- so a marginal expected value is worth taking early.
        marginal = dict(p=0.55, v=100, u=0, price=60, seller_message="yes")
        assert play(persuasion_game(round_=1, **marginal))["decision"] == "yes"
        assert play(persuasion_game(round_=6, **marginal))["decision"] == "no"
