import pytest

from glee_agent.params import PERSUASION as P
from glee_agent.strategies.persuasion import (
    signal_posterior,
    _seller_recommends,
    buyer_ignores_us,
    buyer_threshold,
    estimate_threshold,
    lie_budget,
    play,
    regime,
)
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

    def test_will_not_lie_before_it_has_credibility_to_spend(self):
        # With no purchases behind us the buyer has no evidence, so a lie caught
        # on the first sale drops them under the bar with the whole game left to
        # lose. Reputation has to be earned before it can be spent.
        assert self._lie_rate(round_=1) == 0.0

    def test_lies_more_freely_as_rounds_run_out(self):
        # Same earned record either way; only what the remaining rounds are
        # worth differs. The margin decays with the horizon, so the endgame
        # aggression falls out of the reputation cost rather than a fixed ramp.
        earned = [persuasion_round(round_=r, message="yes", bought=True, quality="high")
                  for r in range(1, 4)]
        early = self._lie_rate(round_=2, history=earned)
        late = self._lie_rate(round_=9, history=earned)
        assert late > early

    def test_stays_under_the_budget_the_buyer_would_tolerate(self):
        assert self._lie_rate(round_=9) <= lie_budget(0.5, 60, 100, 0)

    def test_is_deterministic_for_a_given_game_and_round(self):
        game = self._low(round_=4)
        assert _seller_recommends(game) == _seller_recommends(game)

    def _lie_rate(self, *, round_, trials=400, history=None):
        recommended = 0
        for index in range(trials):
            game = self._low(round_=round_, total_rounds=10, history=history or [])
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
        # p*v = 50 against a price of 60, so the prior does NOT clear the price
        # and the belief is what decides. (At p=0.7 the prior alone pays +10 a
        # round and buying stays correct however much the seller lies -- see
        # TestBuyerPriorFloor.)
        history = [persuasion_round(round_=r, message="yes", bought=True, quality="low") for r in range(1, 5)]
        game = persuasion_game(p=0.5, v=100, u=0, price=60, round_=5, seller_message="yes", history=history)
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


class TestBuyerPriorFloor:
    """Regression: game 4ec7b241 -- bought twice, drew low twice, quit at -2,000,000.

    p=1/3, v=4,000,000, price=1,000,000: the prior alone pays +333,333 a round,
    so buying every round is +EV no matter what the seller does. The posterior
    only updates on rounds we BUY, so two unlucky exploration draws pushed the
    belief under the bar, which stopped us buying, which froze the belief there.
    An absorbing state with a guaranteed-profitable alternative sitting next to it.
    """

    def _game(self, *, p, v, price, history=None, seller_message=None, round_=5):
        return persuasion_game(
            action_type="buyer_decision", slot="player_2",
            p=p, v=v, u=0.0, price=price, round_=round_, total_rounds=20,
            seller_message=seller_message, history=history or [],
        )

    def _two_bad_explorations(self):
        return [
            persuasion_round(round_=1, message="yes", bought=True, quality="low"),
            persuasion_round(round_=2, message="yes", bought=True, quality="low"),
        ]

    def test_keeps_buying_when_the_prior_alone_beats_the_price(self):
        # The exact configuration that lost 2,000,000.
        game = self._game(p=1 / 3, v=4_000_000, price=1_000_000,
                          history=self._two_bad_explorations())
        assert play(game)["decision"] == "yes"

    def test_a_seller_who_recommends_everything_conveys_nothing(self):
        # The real shape of both losses: "yes" on all twenty rounds. A constant
        # signal leaves P(high | recommended) exactly at the prior, so the floor
        # is not a heuristic here -- it is the correct posterior.
        game = self._game(p=1 / 3, v=4_000_000, price=1_000_000, seller_message="yes",
                          history=self._two_bad_explorations())
        assert play(game)["decision"] == "yes"

    def test_an_explicit_warning_still_outranks_the_prior_floor(self):
        # The observed loss came from a SILENT seller, so the floor deliberately
        # sits below the negative signal rather than overriding it. Trusting an
        # unverifiable "no" is a separate question -- quality is hidden on rounds
        # we pass, so a negative can never be checked against an outcome.
        game = self._game(p=1 / 3, v=4_000_000, price=1_000_000,
                          seller_message="this one is not worth the price")
        assert play(game)["decision"] == "no"

    def test_the_floor_applies_when_the_seller_says_nothing(self):
        # A genuinely silent seller cannot steer us either.
        game = self._game(p=1 / 3, v=4_000_000, price=1_000_000, seller_message=None,
                          history=self._two_bad_explorations())
        assert play(game)["decision"] == "yes"

    def test_bad_luck_does_not_become_permanent(self):
        # The absorbing state: every round after the unlucky pair must still buy.
        history = self._two_bad_explorations()
        for round_ in range(3, 21):
            game = self._game(p=1 / 3, v=4_000_000, price=1_000_000,
                              history=history, round_=round_)
            assert play(game)["decision"] == "yes", f"stopped buying at round {round_}"

    def test_an_unprofitable_prior_still_respects_the_seller(self):
        # p*v = 400,000 against a price of 1,000,000: blind buying loses here, so
        # the floor must NOT fire and the negative signal must still be honoured.
        game = self._game(p=1 / 3, v=1_200_000, price=1_000_000,
                          seller_message="this one is not worth the price")
        assert play(game)["decision"] == "no"

    def test_the_floor_is_strict_not_generous(self):
        # Exactly break-even is not profitable; the floor must not fire.
        game = self._game(p=0.5, v=200.0, price=100.0,
                          seller_message="this one is not worth the price")
        assert play(game)["decision"] == "no"


class TestSellerBudgetIsAQuota:
    """Regression: game 2e48f9f7 -- recommended 20 of 20, sold 0, banked nothing.

    p=0.80, v=1,250,000, price=1,000,000. The buyer's bar is P(high|rec) >= 0.80,
    which is exactly the prior, so the lying budget is 1.0 and every point of
    overshoot puts them at indifference. A per-round probability only holds on
    average and there are about four low rounds to average over, so a 0.75 rate
    lands on 4/4 often enough to matter. Rationing against the lows actually seen
    keeps the realised rate near the intended one.
    """

    def _play_game(self, seed, *, p=0.8, rounds=20):
        import random
        rng = random.Random(seed)
        history, lows, lies = [], 0, 0
        for round_ in range(1, rounds + 1):
            quality = "low" if rng.random() > p else "high"
            game = persuasion_game(
                action_type="seller_recommendation", slot="player_1", quality=quality,
                p=p, v=1_250_000, u=0.0, price=1_000_000,
                round_=round_, total_rounds=rounds, history=history,
            )
            game["game_id"] = f"quota-{seed}"
            recommends = _seller_recommends(game)
            if quality == "low":
                lows += 1
                lies += recommends
            history.append(persuasion_round(
                round_=round_, message="yes" if recommends else "no",
                bought=True, quality=quality,
            ))
        return lies / lows if lows else 0.0

    def test_the_realised_rate_stays_under_the_budget(self):
        rates = [self._play_game(s) for s in range(120)]
        mean = sum(rates) / len(rates)
        assert mean <= lie_budget(0.8, 1_000_000, 1_250_000, 0) * P.lie_budget_use

    def test_the_buyer_still_strictly_profits_at_our_rate(self):
        # The whole point: at the realised rate the recommendation must leave
        # them better off buying than not. Indifference is a refusal.
        rates = [self._play_game(s) for s in range(120)]
        mean = sum(rates) / len(rates)
        posterior = 0.8 / (0.8 + mean * 0.2)
        assert posterior > 1_000_000 / 1_250_000

    def test_the_buyer_is_never_left_under_the_bar_mid_game(self):
        """The real invariant, replacing a proxy that has stopped tracking it.

        This used to assert that few games recommend EVERY low round. That was a
        good stand-in while the rate was a per-round coin flip, because
        overshooting the intended rate was the only way to land the buyer on
        their bar. Rationing against the realised mix instead, the proxy fires
        on games that are perfectly safe -- one with two low rounds can push
        both and still show 18/20 high.

        What actually cost us game 2e48f9f7 was the buyer facing a credibility
        at or under their bar on a round they could still refuse. Assert that
        directly. Drops caused by the final-round sweep are excluded on purpose:
        the buyer has no decision left to make, which is why the sweep is free.
        """
        bar = 1_000_000 / 1_250_000
        for seed in range(60):
            worst = self._worst_live_credibility(seed)
            assert worst > bar, (
                f"seed {seed}: buyer faced credibility {worst:.4f} against a bar "
                f"of {bar:.4f} with rounds still to play"
            )

    def _worst_live_credibility(self, seed, *, p=0.8, rounds=20):
        import random
        from glee_agent.strategies.persuasion import _recommendation_record

        rng = random.Random(seed)
        history, worst = [], 1.0
        for round_ in range(1, rounds + 1):
            quality = "low" if rng.random() > p else "high"
            game = persuasion_game(
                action_type="seller_recommendation", slot="player_1", quality=quality,
                p=p, v=1_250_000, u=0.0, price=1_000_000,
                round_=round_, total_rounds=rounds, history=history,
            )
            game["game_id"] = f"quota-{seed}"
            recommends = _seller_recommends(game)
            history.append(persuasion_round(
                round_=round_, message="yes" if recommends else "no",
                bought=True, quality=quality,
            ))
            if round_ < rounds:
                nxt = persuasion_game(
                    action_type="seller_recommendation", slot="player_1", quality="low",
                    p=p, v=1_250_000, u=0.0, price=1_000_000,
                    round_=round_ + 1, total_rounds=rounds, history=history,
                )
                rec, delivered, _ = _recommendation_record(nxt)
                if rec:
                    worst = min(worst, delivered / rec)
        return worst

    def test_a_high_quality_product_is_never_talked_down(self):
        game = persuasion_game(
            action_type="seller_recommendation", slot="player_1", quality="high",
            p=0.8, v=1_250_000, u=0.0, price=1_000_000, round_=9, total_rounds=20,
            history=[persuasion_round(round_=r, message="yes", bought=True, quality="low")
                     for r in range(1, 9)],
        )
        assert _seller_recommends(game) is True


class TestRegimeAndNonBuyer:
    """The two structural questions to ask before choosing any message.

    Which persuasion problem is this -- can the buyer profit on the prior alone,
    can they profit at all -- and is this particular buyer even reading us.
    Observed in 9 of 25 seller games: recommendations that genuinely cleared the
    buyer's bar, four of them with a perfect record, refused for twenty rounds.
    """

    def test_classifies_the_four_markets(self):
        assert regime(0.5, 40, 100, 50) == "free"          # price under the dud value
        assert regime(0.5, 120, 100, 0) == "impossible"    # price over the good value
        assert regime(0.9, 60, 100, 0) == "easy"           # prior alone clears the bar
        assert regime(0.3, 60, 100, 0) == "hard"           # information required

    def test_the_knife_edge_counts_as_hard(self):
        # p exactly at tau leaves the buyer indifferent if we pool, and an
        # indifferent buyer walks. This is the config that sold 0 of 20.
        assert buyer_threshold(1_000_000, 1_250_000, 0) == pytest.approx(0.8)
        assert regime(0.8, 1_000_000, 1_250_000, 0) == "hard"

    def test_an_easy_market_recommends_everything(self):
        game = persuasion_game(
            action_type="seller_recommendation", slot="player_1", quality="low",
            p=0.9, v=100, u=0.0, price=60, round_=3, total_rounds=20,
        )
        assert _seller_recommends(game) is True

    def test_an_impossible_market_costs_nothing_to_push(self):
        # No posterior clears the bar, so honesty buys us no future sale either.
        game = persuasion_game(
            action_type="seller_recommendation", slot="player_1", quality="low",
            p=0.5, v=100, u=0.0, price=120, round_=3, total_rounds=20,
        )
        assert _seller_recommends(game) is True

    def _ignored(self, *, recommends, bought, quality="high"):
        # Seller-visible history: we see the quality of every round, bought or
        # not. `persuasion_round` models the BUYER's view, where a pass reveals
        # nothing, so it is the wrong builder for a seller-side test.
        return [
            {
                "round": r, "seller_message": "yes", "quality": quality,
                "buyer_decision": "yes" if bought else "no", "bought": bought,
                "seller_payoff": 0, "buyer_payoff": 0,
            }
            for r in range(1, recommends + 1)
        ]

    def test_detects_a_buyer_who_ignores_a_perfect_signal(self):
        game = persuasion_game(
            action_type="seller_recommendation", slot="player_1", quality="low",
            p=0.3, v=100, u=0.0, price=60, round_=9, total_rounds=20,
            history=self._ignored(recommends=8, bought=False),
        )
        assert buyer_ignores_us(game) is True
        # Reputation with them will never be spent, so stop funding it.
        assert _seller_recommends(game) is True

    def test_a_buyer_who_bought_is_not_ignoring_us(self):
        game = persuasion_game(
            action_type="seller_recommendation", slot="player_1", quality="low",
            p=0.3, v=100, u=0.0, price=60, round_=9, total_rounds=20,
            history=self._ignored(recommends=8, bought=True),
        )
        assert buyer_ignores_us(game) is False

    def test_patience_before_writing_a_buyer_off(self):
        # Two refusals is not evidence; it takes a real run of them.
        game = persuasion_game(
            action_type="seller_recommendation", slot="player_1", quality="low",
            p=0.3, v=100, u=0.0, price=60, round_=3, total_rounds=20,
            history=self._ignored(recommends=2, bought=False),
        )
        assert buyer_ignores_us(game) is False

    def test_refusals_of_a_weak_signal_do_not_count(self):
        # If our own record was below their bar, they were right to refuse and
        # the fault is ours -- that is not a buyer who ignores information.
        game = persuasion_game(
            action_type="seller_recommendation", slot="player_1", quality="low",
            p=0.3, v=100, u=0.0, price=60, round_=9, total_rounds=20,
            history=self._ignored(recommends=8, bought=False, quality="low"),
        )
        assert buyer_ignores_us(game) is False


class TestTheBareRecommendationArm:
    """The channel split: persuasion can go bare without silencing the others.

    Measured over every persuasion game on record, crossing from the `binary`
    channel to `text` costs us 10-18 points of sell rate in every value band
    (n=459-1001 per cell) against the same opponents -- while the field's sell
    rate goes UP across the same crossing. The reading is that much of the field
    matches tokens rather than reading prose. Whether they answer "Recommended."
    the way they answer "yes" is their move, so this ships off and is decided by
    an A/B, not by these tests.
    """

    def _msg(self, quality, **kw):
        history = [persuasion_round(round_=r, message="yes", bought=True, quality="high")
                   for r in range(1, 6)]
        return play(persuasion_game(
            action_type="seller_message", slot="player_1", quality=quality,
            p=kw.get("p", 0.9), v=kw.get("v", 125), u=0.0, price=kw.get("price", 100),
            round_=6, total_rounds=20, history=history,
        ))["message"]

    def test_the_flag_ships_off(self):
        from glee_agent import params
        assert params.PERSUASION.bare_recommendation is False

    def test_the_shipped_default_still_pitches(self):
        assert "Recommending this one." in self._msg("high")

    def test_the_arm_sends_the_same_two_words_the_binary_half_sends(self, bare_recommendation):
        assert self._msg("high") == "Recommended."
        assert self._msg("low", p=0.3, v=100, price=60) == "Not recommended."

    def test_the_arm_volunteers_nothing_else(self, bare_recommendation):
        for text in (self._msg("high"), self._msg("low", p=0.3, v=100, price=60)):
            for leak in ("125", "100", "record", "arithmetic", "track", "costs you"):
                assert leak not in text.lower()

    def test_the_arm_never_sends_an_empty_message(self, bare_recommendation):
        # safety.sanitize refills an empty seller_message with the fallback
        # pitch, which would put a sales line straight back on the wire.
        for text in (self._msg("high"), self._msg("low", p=0.3, v=100, price=60)):
            assert text.strip()

    def test_the_arm_does_not_touch_the_other_two_families(self, bare_recommendation):
        # The defect being fixed is persuasion's alone: there the message IS the
        # move, while a bargaining or negotiation message rides alongside a
        # number that already says the same thing.
        from glee_agent.strategies import bargaining, negotiation
        assert bargaining.SEND_MESSAGES is True
        assert negotiation.SEND_MESSAGES is True

    def test_the_arm_still_says_yes_exactly_when_the_binary_half_would(self, bare_recommendation):
        # Same decision, different wording -- the arm changes the channel, not
        # the policy. Anything else would confound the A/B.
        from glee_agent.strategies.persuasion import _seller_recommends
        for quality, kw in (("high", {}), ("low", {"p": 0.3, "v": 100, "price": 60})):
            history = [persuasion_round(round_=r, message="yes", bought=True, quality="high")
                       for r in range(1, 6)]
            game = persuasion_game(
                action_type="seller_message", slot="player_1", quality=quality,
                p=kw.get("p", 0.9), v=kw.get("v", 125), u=0.0, price=kw.get("price", 100),
                round_=6, total_rounds=20, history=history,
            )
            said_yes = self._msg(quality, **kw) == "Recommended."
            assert said_yes is _seller_recommends(game)


class TestTheTextChannelSaysOnlyYesOrNo:
    """Shipped behaviour: text mode carries the recommendation and nothing else.

    Half of these games use a `binary` channel that is already a bare yes/no.
    The other half use `text`, where the message is the whole move -- so it
    sends the same yes/no, with none of the pitch that used to ride along.
    """

    def _msg(self, quality, **kw):
        history = [persuasion_round(round_=r, message="yes", bought=True, quality="high")
                   for r in range(1, 6)]
        game = persuasion_game(
            action_type="seller_message", slot="player_1", quality=quality,
            p=kw.get("p", 0.9), v=kw.get("v", 125), u=0.0, price=kw.get("price", 100),
            round_=6, total_rounds=20, history=history,
        )
        return play(game)["message"]

    def test_a_recommendation_is_bare(self, messages_off):
        assert self._msg("high") == "Recommended."

    def test_a_refusal_is_bare(self, messages_off):
        assert self._msg("low", p=0.3, v=100, price=60) == "Not recommended."

    def test_nothing_about_us_or_the_numbers_goes_on_the_wire(self, messages_off):
        for text in (self._msg("high"), self._msg("low", p=0.3, v=100, price=60)):
            for leak in ("125", "100", "record", "arithmetic", "track", "costs you"):
                assert leak not in text.lower()

    def test_the_shipped_default_sends_the_full_message(self):
        # Guards the SHIPPED default. Flipping SEND_MESSAGES is expected to fail
        # exactly this one test and nothing else.
        from glee_agent import params
        assert params.SEND_MESSAGES is True

    def test_it_is_never_empty(self, messages_off):
        # An empty seller_message is refilled by safety.sanitize with the
        # fallback pitch, which would put a sales line back on the wire.
        for text in (self._msg("high"), self._msg("low", p=0.3, v=100, price=60)):
            assert text.strip()


class TestSellerMessageCarriesEvidence:
    def test_states_the_verifiable_record(self, messages_on):
        history = [persuasion_round(round_=r, message="yes", bought=True, quality="high")
                   for r in range(1, 6)]
        game = persuasion_game(
            action_type="seller_message", slot="player_1", quality="high",
            p=0.9, v=125, u=0.0, price=100, round_=6, total_rounds=20, history=history,
        )
        message = play(game)["message"]
        assert "5 of my 5" in message

    def test_gives_the_buyer_their_own_arithmetic(self, messages_on):
        game = persuasion_game(
            action_type="seller_message", slot="player_1", quality="high",
            p=0.9, v=125, u=0.0, price=100, round_=1, total_rounds=20,
        )
        message = play(game)["message"]
        assert "125" in message and "100" in message and "25" in message

    def test_a_refusal_is_still_plainly_a_refusal(self, messages_on):
        game = persuasion_game(
            action_type="seller_message", slot="player_1", quality="low",
            p=0.3, v=100, u=0.0, price=60, round_=2, total_rounds=20,
        )
        assert "not worth" in play(game)["message"]


class TestUnknownBuyerValue:
    """More than half our seller games never disclose the buyer's value.

    Without `tau` every rule built on it goes dark, and those games had the
    worst sale rate of any regime -- 15% of rounds bought against 100% in the
    easy regime. But the buyer brackets `tau` themselves: buying at credibility
    c proves tau <= c, refusing proves tau > c. No posterior over v required.
    """

    def _round(self, *, round_, recommend, bought, quality="high"):
        return {
            "round": round_, "seller_message": "yes" if recommend else "no",
            "quality": quality, "buyer_decision": "yes" if bought else "no",
            "bought": bought, "seller_payoff": 0, "buyer_payoff": 0,
        }

    def _game(self, history, *, round_=9, p=0.5):
        # v and u absent: exactly what the platform sends in these games.
        game = persuasion_game(
            action_type="seller_recommendation", slot="player_1", quality="low",
            p=p, price=100, round_=round_, total_rounds=20, history=history,
            seller_knows_values=False,
        )
        game["game_state"].pop("v", None)
        game["game_state"].pop("u", None)
        return game

    def test_a_purchase_puts_a_ceiling_on_their_bar(self):
        history = [self._round(round_=1, recommend=True, bought=True)]
        _lower, upper = estimate_threshold(self._game(history), 0.5)
        assert upper <= 0.5      # they bought at the prior, so tau is no higher

    def test_a_refusal_puts_a_floor_under_it(self):
        history = [self._round(round_=1, recommend=True, bought=False)]
        lower, upper = estimate_threshold(self._game(history), 0.5)
        assert lower >= 0.5 and upper == 1.0

    def test_the_bracket_narrows_as_they_answer(self):
        history = [
            self._round(round_=1, recommend=True, bought=False),
            self._round(round_=2, recommend=True, bought=True),
            self._round(round_=3, recommend=True, bought=True),
        ]
        lower, upper = estimate_threshold(self._game(history), 0.5)
        assert 0.0 < lower <= upper < 1.0

    def test_stays_honest_until_they_have_bought_something(self):
        # No ceiling on what they need, so the only lever is being believable.
        history = [self._round(round_=r, recommend=True, bought=False) for r in (1, 2)]
        assert _seller_recommends(self._game(history)) is False

    def test_spends_credibility_once_the_bar_is_known(self):
        # Bought repeatedly at a low bar, and our record is strong: there is
        # headroom above what they have shown they need.
        history = [self._round(round_=r, recommend=True, bought=True) for r in range(1, 9)]
        assert _seller_recommends(self._game(history, round_=18)) is True

    def test_writes_off_a_buyer_who_never_takes_anything(self):
        history = [self._round(round_=r, recommend=True, bought=False) for r in range(1, 9)]
        assert _seller_recommends(self._game(history)) is True

    def test_an_inconsistent_buyer_has_no_bar_to_respect(self):
        # Bought on weak evidence, refused later on stronger evidence.
        history = [
            self._round(round_=1, recommend=True, bought=True, quality="low"),
            self._round(round_=2, recommend=True, bought=True),
            self._round(round_=3, recommend=True, bought=True),
            self._round(round_=4, recommend=True, bought=False),
        ]
        lower, upper = estimate_threshold(self._game(history), 0.5)
        assert lower > upper
        assert _seller_recommends(self._game(history)) is True

    def test_a_known_value_game_is_untouched(self):
        # The bracket is only for the blind case; disclosed values still rule.
        game = persuasion_game(
            action_type="seller_recommendation", slot="player_1", quality="low",
            p=0.9, v=100, u=0.0, price=60, round_=3, total_rounds=20,
        )
        assert regime(0.9, 60, 100, 0.0) == "easy"
        assert _seller_recommends(game) is True


class TestSellerRationingIsMeasuredButNotActedOn:
    """Chunk 10: the rationing estimator went live, worked, and lost money.

    It did what it was built for -- games where we never bought a single round
    fell 34% -> 17%, hard-market buying rose 16.6% -> 30.8% of rounds. But those
    purchases came in at 71.2% high quality against a bar of 80.0% (n=333, 3.5
    sigma below), where the old policy sat at 79.4% and broke even. Persuasion
    lost 24 rating points over 152 games.

    `p / rate` is a CEILING, exact only if every high-quality unit is
    recommended, and it was validated on rounds we had already chosen to buy --
    which says nothing about the marginal rounds it newly licenses. It is kept,
    documented and tested as a measurement; it is not wired into the decision.
    """

    def _game(self, *, p, price, v, rounds, rec_every_n=1, total=20):
        history = [
            {"round": r, "seller_message": ("Worth it at this price." if r % rec_every_n == 0
                                            else "Nothing special. I'd understand a pass."),
             "buyer_decision": "no", "bought": False}
            for r in range(1, rounds + 1)
        ]
        return persuasion_game(
            action_type="buyer_decision", slot="player_2", p=p, v=v, u=0.0,
            price=price, round_=rounds + 1, total_rounds=total,
            seller_message="Worth it at this price.", history=history,
        )

    def test_the_estimator_still_reads_rationing_correctly(self):
        game = self._game(p=1 / 3, price=1_000_000, v=1_250_000, rounds=9, rec_every_n=3)
        assert signal_posterior(game, 1 / 3) > 1 / 3

    def test_but_the_buyer_does_not_act_on_it(self):
        # The regression this guards: wiring it back in without first validating
        # it on rounds we did not already want to buy.
        game = self._game(p=1 / 3, price=1_000_000, v=1_250_000, rounds=9, rec_every_n=3)
        assert play(game)["decision"] == "no"

    def test_a_seller_who_recommends_everything_reads_as_the_prior(self):
        game = self._game(p=1 / 3, price=1_000_000, v=1_250_000, rounds=9, rec_every_n=1)
        assert signal_posterior(game, 1 / 3) == pytest.approx(1 / 3)

    def test_the_estimate_stays_within_bounds(self):
        for rate_n in (1, 2, 3, 8):
            for p in (0.05, 1 / 3, 0.5, 0.95):
                game = self._game(p=p, price=100, v=125, rounds=8, rec_every_n=rate_n)
                assert 0.0 <= signal_posterior(game, p) <= 1.0

    def test_a_proven_liar_still_overrides_the_rationing(self):
        # Rationing is only a prior; rounds we bought are hard evidence and must
        # win. A seller who rations AND delivers junk gets no credit for it.
        history = [
            {"round": r, "seller_message": "Worth it at this price.",
             "buyer_decision": "yes", "bought": True, "quality": "low"}
            for r in range(1, 9)
        ]
        game = persuasion_game(
            action_type="buyer_decision", slot="player_2", p=1 / 3, v=1_250_000, u=0.0,
            price=1_000_000, round_=9, total_rounds=20,
            seller_message="Worth it at this price.", history=history,
        )
        assert play(game)["decision"] == "no"


# --- the knife edge, p == tau ------------------------------------------------


def test_knife_edge_rations_against_the_realised_mix():
    """At p == tau we ration on what we have actually recommended, not on a veto.

    The invariant that matters is the buyer's: the share of our recommendations
    that were genuinely high must stay above their bar, or the recommendation is
    worthless to them. Within that, we should be spending the allowance rather
    than sitting on it.
    """
    import random
    from glee_agent.strategies.persuasion import _seller_recommends

    def one_game(seed, p, v, price, rounds=20):
        rng = random.Random(seed)
        history, lows, lies, recs, highs = [], 0, 0, 0, 0
        for round_ in range(1, rounds + 1):
            quality = "low" if rng.random() > p else "high"
            game = persuasion_game(
                action_type="seller_recommendation", slot="player_1", quality=quality,
                p=p, v=v, u=0.0, price=price, round_=round_, total_rounds=rounds,
                history=history,
            )
            game["game_id"] = f"knife-{seed}"
            rec = _seller_recommends(game)
            if quality == "low":
                lows += 1
                lies += rec
            if rec:
                recs += 1
                highs += quality == "high"
            history.append(persuasion_round(
                round_=round_, message="yes" if rec else "no",
                bought=True, quality=quality,
            ))
        return (lies / lows if lows else 0.0, highs / recs if recs else 1.0)

    for p, v, price in ((0.8, 1_250_000, 1_000_000), (0.5, 100.0, 50.0)):
        runs = [one_game(s, p, v, price) for s in range(60)]
        low_push = sum(r[0] for r in runs) / len(runs)
        credibility = sum(r[1] for r in runs) / len(runs)
        # The buyer's invariant: our recommendations stay worth acting on.
        assert credibility >= p, (
            f"p={p}: recommendations averaged {credibility:.3f} high, under the bar {p}"
        )
        # ...and we are not hoarding the allowance. The credibility-margin veto
        # produced 0.35-0.47 here on live data; rationing on the realised mix
        # should clearly beat that.
        assert low_push > 0.47, f"p={p}: pushed only {low_push:.3f} of low rounds"


def test_easy_market_still_pushes_everything():
    """p strictly above tau is untouched -- it never reaches the knife branch."""
    from glee_agent.strategies.persuasion import play

    game = persuasion_game(
        action_type="seller_recommendation",
        slot="player_1",
        p=0.8,
        v=100.0,
        price=25.0,          # tau = 0.25, well under p
        quality="low",
        round_=1,
        total_rounds=20,
    )
    assert play(game)["decision"] == "yes"


class TestTheInteriorCanRationOnTheMixToo:
    """`hard_regime_rations_on_mix`: the knife rule extended to p < tau.

    The live credibility gate is anchored at the prior, so where p sits under
    the buyer's bar it stays shut for longer than the game lasts. Replaying it
    over 6,390 logged interior low rounds it opened on 6.3% of them, and on only
    9.7% with the margin taken to zero -- so the margin is not what binds, the
    anchor is. The mix rule has no anchor and a fixed point at tau.

    These pin the two things that make it safe to try: it does more than the
    gate, and it still never sells the buyer a posterior under their bar.
    """

    P_INT, V, PRICE = 0.5, 1_250_000, 1_000_000     # tau = 0.80, so p < tau

    def _play(self, seed, *, rounds=20):
        """Play one interior game, returning (lie rate, worst live posterior)."""
        import random
        from glee_agent.strategies.persuasion import _recommendation_record

        rng = random.Random(seed)
        history, lows, lies, worst = [], 0, 0, 1.0
        for round_ in range(1, rounds + 1):
            quality = "low" if rng.random() > self.P_INT else "high"
            game = persuasion_game(
                action_type="seller_recommendation", slot="player_1", quality=quality,
                p=self.P_INT, v=self.V, u=0.0, price=self.PRICE,
                round_=round_, total_rounds=rounds, history=history,
            )
            game["game_id"] = f"interior-{seed}"
            recommends = _seller_recommends(game)
            if quality == "low":
                lows += 1
                lies += recommends
            history.append(persuasion_round(
                round_=round_, message="yes" if recommends else "no",
                bought=True, quality=quality,
            ))
            if round_ < rounds:
                nxt = persuasion_game(
                    action_type="seller_recommendation", slot="player_1", quality="low",
                    p=self.P_INT, v=self.V, u=0.0, price=self.PRICE,
                    round_=round_ + 1, total_rounds=rounds, history=history,
                )
                rec, delivered, _ = _recommendation_record(nxt)
                if rec:
                    worst = min(worst, delivered / rec)
        return (lies / lows if lows else 0.0), worst

    def test_the_shipped_default_leaves_the_interior_alone(self):
        # Guards the SHIPPED default: flipping the flag is expected to change
        # this number and nothing outside this class.
        rates = [self._play(s)[0] for s in range(40)]
        assert sum(rates) / len(rates) < 0.15

    def test_rationing_on_the_mix_frees_the_interior(self, rations_on_mix):
        rates = [self._play(s)[0] for s in range(40)]
        assert sum(rates) / len(rates) > 0.20

    def test_but_never_past_the_persuasion_optimum(self, rations_on_mix):
        """q* is the most a buyer at their bar can be made to tolerate.

        Overshooting it is the one way this rule could be worse than the gate it
        replaces, so bound it directly rather than trusting the fixed point.
        """
        rates = [self._play(s)[0] for s in range(40)]
        q_star = lie_budget(self.P_INT, self.PRICE, self.V, 0)
        assert sum(rates) / len(rates) <= q_star

    def test_the_buyer_is_still_never_left_under_the_bar(self, rations_on_mix):
        bar = buyer_threshold(self.PRICE, self.V, 0)
        for seed in range(40):
            _, worst = self._play(seed)
            assert worst > bar, (
                f"seed {seed}: buyer faced posterior {worst:.4f} against a bar of "
                f"{bar:.4f} with rounds still to play"
            )

    def test_a_high_quality_product_is_still_never_talked_down(self, rations_on_mix):
        game = persuasion_game(
            action_type="seller_recommendation", slot="player_1", quality="high",
            p=self.P_INT, v=self.V, u=0.0, price=self.PRICE, round_=9, total_rounds=20,
            history=[persuasion_round(round_=r, message="yes", bought=True, quality="low")
                     for r in range(1, 9)],
        )
        assert _seller_recommends(game) is True
