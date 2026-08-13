import pytest

from glee_agent.params import BARGAINING as P
from glee_agent.strategies.bargaining import (
    _final_round_is_ours,
    endgame_sweep,
    opponent_is_sweeping,
    play,
    proposer_share,
    stonewall_threshold,
)
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


class TestImpatienceClosesEarly:
    """Regression: game c8cf3c48. Our delta was 0.9 and we ground seven rounds.

    They opened at 427,179 of a 1,000,000 pot. We rejected, haggled to 459,907 --
    a 7.6% improvement -- and were paid 244,413, because six rounds of our own
    inflation cost 47%. Rejecting was priced at one round of delay when it really
    cost six, and the more impatient we are the more that error costs.
    """

    def _live_offer(self, my_gain, *, delta, money=1_000_000, round_=1, max_rounds=12):
        return bargaining_game(
            action_type="decision",
            slot="player_2",
            complete_information=False,
            money=money,
            round_=round_,
            max_rounds=max_rounds,
            delta_2=delta,
            last_offer={
                "player_1_gain": money - my_gain,
                "player_2_gain": my_gain,
                "proposer": "player_1",
                "round": round_,
            },
        )

    def test_takes_the_round_one_offer_that_cost_us_the_game(self):
        # 427,179 now beat 459,907 six rounds later by roughly 183,000.
        game = self._live_offer(427_179.49, delta=0.9)
        assert play(game)["decision"] == "accept"

    def test_a_patient_player_can_still_hold_out_for_more(self):
        # Same offer, same pot: only the cost of waiting differs. 30% sits
        # between the two stonewall bars (19.5% at delta 0.9, 42.4% at 0.995) --
        # 427,179 now clears both, since a bleeding player signs almost anything.
        patient = play(self._live_offer(300_000, delta=0.995))["decision"]
        impatient = play(self._live_offer(300_000, delta=0.9))["decision"]
        assert (patient, impatient) == ("reject", "accept")

    def test_a_lowball_is_still_a_lowball_when_impatient(self):
        # Impatience is not capitulation: 5% of the pot stays worth rejecting.
        assert play(self._live_offer(50_000, delta=0.9))["decision"] == "reject"

    def test_acceptance_threshold_falls_as_patience_falls(self):
        thresholds = []
        for delta in (0.99, 0.95, 0.9, 0.8):
            lowest_accepted = None
            for gain in range(500_000, 100_000, -10_000):
                if play(self._live_offer(gain, delta=delta))["decision"] == "accept":
                    lowest_accepted = gain
                else:
                    break
            thresholds.append(lowest_accepted)
        assert all(t is not None for t in thresholds)
        assert thresholds == sorted(thresholds, reverse=True)

    def test_impatient_openings_sit_closer_to_the_floor(self):
        def demand(delta):
            action = play(
                bargaining_game(
                    slot="player_2", complete_information=False, money=1_000_000,
                    round_=1, max_rounds=12, delta_2=delta,
                )
            )
            return action["bob_gain"]

        assert demand(0.8) < demand(0.9) < demand(0.99)

    def test_opening_never_drops_below_the_floor_we_defend(self):
        action = play(
            bargaining_game(
                slot="player_2", complete_information=False, money=1_000_000,
                round_=1, max_rounds=12, delta_2=0.5,
            )
        )
        assert action["bob_gain"] >= 1_000_000 * P.never_concede_below - 1


class TestUndiscountedGamesDoNotDeadlock:
    """Regression: delta 1.0 -- a third of the observed grid -- deadlocked at $0.

    With no discounting the Rubinstein denominator is zero and the fixed point
    was read as 1.0: we demanded 97% every round and accepted nothing below 97%.
    Observed across five open-ended games: 50 consecutive rejections of standing
    offers worth 65-72% of the pot, still unresolved at round 99. A no-deal pays
    $0, the bottom of the percentile scale, so this was the worst bug we had.
    """

    def _standing_offer(self, share, *, delta=1.0, round_=1, pot=1_000_000, max_rounds=None):
        return bargaining_game(
            action_type="decision",
            slot="player_2",
            complete_information=False,
            money=pot,
            round_=round_,
            max_rounds=max_rounds,
            delta_2=delta,
            last_offer={
                "player_1_gain": pot * (1 - share),
                "player_2_gain": pot * share,
                "proposer": "player_1",
                "round": round_,
            },
        )

    def test_no_time_pressure_anchors_on_the_even_split(self):
        # Every split is an equilibrium here; 1.0 was an arbitrary pick that
        # happened to be the one guaranteeing no deal.
        assert proposer_share(1.0, 1.0, None) == 0.5

    def test_discounted_fixed_point_is_unchanged(self):
        # The fix must not disturb the non-degenerate case.
        assert proposer_share(0.9, 0.9, None) == pytest.approx(0.1 / 0.19)

    @pytest.mark.parametrize("share", [0.72, 0.70, 0.65])
    def test_takes_the_generous_offers_it_used_to_refuse(self, share):
        assert play(self._standing_offer(share))["decision"] == "accept"

    def test_a_marginal_offer_is_not_taken_instantly_but_does_get_taken(self):
        # 40% is under the 45% bar a perfectly patient player holds, so it waits
        # -- and is worth signing rather than spending another 90 rounds proving
        # a point, which is what the walk-down guarantees.
        assert play(self._standing_offer(0.40, round_=1))["decision"] == "reject"
        assert play(self._standing_offer(0.40, round_=12))["decision"] == "accept"

    def test_open_ended_games_always_close_eventually(self):
        # The failure mode was unbounded rejection, so assert termination.
        for share in (0.40, 0.46, 0.55):
            decisions = [
                play(self._standing_offer(share, round_=r))["decision"] for r in range(1, 25)
            ]
            assert "accept" in decisions, f"never accepted {share:.0%} in 24 rounds"

    def test_a_genuine_lowball_is_still_refused_early(self):
        assert play(self._standing_offer(0.05, round_=1))["decision"] == "reject"

    def test_offers_leave_the_opponent_a_real_share(self):
        action = play(
            bargaining_game(
                slot="player_2", complete_information=False, money=1_000_000,
                round_=1, max_rounds=None, delta_2=1.0,
            )
        )
        # Was 97% of the pot for us, every round, forever.
        assert action["bob_gain"] <= 1_000_000 * P.opening_demand + 1

    def test_ceiling_holds_when_only_we_are_patient(self):
        # Complete information, we pay nothing for delay and they do: theory says
        # we can take everything. No opponent signs that, and $0 is the penalty.
        share = proposer_share(1.0, 0.9, None)
        assert share == 1.0                       # the model really does say this
        # The ceiling binds where the damage was: what we will sign. Uncapped,
        # this demanded 97% of the pot before it would accept anything.
        #
        # 11 rounds, not 12, so the last proposal is THEIRS and the endgame sweep
        # stays out of it -- holding out for 97% is correct when we own the final
        # round (see TestEndgameSweep) and this test is about the other case.
        offer = self._standing_offer(0.75, delta=1.0, pot=1000, max_rounds=11)
        offer["game_state"]["complete_information"] = True
        offer["game_state"]["delta_1"] = 0.9
        assert play(offer)["decision"] == "accept"


class TestEndgameSweep:
    """Delta 1.0 + the last proposal is ours: stall to the end and take the pot.

    Waiting costs a perfectly patient player nothing, and a responder facing the
    final offer chooses between it and $0. Both halves are required -- with real
    inflation stalling burns the pot we are stalling for, and if the last word is
    theirs we arrive at the end with nothing to threaten them with.
    """

    def _decision(self, my_gain, *, delta, round_, max_rounds, pot=1000, slot="player_2"):
        other = "player_1" if slot == "player_2" else "player_2"
        # player_1 proposes odd rounds, player_2 even -- so the responder on an
        # even round is player_1, and vice versa.
        proposer = "player_1" if round_ % 2 else "player_2"
        game = bargaining_game(
            action_type="decision", slot=slot, money=pot, round_=round_,
            max_rounds=max_rounds, delta_1=delta, delta_2=delta,
            complete_information=False,
            last_offer={
                f"{slot}_gain": my_gain, f"{other}_gain": pot - my_gain,
                "proposer": proposer, "round": round_,
            },
        )
        game["game_state"]["proposer"] = proposer
        return game

    def test_knows_whose_the_final_round_is(self):
        # 12 rounds, player_1 opens: the last proposal belongs to player_2.
        state = {"horizon_known": True, "max_rounds": 12, "round": 7, "proposer": "player_1"}
        assert _final_round_is_ours(state, "player_2") is True
        assert _final_round_is_ours(state, "player_1") is False
        # 11 rounds instead, and it flips.
        state = {"horizon_known": True, "max_rounds": 11, "round": 7, "proposer": "player_1"}
        assert _final_round_is_ours(state, "player_1") is True

    def test_open_ended_games_have_no_final_round_to_sweep(self):
        state = {"horizon_known": False, "round": 3, "proposer": "player_2"}
        assert _final_round_is_ours(state, "player_2") is False

    def test_refuses_a_good_offer_when_the_endgame_is_free_and_ours(self):
        # 60% now is worth less than 97% at round 12, and the wait is free.
        game = self._decision(600, delta=1.0, round_=3, max_rounds=12)
        assert play(game)["decision"] == "reject"
        assert endgame_sweep(game["game_state"], "player_2") is True

    def test_takes_an_offer_that_already_beats_the_endgame(self):
        game = self._decision(995, delta=1.0, round_=3, max_rounds=12)
        assert play(game)["decision"] == "accept"

    def test_does_not_stall_when_delay_actually_costs_us(self):
        # Same parity, same horizon -- only the inflation differs.
        game = self._decision(600, delta=0.9, round_=3, max_rounds=12)
        assert endgame_sweep(game["game_state"], "player_2") is False
        assert play(game)["decision"] == "accept"

    def test_does_not_stall_when_the_last_word_is_theirs(self):
        # 11 rounds: player_1 proposes last, so as player_2 we have no threat.
        game = self._decision(600, delta=1.0, round_=3, max_rounds=11)
        assert endgame_sweep(game["game_state"], "player_2") is False

    def test_demands_the_endgame_share_on_the_way_there(self):
        # Our earlier proposals cost nothing to make and are upside if taken.
        game = bargaining_game(
            slot="player_2", money=1000, round_=4, max_rounds=12,
            delta_1=1.0, delta_2=1.0, complete_information=False,
        )
        game["game_state"]["proposer"] = "player_2"
        action = play(game)
        assert action["bob_gain"] >= 1000 * (P.final_round_demand - P.min_opponent_share)

    def test_the_sweep_still_leaves_them_a_token(self):
        game = bargaining_game(
            slot="player_2", money=1000, round_=12, max_rounds=12,
            delta_1=1.0, delta_2=1.0, complete_information=False,
        )
        game["game_state"]["proposer"] = "player_2"
        assert play(game)["alice_gain"] >= 1000 * P.min_opponent_share - 1


class TestCounteringASweeper:
    """The mirror image: they own the final round and are stalling to it.

    Structurally we are losing -- a patient player holding the last proposal can
    extract almost everything, and our alternative at the end is their token or
    $0. What is still winnable is the difference between their token and a real
    share taken early, so the job is to notice in time and bank the better one.
    """

    def _history(self, *, refusals, their_best, pot=1000):
        entries = []
        for round_ in range(1, refusals + 1):
            entries.append({
                "round": round_ * 2,
                "proposer": "player_2",
                "offer": {"player_2_gain": pot * 0.8, "player_1_gain": pot * 0.2},
                "decision": "reject",
            })
            entries.append({
                "round": round_ * 2 + 1,
                "proposer": "player_1",
                "offer": {"player_2_gain": their_best, "player_1_gain": pot - their_best},
                "decision": "reject",
            })
        return entries

    def _game(self, *, refusals, their_best, offered, pot=1000, max_rounds=11, round_=9):
        game = bargaining_game(
            action_type="decision", slot="player_2", money=pot, round_=round_,
            max_rounds=max_rounds, delta_1=1.0, delta_2=1.0,
            complete_information=False,
            last_offer={"player_2_gain": offered, "player_1_gain": pot - offered,
                        "proposer": "player_1", "round": round_},
            history=self._history(refusals=refusals, their_best=their_best, pot=pot),
        )
        # 11 rounds, player_1 opens -> the last proposal is theirs.
        game["game_state"]["proposer"] = "player_1"
        return game

    def test_detects_a_sweeper(self):
        game = self._game(refusals=3, their_best=40, offered=40)
        assert opponent_is_sweeping(game, "player_2") is True

    def test_does_not_cry_sweep_when_we_hold_the_endgame(self):
        game = self._game(refusals=3, their_best=40, offered=40, max_rounds=12)
        game["game_state"]["proposer"] = "player_1"
        assert opponent_is_sweeping(game, "player_2") is False

    def test_two_refusals_are_not_yet_evidence(self):
        # An ordinary hard bargainer says no more than once.
        game = self._game(refusals=2, their_best=40, offered=40)
        assert opponent_is_sweeping(game, "player_2") is False

    def test_a_real_offer_on_the_table_is_not_a_sweep(self):
        # They are converging toward a split, which is negotiating, not sweeping.
        game = self._game(refusals=4, their_best=450, offered=450)
        assert opponent_is_sweeping(game, "player_2") is False

    def test_banks_a_modest_share_rather_than_be_swept(self):
        # 12% now beats the 3% token waiting at the end.
        game = self._game(refusals=3, their_best=120, offered=120)
        assert play(game)["decision"] == "accept"

    def test_still_refuses_the_token_itself(self):
        # Capitulating is not the same as accepting anything: 3% now is no better
        # than 3% later, so there is nothing to gain by taking it early.
        game = self._game(refusals=3, their_best=30, offered=30)
        assert play(game)["decision"] == "reject"

    def test_an_ordinary_negotiation_is_unaffected(self):
        # No sweep detected -> the normal threshold governs, and a lowball with
        # rounds to spare is still refused.
        game = self._game(refusals=0, their_best=0, offered=50, max_rounds=11, round_=1)
        assert opponent_is_sweeping(game, "player_2") is False
        assert play(game)["decision"] == "reject"

    def test_says_so_out_loud(self):
        game = bargaining_game(
            slot="player_2", money=1000, round_=8, max_rounds=11,
            delta_1=1.0, delta_2=1.0, complete_information=False,
            history=self._history(refusals=3, their_best=40),
        )
        game["game_state"]["proposer"] = "player_2"
        assert "rather book nothing" in play(game)["message"]


class TestStonewallThreshold:
    """What rejecting is worth against a field that does not concede.

    Measured over 55 games: their offers drifted a median +0.5% from first to
    last however long we waited, and our counters landed 15% of the time at
    best. Pricing rejection as "they concede next round" cost 32.5% of the
    nominal split to delay, so the bar is derived from what they actually do.
    """

    def _bar(self, delta):
        return stonewall_threshold({"delta_2": delta, "horizon_known": True,
                                    "max_rounds": 12, "round": 1}, "player_2")

    def test_the_bar_rises_with_patience(self):
        bars = [self._bar(d) for d in (0.8, 0.9, 0.95, 0.99, 1.0)]
        assert bars == sorted(bars)
        assert bars[0] < 0.2 < bars[-1]

    def test_a_bleeding_player_signs_almost_anything(self):
        # 20% of the pot gone per round: holding out for a fair split is paying
        # more for the argument than the argument can possibly win.
        assert self._bar(0.8) < 0.15

    def test_a_costless_player_holds_the_line(self):
        # Nothing to lose by waiting, so there is no reason to take a bad split.
        assert self._bar(1.0) >= P.realistic_counter_share - 1e-9

    def test_matches_the_closed_form(self):
        p, demand, delta = P.counter_success_rate, P.realistic_counter_share, 0.9
        expected = p * demand * delta / (1 - (1 - p) * delta ** 2)
        assert self._bar(0.9) == pytest.approx(expected)

    def test_an_impatient_player_takes_the_stonewalled_offer(self):
        # The observed shape: they offer 18% and never move (15% 15% 16% 16% 16%
        # was a real sequence). Bleeding 20% a round, 18% now beats 18% later,
        # which is the only alternative actually on offer.
        game = bargaining_game(
            action_type="decision", slot="player_2", money=1000, round_=1,
            max_rounds=12, delta_2=0.8, complete_information=False,
            last_offer={"player_2_gain": 180, "player_1_gain": 820,
                        "proposer": "player_1", "round": 1},
        )
        assert play(game)["decision"] == "accept"

    def test_but_not_when_waiting_is_free(self):
        game = bargaining_game(
            action_type="decision", slot="player_2", money=1000, round_=1,
            max_rounds=12, delta_2=1.0, complete_information=False,
            last_offer={"player_2_gain": 180, "player_1_gain": 820,
                        "proposer": "player_1", "round": 1},
        )
        game["game_state"]["proposer"] = "player_1"
        assert play(game)["decision"] == "reject"
