import pytest

from glee_agent.params import BARGAINING as P
from glee_agent.strategies.bargaining import play, proposer_share
from tests.fixtures import bargaining_game


class TestProposerShare:
    def test_last_round_proposer_takes_everything(self):
        # The responder's alternative to accepting is $0.
        assert proposer_share(0.9, 0.9, 1) == 1.0

    def test_rubinstein_fixed_point_when_unbounded(self):
        # (1 - d_opp) / (1 - d_me * d_opp) -- symmetric deltas give a near-even split.
        assert proposer_share(0.9, 0.9, None) == pytest.approx(0.1 / 0.19)

    def test_patience_is_worth_share(self):
        patient = proposer_share(0.99, 0.7, None)
        impatient = proposer_share(0.7, 0.99, None)
        assert patient > 0.9 > impatient

    def test_long_horizon_converges_on_the_fixed_point(self):
        assert proposer_share(0.9, 0.9, 200) == pytest.approx(proposer_share(0.9, 0.9, None))


class TestOffers:
    @pytest.mark.parametrize("money", [100, 1000, 37])
    @pytest.mark.parametrize("slot", ["player_1", "player_2"])
    def test_gains_sum_to_the_pot_exactly(self, money, slot):
        action = play(bargaining_game(money=money, slot=slot))
        assert action["alice_gain"] + action["bob_gain"] == money

    def test_our_own_side_gets_the_larger_share_early(self):
        as_alice = play(bargaining_game(slot="player_1", round_=1))
        assert as_alice["alice_gain"] > as_alice["bob_gain"]
        as_bob = play(bargaining_game(slot="player_2", round_=1))
        assert as_bob["bob_gain"] > as_bob["alice_gain"]

    def test_demand_falls_as_the_horizon_closes(self):
        early = play(bargaining_game(round_=1, max_rounds=8))["alice_gain"]
        late = play(bargaining_game(round_=6, max_rounds=8))["alice_gain"]
        assert late < early

    def test_final_offer_still_leaves_the_opponent_a_reason_to_sign(self):
        action = play(bargaining_game(round_=6, max_rounds=6, money=1000))
        assert action["bob_gain"] >= 1000 * (1 - P.final_round_demand) - 1

    def test_never_offers_the_opponent_nothing(self):
        action = play(bargaining_game(round_=1, max_rounds=6, money=1000))
        assert action["bob_gain"] > 0

    def test_message_omitted_when_the_game_forbids_them(self):
        assert "message" not in play(bargaining_game(messages_allowed=False))
        assert "message" in play(bargaining_game(messages_allowed=True))

    def test_unbounded_horizon_is_playable(self):
        action = play(bargaining_game(max_rounds=None, round_=3, money=500))
        assert action["alice_gain"] + action["bob_gain"] == 500


class TestDecisions:
    def _offer(self, alice, bob, money=1000, **kwargs):
        return bargaining_game(
            action_type="decision",
            money=money,
            last_offer={"player_1_gain": alice, "player_2_gain": bob, "proposer": "player_2", "round": 1},
            **kwargs,
        )

    def test_rejects_a_lowball_with_rounds_to_spare(self):
        assert play(self._offer(50, 950, round_=1, max_rounds=8))["decision"] == "reject"

    def test_accepts_a_strong_offer(self):
        assert play(self._offer(700, 300, round_=1, max_rounds=8))["decision"] == "accept"

    def test_accepts_anything_on_the_final_round(self):
        # Rejecting here pays $0, which is the bottom of the percentile scale.
        assert play(self._offer(1, 999, round_=6, max_rounds=6))["decision"] == "accept"

    def test_softens_but_does_not_capitulate_near_the_end(self):
        near_end = self._offer(120, 880, round_=5, max_rounds=6)
        assert play(near_end)["decision"] == "accept"
        assert play(self._offer(120, 880, round_=1, max_rounds=6))["decision"] == "reject"

    def test_reads_our_own_gain_when_playing_as_bob(self):
        game = self._offer(950, 50, round_=1, max_rounds=8, slot="player_2")
        assert play(game)["decision"] == "reject"
        game = self._offer(300, 700, round_=1, max_rounds=8, slot="player_2")
        assert play(game)["decision"] == "accept"

    def test_never_walks_away(self):
        # Walking away pays $0 -- it can only ever match the worst outcome.
        for round_ in range(1, 7):
            action = play(self._offer(400, 600, round_=round_, max_rounds=6))
            assert action["decision"] != "walkaway"
