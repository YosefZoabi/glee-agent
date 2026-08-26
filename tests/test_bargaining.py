import pytest

from glee_agent.params import BARGAINING as P
from glee_agent.strategies.bargaining import (
    _final_round_is_ours,
    endgame_hold_value,
    endgame_sweep,
    hold_out_value,
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
        # Rounds 1 and 5 of an 8-round game are both ours to propose, so the
        # last word is theirs in both -- comparing rounds of opposite parity
        # would compare two different games, one where we own the endgame seat
        # and one where we do not.
        early = play(bargaining_game(round_=1, max_rounds=8))["alice_gain"]
        late = play(bargaining_game(round_=5, max_rounds=8))["alice_gain"]
        assert late < early

    def test_demand_rises_toward_the_final_ask_when_the_last_word_is_ours(self):
        # Proposing at round 6 of 8 puts the last proposal at round 8 with us,
        # where the responder chooses between our number and $0. Conceding into
        # that is giving away the one seat they cannot take from us.
        early = play(bargaining_game(round_=2, max_rounds=8))["alice_gain"]
        late = play(bargaining_game(round_=6, max_rounds=8))["alice_gain"]
        assert late > early

    def test_final_offer_still_leaves_the_opponent_a_reason_to_sign(self):
        action = play(bargaining_game(round_=6, max_rounds=6, money=1000))
        assert action["bob_gain"] >= 1000 * (1 - P.final_round_demand) - 1

    def test_never_offers_the_opponent_nothing(self):
        action = play(bargaining_game(round_=1, max_rounds=6, money=1000))
        assert action["bob_gain"] > 0

    def test_no_message_is_ever_sent(self, messages_off):
        # We play as though the channel were not there, so a game that ALLOWS
        # messages gets one just as silent as a game that forbids them.
        assert "message" not in play(bargaining_game(messages_allowed=False))
        assert "message" not in play(bargaining_game(messages_allowed=True))

    def test_message_omitted_when_the_game_forbids_them(self, messages_on):
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

    def test_holds_the_endgame_seat_rather_than_softening_into_it(self):
        # This used to assert the opposite, and the opposite was a bug. Answering
        # an offer at all means they proposed this round, so the next round is
        # ours -- and at round 5 of 6 the next round is the last one, where the
        # responder picks between our number and $0. Softening one round short of
        # the seat hands back the whole point of holding it. 12% now against
        # 97% x 0.9 = 87% one round later is not a close call.
        near_end = self._offer(120, 880, round_=5, max_rounds=6)
        assert play(near_end)["decision"] == "reject"
        assert play(self._offer(120, 880, round_=1, max_rounds=6))["decision"] == "reject"

    def test_still_capitulates_on_the_final_round_itself(self):
        # The softening this replaces is not gone, just moved to where it is
        # true: on the last round rejecting really does pay $0.
        assert play(self._offer(120, 880, round_=6, max_rounds=6))["decision"] == "accept"

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
        # Same offer, same pot: only the cost of waiting differs. The separating
        # number moved from 300,000 to 500,000 because the last proposal of this
        # 12-round game is ours, and waiting eleven rounds for it is worth
        # 97% x 0.9**11 = 30% to the impatient player and 92% to the patient one.
        patient = play(self._live_offer(500_000, delta=0.995))["decision"]
        impatient = play(self._live_offer(500_000, delta=0.9))["decision"]
        assert (patient, impatient) == ("reject", "accept")

    def test_a_lowball_is_still_a_lowball_when_impatient(self):
        # Impatience is not capitulation: 5% of the pot stays worth rejecting.
        assert play(self._live_offer(50_000, delta=0.9))["decision"] == "reject"

    def test_acceptance_threshold_falls_as_patience_falls(self):
        thresholds = []
        for delta in (0.99, 0.95, 0.9, 0.8):
            lowest_accepted = None
            # Scans from the whole pot down: at delta 0.99 the bar is now 87%,
            # since eleven rounds of waiting for our own final proposal costs
            # almost nothing. Starting at 500,000 found no accept at all.
            for gain in range(1_000_000, 100_000, -10_000):
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
        # 40% is under the bar a perfectly patient player holds, so it waits --
        # and it does still get taken, at the round-97 collapse rather than
        # inside a dozen rounds. `free_clock_accept_floor` deliberately stopped
        # walking the bar down early here: at delta 1.0 the offer is worth
        # exactly as much on round 97 as on round 1, so the rounds spent are
        # free and the chance they improve their offer is not.
        assert play(self._standing_offer(0.40, round_=1))["decision"] == "reject"
        assert play(self._standing_offer(0.40, round_=12))["decision"] == "reject"
        assert play(self._standing_offer(0.40, round_=97))["decision"] == "accept"

    def test_open_ended_games_always_close_eventually(self):
        # The failure mode was unbounded rejection, so assert termination -- and
        # termination is the whole of the claim. Which round it lands on is a
        # pricing question, and on a free clock the answer is "the last one that
        # is still free", because the server pays both sides $0 only at 99.
        for share in (0.40, 0.46, 0.55):
            decisions = [
                play(self._standing_offer(share, round_=r))["decision"]
                for r in list(range(1, 25)) + [96, 97, 98]
            ]
            assert "accept" in decisions, f"never accepted {share:.0%} before the cap"

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

    def test_says_so_out_loud(self, messages_on):
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

    def test_the_horizon_does_not_change_the_demand(self):
        # Splitting the demand by horizon was tried and did not replicate --
        # +0.0025 across the bounded half against a proper control. See
        # `realistic_counter_share`.
        open_bar = stonewall_threshold({"delta_2": 0.9, "horizon_known": False,
                                        "round": 1}, "player_2")
        assert open_bar == pytest.approx(self._bar(0.9))

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


class TestTheEndgameSeat:
    """Regression: chunk 7. We signed 38% while owning the final proposal.

    73bcc09c is the clearest case -- our delta 0.95, theirs 1.0, twelve rounds,
    they opened, so round 12 was ours. We took 38% in round 1. Riding to our own
    last proposal and asking `final_round_demand` there is worth
    0.97 * 0.95**11 = 55% in round-1 money, and it is a guarantee rather than a
    forecast: they cannot take that seat from us, and the responder facing the
    last offer is choosing between it and $0.

    The record backs the price. Across every bargaining game we have played, the
    last proposal was ours in 68 of them: 68 agreements, 0 no-deals, and all 12
    that ran to the final round were signed at 97%.

    `endgame_sweep` already did this at delta 1.0. This is the same claim priced
    for a player who pays for the wait.
    """

    def _offer(self, my_share, *, delta, round_, max_rounds, pot=1_000_000, ci=False):
        # They proposed this round, so the next one is ours: with an even
        # `max_rounds` and an odd `round_`, the last proposal is ours.
        return bargaining_game(
            action_type="decision", slot="player_2", money=pot, round_=round_,
            max_rounds=max_rounds, delta_2=delta, delta_1=0.9,
            complete_information=ci,
            last_offer={"player_1_gain": pot * (1 - my_share),
                        "player_2_gain": pot * my_share,
                        "proposer": "player_1", "round": round_},
        )

    def test_refuses_the_offer_that_cost_us_the_chunk(self):
        assert play(self._offer(0.38, delta=0.95, round_=1, max_rounds=12))["decision"] == "reject"

    def test_the_seat_is_worth_more_the_closer_it_gets(self):
        bars = []
        for round_ in (1, 5, 9, 11):
            lowest = None
            for share in [s / 100 for s in range(99, 0, -1)]:
                if play(self._offer(share, delta=0.9, round_=round_, max_rounds=12))["decision"] == "accept":
                    lowest = share
            bars.append(lowest)
        assert bars == sorted(bars), bars

    def test_an_impatient_player_does_not_wait_for_it(self):
        # 0.97 * 0.8**11 is 8% of the pot: the wait costs more than the seat is
        # worth, so the evidence bar stays in charge and 30% is still signable.
        assert play(self._offer(0.30, delta=0.8, round_=1, max_rounds=12))["decision"] == "accept"

    def test_does_not_fire_when_the_last_word_is_theirs(self):
        # Same everything, one round later, which flips the parity.
        held = play(self._offer(0.38, delta=0.95, round_=2, max_rounds=12))
        assert held["decision"] == "accept"

    def test_does_not_fire_without_a_known_horizon(self):
        # No horizon, no final round to hold, so there is no seat to price.
        assert endgame_hold_value(
            self._offer(0.38, delta=1.0, round_=1, max_rounds=None)["game_state"], "player_2"
        ) == 0.0

    def test_the_bar_collapse_no_longer_hands_the_seat_back(self):
        # Answering an offer with two rounds left means they proposed at
        # `max_rounds - 1`, so the last round is always ours. Collapsing to
        # `endgame_floor` there was giving away the seat one round before
        # sitting in it.
        game = self._offer(0.10, delta=0.95, round_=11, max_rounds=12)
        assert play(game)["decision"] == "reject"


class TestTheNewFloorsNeverConcedeMore:
    """The whole change is only safe if it cannot make us sign for less.

    Every new claim enters through a `max` against the bar that was already
    there, so this is a property, not a coincidence -- and it is worth pinning,
    because the value of the previous tuning is entirely in deals we do sign.
    """

    @pytest.mark.parametrize("delta_me", [0.8, 0.9, 0.95, 1.0])
    @pytest.mark.parametrize("delta_them", [0.8, 0.9, 0.95, 1.0])
    @pytest.mark.parametrize("max_rounds", [None, 6, 12])
    @pytest.mark.parametrize("ci", [True, False])
    def test_the_bar_never_falls_below_the_evidence_bar(self, delta_me, delta_them, max_rounds, ci):
        for round_ in range(1, (max_rounds or 12) + 1):
            state = bargaining_game(
                action_type="decision", slot="player_2", money=1000, round_=round_,
                max_rounds=max_rounds, delta_1=delta_them, delta_2=delta_me,
                complete_information=ci,
            )["game_state"]
            combined = max(stonewall_threshold(state, "player_2"),
                           hold_out_value(state, "player_2") * P.accept_slack)
            assert combined >= stonewall_threshold(state, "player_2") - 1e-12

    def test_a_guessed_opponent_delta_never_raises_the_bar(self):
        # Under incomplete information `_deltas` fills theirs in with ours. That
        # guess is fine for shaping an offer and far too thin to bet a raised
        # accept bar on, so the equilibrium claim is only made when their delta
        # is actually on the table.
        def bar(ci):
            state = bargaining_game(
                action_type="decision", slot="player_2", money=1000, round_=1,
                max_rounds=None, delta_1=0.8, delta_2=0.95, complete_information=ci,
            )["game_state"]
            return hold_out_value(state, "player_2")

        assert bar(ci=False) == 0.0
        assert bar(ci=True) > 0.0


class TestTheDeadlineBeatsTheClosedForm:
    """Regression: 7159f219 and 9bb27d9e, chunk 8. We took 2% of the pot.

    Our delta 1.0, twelve rounds, and the last proposal THEIRS. The
    infinite-horizon share says a player who pays nothing for delay can hold out
    for everything, so the equilibrium bar sat at 73% -- while the actual
    continuation, with them holding the seat, was 22% at round 2 and 5% by round
    10. We turned down 72% of the pot at round 10 and then took the 2% they
    offered at round 12, where refusing pays $0.

    A deadline is precisely what makes "delay is free" false, so past one the
    finite recursion is not a stylised alternative to the closed form.
    """

    def _offer(self, my_share, *, round_, max_rounds=12, pot=10_000, d_me=1.0, d_them=0.95):
        # We are player_1 proposing on odd rounds, so an even `max_rounds` puts
        # the last proposal with them.
        return bargaining_game(
            action_type="decision", slot="player_1", money=pot, round_=round_,
            max_rounds=max_rounds, delta_1=d_me, delta_2=d_them,
            complete_information=True,
            last_offer={"player_1_gain": pot * my_share,
                        "player_2_gain": pot * (1 - my_share),
                        "proposer": "player_2", "round": round_},
        )

    def test_signs_the_offer_it_used_to_grind_past(self):
        assert play(self._offer(0.498, round_=2))["decision"] == "accept"

    def test_signs_the_72_percent_it_turned_down_at_round_ten(self):
        assert play(self._offer(0.72, round_=10))["decision"] == "accept"

    def test_the_bar_falls_as_their_seat_gets_closer(self):
        bars = []
        for round_ in (2, 6, 10):
            lowest = None
            for share in [s / 100 for s in range(99, 0, -1)]:
                if play(self._offer(share, round_=round_))["decision"] == "accept":
                    lowest = share
            bars.append(lowest)
        assert bars == sorted(bars, reverse=True), bars

    def test_an_open_ended_game_still_uses_the_closed_form(self):
        # No deadline, so nothing makes "delay is free" false: a910fa01 was
        # exactly this shape and holding out was right there.
        game = bargaining_game(
            action_type="decision", slot="player_1", money=1_000_000, round_=1,
            max_rounds=None, delta_1=1.0, delta_2=0.8, complete_information=True,
            last_offer={"player_1_gain": 447_000, "player_2_gain": 553_000,
                        "proposer": "player_2", "round": 1},
        )
        assert play(game)["decision"] == "reject"

    def test_the_endgame_seat_is_untouched_when_it_is_ours(self):
        # fb5dcaac: refused 38% at round 1 and took 97% at round 12. The seat is
        # a separate claim and must survive this cap.
        game = bargaining_game(
            action_type="decision", slot="player_2", money=1_000_000, round_=1,
            max_rounds=12, delta_1=1.0, delta_2=0.95, complete_information=True,
            last_offer={"player_1_gain": 620_000, "player_2_gain": 380_000,
                        "proposer": "player_1", "round": 1},
        )
        assert play(game)["decision"] == "reject"


class TestTheOpenEndedWalkOnlyEverGoesDown:
    """Regression: 92727cf1. Sixty-nine rounds to bank 274 of a 353,652 split.

    The open-ended rule interpolates the bar toward `min_accept_share` as the
    soft horizon passes, which walks it DOWN from a high bar and UP from a low
    one -- and a low bar is what every impatient player has. At delta 0.9 ours
    climbed 19.5% -> 35% while each round burned 10% of the prize, so the rule
    meant to stop us grinding was the thing doing the grinding.
    """

    def _standing(self, share, round_, delta=0.9, pot=1_000_000):
        return bargaining_game(
            action_type="decision", slot="player_2", money=pot, round_=round_,
            max_rounds=None, delta_2=delta, complete_information=False,
            last_offer={"player_1_gain": pot * (1 - share), "player_2_gain": pot * share,
                        "proposer": "player_1", "round": round_},
        )

    def test_a_standing_offer_does_not_get_harder_to_accept_over_time(self):
        # 25% is above the delta-0.9 bar of 19.5% and below `min_accept_share`,
        # so this is exactly the band the old interpolation walked away from.
        for round_ in (1, 5, 15, 40, 69):
            assert play(self._standing(0.25, round_))["decision"] == "accept", round_

    def test_a_patient_player_holds_one_bar_and_never_raises_it(self):
        # On a free clock the bar no longer walks at all: it sits at
        # `free_clock_accept_floor` until the round-97 collapse. That is the
        # same invariant this class is named for -- never harder to accept as
        # the game goes on -- with the walk flattened rather than reversed,
        # because at delta 1.0 waiting costs nothing so there is nothing to
        # concede to.
        for round_ in (1, 5, 15, 40, 69):
            assert play(self._standing(0.50, round_, delta=1.0))["decision"] == "accept", round_
            assert play(self._standing(0.49, round_, delta=1.0))["decision"] == "reject", round_
        assert play(self._standing(0.49, 97, delta=1.0))["decision"] == "accept"

    def test_a_real_lowball_is_still_refused_however_long_it_stands(self):
        assert play(self._standing(0.05, 60))["decision"] == "reject"


class TestWaitingIsFreeSoWaitLonger:
    """Regression: a 10,000 pot, 0% inflation, no round limit. We took 48%.

    Both hold-out claims were unavailable -- no horizon means no final proposal
    to sit on, and incomplete information means no equilibrium to compute -- so
    a player who paid nothing at all to wait defended the flat evidence bar of
    45%, walked down to 44%, and signed.

    What the record says about that, over 56 post-fix games of exactly this
    shape: rejecting an offer of 40-45% ended at a median 47.2% (+5.2),
    rejecting 45-50% ended at 49.0% (+1.7), rejecting 50-55% gained nothing,
    and NO band produced a single no-deal. Break-even is 50%.
    """

    def _offer(self, share, *, delta=1.0, round_=2, max_rounds=None, ci=False, pot=10_000):
        return bargaining_game(
            action_type="decision", slot="player_1", money=pot, round_=round_,
            max_rounds=max_rounds, delta_1=delta, complete_information=ci,
            last_offer={"player_1_gain": pot * share, "player_2_gain": pot * (1 - share),
                        "proposer": "player_2", "round": round_},
        )

    def test_refuses_the_offer_it_used_to_sign(self):
        assert play(self._offer(0.48))["decision"] == "reject"

    def test_signs_once_the_offer_clears_the_break_even(self):
        assert play(self._offer(0.52))["decision"] == "accept"

    def test_an_inflating_player_is_untouched(self):
        # The floor is priced on delay being free. At 10% a round it is not, and
        # holding out for two more points is how you lose forty.
        for delta in (0.8, 0.9, 0.95):
            assert play(self._offer(0.48, delta=delta))["decision"] == "accept", delta

    def test_a_known_horizon_is_untouched(self):
        # Bounded games already have the endgame seat and the deadline cap; this
        # floor is only for the case where neither exists.
        assert play(self._offer(0.48, max_rounds=12))["decision"] == "accept"

    def test_the_walk_down_still_breaks_a_deadlock(self):
        # The floor must not become the round-99 stalemate it replaced. It does
        # not: the collapse at the real cap still fires, two rounds before the
        # server books the double zero. What changed is only when -- and on a
        # free clock the offer has not lost a cent in the meantime.
        assert play(self._offer(0.48, round_=20))["decision"] == "reject"
        assert play(self._offer(0.48, round_=97))["decision"] == "accept"

    def test_it_is_a_floor_and_never_a_ceiling(self):
        from glee_agent.strategies.bargaining import costless_hold_value
        for delta in (0.8, 0.9, 0.95, 1.0):
            for max_rounds in (None, 12):
                state = self._offer(0.5, delta=delta, max_rounds=max_rounds)["game_state"]
                assert costless_hold_value(state, "player_1") >= 0.0
                combined = max(stonewall_threshold(state, "player_1"),
                               costless_hold_value(state, "player_1"))
                assert combined >= stonewall_threshold(state, "player_1") - 1e-12


class TestSeeingTheirClockMustNotMakeUsWorse:
    """Chunks 9 and 12: complete information COST us 5-6% at delta 0.8.

    0.8 is the bottom of the observed delta grid, so a visible opponent is
    almost always the more patient one. The equilibrium share collapses --
    proposer_share(0.8, 0.95) is 0.208 -- lands on the `never_concede_below`
    clamp, and we open lower than the incomplete-information path, which assumes
    symmetry and floors at 0.556.

    Measured on identical delta and horizon, visible against hidden: -5.7% and
    -5.0% (chunk 9), -6.4% (chunk 12). Every delta at 0.9 and above GAINED from
    the extra information, so the fix is not to ignore it -- it is to stop it
    lowering the floor. Bargaining took zero no-deals across 521 games, so
    asking for more is close to free here.
    """

    def _open(self, d_me, d_them, ci=True, pot=1_000_000, max_rounds=12):
        return play(bargaining_game(slot="player_1", money=pot, round_=1, max_rounds=max_rounds,
                                    delta_1=d_me, delta_2=d_them,
                                    complete_information=ci))["alice_gain"] / pot

    def test_it_does_not_apply_without_a_horizon_to_enforce_it(self):
        """Chunk 13: this helped bounded games and hurt open-ended ones.

        delta 0.8 with their clock visible went 38.0% -> 41.4% bounded, but
        44.4% -> 37.5% open, and the median settle round moved 1 -> 2. The
        accept bar at delta 0.8 is 11.8%, so opening higher pushed them past
        round one and we then signed their counter. A known horizon forces a
        resolution before that cycle can run; an open one does not.
        """
        assert self._open(0.8, 0.95, max_rounds=None) < self._open(0.8, 0.95, max_rounds=12)

    def test_a_patient_opponent_no_longer_lowers_our_opening(self):
        # The regression: these three differed, and the gap was the whole defect.
        assert self._open(0.8, 0.8) == pytest.approx(self._open(0.8, 0.95))
        assert self._open(0.8, 0.8) == pytest.approx(self._open(0.8, 1.0))

    def test_seeing_their_clock_matches_not_seeing_it_at_worst(self):
        for d_me in (0.8, 0.9, 0.95, 1.0):
            for d_them in (0.8, 0.9, 0.95, 1.0):
                seen = self._open(d_me, d_them, ci=True)
                hidden = self._open(d_me, d_me, ci=False)
                assert seen >= hidden - 1e-9, (d_me, d_them, seen, hidden)

    def test_an_impatient_opponent_is_still_exploited(self):
        # The information is still worth having when it favours us -- this must
        # not flatten into "always assume a twin".
        assert self._open(0.9, 0.8) > self._open(0.9, 0.95)
        assert self._open(0.95, 0.8) > self._open(0.95, 1.0)

    def test_the_ceiling_still_holds(self):
        for d_me in (0.8, 0.9, 0.95, 1.0):
            for d_them in (0.8, 0.9, 0.95, 1.0):
                assert self._open(d_me, d_them) <= P.final_round_demand + 1e-9


class TestClosingInsteadOfHaggling:
    """An impatient proposer with no deadline opens at a signable number.

    Measured over 1,469 games: our openings are accepted 4-10% of the time
    whether we ask 0.65 or 0.85, and the field concedes a median +0.0000 per
    round. So the inflated opening buys nothing except the round of inflation
    it takes them to counter -- 281 open-horizon games where we opened ~0.66,
    they countered ~0.44, and we signed that counter one round poorer.
    """

    def _open(self, d_me, *, max_rounds=None, ci=False, d_them=None, pot=1_000_000):
        return play(bargaining_game(
            slot="player_2", money=pot, round_=1, max_rounds=max_rounds,
            delta_1=d_them if d_them is not None else d_me, delta_2=d_me,
            complete_information=ci,
        ))["bob_gain"] / pot

    def test_an_impatient_open_horizon_opens_at_the_closing_share(self):
        for delta in (0.8, 0.9, 0.95):
            assert self._open(delta) == pytest.approx(P.closing_offer_share)

    def test_a_known_deadline_is_left_alone(self):
        # Chunk 13 measured the opposite sign here: raising the bounded opening
        # was worth +3.4 points. Closing must not spend that.
        for delta in (0.8, 0.9, 0.95):
            assert self._open(delta, max_rounds=12) > P.closing_offer_share

    def test_a_patient_proposer_is_left_alone(self):
        # Delay is free at 1.0, so there is no round of inflation to save and
        # the endgame sweep is worth far more than closing early.
        assert self._open(1.0) > P.closing_offer_share

    def test_it_never_undercuts_what_we_would_hold_out_for(self):
        # We are the patient side and can see it: the equilibrium share is real
        # here, and `hold_out_value` has to floor the closing number.
        patient = self._open(0.95, ci=True, d_them=0.8)
        assert patient > P.closing_offer_share

    def test_it_never_offers_below_the_floor_we_defend(self):
        assert self._open(0.5) >= P.never_concede_below

    def test_the_closing_offer_says_why_it_should_be_signed(self, messages_on):
        action = play(bargaining_game(
            slot="player_2", money=1_000_000, round_=1, max_rounds=None,
            delta_1=0.8, delta_2=0.8, complete_information=False,
        ))
        # The number is not what decides these games, so the text has to carry
        # it: an even split, a refusal to improve, and a cost to countering.
        assert "even split" in action["message"]
        assert "not beat it later" in action["message"]
        # Never advertise our own impatience -- it is an invitation to wait.
        assert "inflation" not in action["message"].lower()

    def test_a_bounded_game_keeps_its_ordinary_opening_message(self, messages_on):
        action = play(bargaining_game(
            slot="player_2", money=1_000_000, round_=1, max_rounds=12,
            delta_1=0.8, delta_2=0.8, complete_information=False,
        ))
        assert "even split" not in action["message"]


class TestTheOpenGameBarHasACeiling:
    """`discounted_hold_cap`: stop refusing offers better than the deal we sign.

    Measured over 389 refusals in open games below `costless_delay_delta`:
    refusing an offer at or above 0.425 of the pot returned -0.0464 of pot
    (sigma -9.0), stable in every 0.025 band from 0.375 up and in both seats.

    The live bar only climbs that high in one place, and probing it says exactly
    where: an OPEN game under complete information where we are the patient side,
    so `_continuation_value` hands us the big half. At delta 0.95 against 0.80 it
    demands 0.578, and against 0.90 it demands 0.536 -- both well past the point
    the record says holding out stops paying. Symmetric deltas never get there,
    which is why these fixtures are deliberately lopsided.

    These pin both halves: that it signs what it should, and that it leaves alone
    the regimes where holding out genuinely pays.
    """

    def _decide(self, *, their_offer, d_me=0.95, d_opp=0.80, max_rounds=None,
                round_=3, complete_information=True, slot="player_1"):
        money = 1000
        mine = money * their_offer
        them = "player_2" if slot == "player_1" else "player_1"
        d1, d2 = (d_me, d_opp) if slot == "player_1" else (d_opp, d_me)
        game = bargaining_game(
            action_type="decision", slot=slot, money=money, round_=round_,
            max_rounds=max_rounds, delta_1=d1, delta_2=d2,
            complete_information=complete_information,
            last_offer={f"{slot}_gain": mine, f"{them}_gain": money - mine,
                        "proposer": them, "round": round_},
        )
        return play(game)["decision"]

    def test_the_shipped_default_still_refuses_it(self):
        # Guards the SHIPPED bar: flipping the flag is expected to change this
        # one and nothing in the regimes below it.
        assert self._decide(their_offer=0.47) == "reject"

    def test_an_offer_over_the_cap_is_signed(self, hold_cap_on):
        assert self._decide(their_offer=0.47) == "accept"

    def test_and_so_is_one_the_old_bar_refused_outright(self, hold_cap_on):
        assert self._decide(their_offer=0.52) == "accept"

    def test_an_offer_under_the_cap_is_still_refused(self, hold_cap_on):
        # A ceiling only ever signs what we were about to refuse. It must not
        # turn into a floor that starts signing lowballs.
        assert self._decide(their_offer=0.20) == "reject"

    def test_costless_delay_is_left_alone(self, hold_cap_on):
        # At delta 1.0 every measured band said holding out PAYS (+0.004 to
        # +0.141), which is why `costless_hold_share` raises the bar there.
        assert self._decide(their_offer=0.47, d_me=1.0) == "reject"

    def test_a_bounded_game_is_left_alone(self, hold_cap_on):
        # Bounded games have an endgame seat to play for; the measurement was
        # open games only.
        assert self._decide(their_offer=0.47, max_rounds=12) == "reject"

    def test_it_applies_to_both_seats(self, hold_cap_on):
        for slot in ("player_1", "player_2"):
            assert self._decide(their_offer=0.47, slot=slot) == "accept", slot


class TestTheOpenHorizonIsNotReallyOpen:
    """The server stops open games at round 99 and pays both sides $0.

    It is real -- results carry `round_cap_reached: true` -- and undocumented.
    The agent is never told: `horizon_known` stays false, so `rounds_left` is
    None, `is_final_round` never fires, and the accept bar sits at
    `min_accept_share` right through the last round. Replaying the pre-fix build
    at round 99 it refused 0.34, 0.25 and 0.10 and banked nothing, which is
    strictly dominated. 25 of 3,564 open games in the record ended exactly there.

    This ships ON and has no flag: taking something over nothing at a genuine
    final round cannot be worse.
    """

    def _decide(self, *, their_offer, round_, d=1.0, max_rounds=None, slot="player_1"):
        money = 1000
        mine = money * their_offer
        them = "player_2" if slot == "player_1" else "player_1"
        game = bargaining_game(
            action_type="decision", slot=slot, money=money, round_=round_,
            max_rounds=max_rounds, delta_1=d, delta_2=d, complete_information=True,
            last_offer={f"{slot}_gain": mine, f"{them}_gain": money - mine,
                        "proposer": them, "round": round_},
        )
        return play(game)["decision"]

    def test_at_the_cap_we_take_what_is_on_the_table(self):
        assert self._decide(their_offer=0.10, round_=99) == "accept"

    def test_even_a_token_beats_the_zero_a_cap_pays(self):
        assert self._decide(their_offer=0.02, round_=99) == "accept"

    def test_the_bar_collapses_as_the_cap_comes_into_view(self):
        # Mirrors the bounded endgame: within `endgame_rounds` of the end the
        # bar drops to `endgame_floor`, not all the way to zero.
        assert self._decide(their_offer=0.10, round_=97) == "accept"
        assert self._decide(their_offer=0.02, round_=97) == "reject"

    def test_mid_game_is_untouched(self):
        # Far from the cap the agent should still be holding out normally.
        assert self._decide(their_offer=0.10, round_=40) == "reject"

    def test_a_bounded_game_keeps_its_own_endgame(self):
        # 12-round games have a horizon the agent can see; nothing here applies.
        assert self._decide(their_offer=0.10, round_=6, max_rounds=12) == "reject"


class TestHoldingOutStopsPayingAtTheTop:
    """`costless_hold_cap`: the arm. Ships off.

    At delta 1.0 in an open game, holding out is measurably right for a long
    way -- refusing 0.30-0.40 returns +0.150 of pot, 0.40-0.50 +0.029,
    0.50-0.60 +0.056 -- and then turns over hard: refusing 0.60 or better
    returns -0.3057 over 263 refusals, sigma -9.9, at a median round of 38-57.

    So the cap has to sit ABOVE the range that pays. Getting the level wrong
    converts a measured gain into a measured loss, which is why this is an arm
    and not a default.
    """

    def _decide(self, *, their_offer, d_me=1.0, d_opp=0.8, round_=3,
                max_rounds=None, slot="player_1"):
        money = 1000
        mine = money * their_offer
        them = "player_2" if slot == "player_1" else "player_1"
        d1, d2 = (d_me, d_opp) if slot == "player_1" else (d_opp, d_me)
        game = bargaining_game(
            action_type="decision", slot=slot, money=money, round_=round_,
            max_rounds=max_rounds, delta_1=d1, delta_2=d2, complete_information=True,
            last_offer={f"{slot}_gain": mine, f"{them}_gain": money - mine,
                        "proposer": them, "round": round_},
        )
        return play(game)["decision"]

    def test_the_shipped_default_still_holds_out(self):
        # Guards the SHIPPED default. The equilibrium continuation puts the bar
        # at 0.7275 here, which is what refuses the offers that measured -0.31.
        assert self._decide(their_offer=0.65) == "reject"

    def test_the_arm_signs_an_offer_over_the_cap(self, costless_cap_on):
        assert self._decide(their_offer=0.65) == "accept"

    def test_the_arm_leaves_the_range_that_pays_alone(self, costless_cap_on):
        # Below the cap holding out is worth +0.03 to +0.15 of pot. The arm must
        # not touch that half, or it trades a measured gain for nothing.
        assert self._decide(their_offer=0.45) == "reject"
        assert self._decide(their_offer=0.55) == "reject"

    def test_the_arm_does_not_reach_discounted_games(self, costless_cap_on):
        """delta 0.95 belongs to `discounted_hold_cap`, not to this one.

        Asserted on the cap itself rather than on a decision: the decision there
        also depends on whether `discounted_hold_cap_on` is set, so testing it
        through `play` would pass or fail for reasons that have nothing to do
        with this arm.
        """
        from glee_agent.strategies.bargaining import costless_hold_cap
        state = bargaining_game(
            action_type="decision", slot="player_1", money=1000, round_=3,
            max_rounds=None, delta_1=0.95, delta_2=0.8, complete_information=True,
        )["game_state"]
        assert costless_hold_cap(state, "player_1") == 1.0

    def test_the_arm_does_not_reach_bounded_games(self, costless_cap_on):
        # A known horizon has an endgame seat worth playing for -- the
        # measurement was open games only.
        assert self._decide(their_offer=0.65, round_=3, max_rounds=12) == "reject"


class TestASweeperStillHasAClock:
    """Regression: game 12416c63. Pot 1,000,000, our inflation 0%, his 5%,
    twelve rounds, the last proposal his.

    He offered 199,167/800,833 on rounds 2, 4 and 6 without moving a cent. We
    answered 850,000, then 824,698, then 802,270 -- leaving him 150,000 to
    197,730 against a standing demand of 800,833 -- and then took his 199,167.
    Three of our turns were spent on asks that could never have been signed.

    Repeating his demand costs him a round of his own 5%, so 800,833 next round
    is worth 760,791 now: anything above that beats waiting, for him, whatever
    he thinks of us. That price leaves us 231,601.

    The patience half is deliberately NOT the fix. He holds the last word, so
    our equilibrium share falls as the clock runs -- 0.2649 at round 1, 0.1426 at
    round 6, 0.0500 at round 11 -- and simply waiting makes this worse. Refusing
    is only correct because there is a specific better ask to make.
    """

    POT = 1_000_000.0

    def _state(self, round_, phase, history_rounds):
        history = []
        ours = {3: 824_698.0, 5: 802_270.0, 1: 850_000.0}
        for r in range(1, history_rounds + 1):
            if r % 2:
                gain = ours.get(r, 800_000.0)
                history.append({"round": r, "proposer": "player_1", "decision": "reject",
                                "offer": {"player_1_gain": gain, "player_2_gain": self.POT - gain,
                                          "proposer": "player_1", "round": r}})
            else:
                history.append({"round": r, "proposer": "player_2", "decision": "reject",
                                "offer": {"player_1_gain": 199_167.0, "player_2_gain": 800_833.0,
                                          "proposer": "player_2", "round": r}})
        return {
            "round": round_, "max_rounds": 12, "horizon_known": True, "phase": phase,
            "money_to_divide": self.POT, "delta_1": 1.0, "delta_2": 0.95,
            "complete_information": True, "messages_allowed": False,
            "current_player": "player_1", "proposer": "player_2" if phase == "decision" else "player_1",
            "history": history,
            "last_offer": {"player_1_gain": 199_167.0, "player_2_gain": 800_833.0,
                           "proposer": "player_2", "round": round_ if phase == "decision" else round_ - 1},
        }

    def _game(self, round_, phase, history_rounds):
        return {"game_state": self._state(round_, phase, history_rounds),
                "your_player": "player_1", "game_family": "bargaining",
                "valid_actions": {"type": phase}}

    def test_the_shipped_default_banks_his_crumb_at_round_six(self):
        assert play(self._game(6, "decision", 5))["decision"] == "accept"

    def test_the_arm_declines_it(self, sweep_counter):
        assert play(self._game(6, "decision", 5))["decision"] == "reject"

    def test_and_answers_with_a_price_his_own_clock_signs(self, sweep_counter):
        offer = play(self._game(7, "offer", 6))
        # 800,833 next round is worth 760,791 to him now.
        assert offer["bob_gain"] > 800_833.0 * 0.95
        assert offer["alice_gain"] > 199_167.0

    def test_the_default_answers_with_an_ask_he_cannot_take(self):
        offer = play(self._game(7, "offer", 6))
        assert offer["bob_gain"] < 800_833.0 * 0.95

    def test_it_never_bids_below_what_he_already_offered_us(self, sweep_counter):
        offer = play(self._game(7, "offer", 6))
        assert offer["alice_gain"] >= 199_167.0

    def test_it_stays_out_of_games_where_waiting_costs_us(self, sweep_counter):
        # Same shape, but our own inflation is 10% a round: the crumb in hand is
        # worth more than a better number two rounds away, so take it.
        game = self._game(6, "decision", 5)
        game["game_state"]["delta_1"] = 0.9
        assert play(game)["decision"] == "accept"

    def test_it_stays_out_when_his_clock_does_not_burn(self, sweep_counter):
        # He loses nothing by repeating himself, so there is no price to name.
        game = self._game(6, "decision", 5)
        game["game_state"]["delta_2"] = 1.0
        assert play(game)["decision"] == "accept"

    def test_it_signs_once_the_rounds_run_out(self, sweep_counter):
        # Round 10 of 12: refusing stops being free, so bank what is there.
        assert play(self._game(10, "decision", 9))["decision"] == "accept"


class TestARejectionIsChargedWhatItCosts:
    """The bar we defend has to be a bar the clock can pay for.

    Measured over 23,617 offers we actually refused -- each an exact paired
    counterfactual, since accepting is unilateral and terminal -- refusing stops
    paying well below where our bar sits. At delta 0.95 in an open complete-
    information game the break-even is 0.20 and the shipped bar is 0.62.

    The mechanism is our own inflation, not the opponent's stubbornness: the
    NOMINAL share we negotiate is right (0.667 against an SPE of 0.673), but we
    take six rounds to reach it and lose 23% of it on the way.
    """

    def _state(self, d_me, d_them, mx, round_=1, offer=0.30):
        st = {"round": round_, "horizon_known": mx is not None, "phase": "decision",
              "money_to_divide": 1.0, "complete_information": True,
              "messages_allowed": False, "current_player": "player_1",
              "proposer": "player_2", "history": [],
              "delta_1": d_me, "delta_2": d_them,
              "last_offer": {"player_1_gain": offer, "player_2_gain": 1 - offer,
                             "proposer": "player_2", "round": round_}}
        if mx is not None:
            st["max_rounds"] = mx
        return st

    def _bar(self, st):
        from glee_agent.strategies import bargaining as B
        return max(B.stonewall_threshold(st, "player_1"),
                   B.hold_out_value(st, "player_1") * B.P.accept_slack,
                   B.costless_hold_value(st, "player_1"))

    def test_the_flag_ships_off(self):
        from glee_agent import params
        assert params.BARGAINING.settle_early_on is False

    def test_the_accessors_track_the_flag(self, settle_early):
        from glee_agent.strategies import bargaining as B
        assert B.settle_rounds() == 9
        assert B.counter_share() == 0.25
        assert B.floor_accept_share(self._state(0.95, 0.90, None), "player_1") == 0.50

    def test_the_shipped_bar_sits_far_above_the_break_even(self):
        # 0.95 vs 0.90, open, complete: the record says refusing 0.20+ loses.
        assert self._bar(self._state(0.95, 0.90, None)) > 0.55

    def test_the_arm_brings_it_down(self, settle_early):
        assert self._bar(self._state(0.95, 0.90, None)) < 0.50

    def test_it_never_raises_the_bar_where_waiting_is_free(self, settle_early):
        # At delta 1.0 holding out genuinely pays and the record agrees, so the
        # arm must not drag that bar down with the rest.
        assert self._bar(self._state(1.00, 0.80, 12)) > 0.80

    def test_it_still_signs_at_the_endgame(self, settle_early):
        st = self._state(0.90, 0.90, 12, round_=12, offer=0.10)
        assert play({"game_state": st, "your_player": "player_1",
                     "game_family": "bargaining",
                     "valid_actions": {"type": "decision"}})["decision"] == "accept"

    def test_it_opens_lower_because_haggling_is_priced_higher(self, settle_early):
        # A real pot: `split_exactly` works in whole units, so a pot of 1.0
        # rounds any demand to the whole thing and measures nothing.
        st = dict(self._state(0.90, 0.90, 12), phase="offer", money_to_divide=1_000_000.0,
                  proposer="player_1", current_player="player_1")
        st["last_offer"] = None
        ask = play({"game_state": st, "your_player": "player_1",
                    "game_family": "bargaining",
                    "valid_actions": {"type": "offer"}})["alice_gain"] / 1_000_000.0
        assert ask < 0.76   # the shipped schedule opens this cell at 0.7623


class TestAFreeClockIsNotADeadline:
    """Regression: pot 1,000,000, our inflation 0%, hidden, no round limit.

    We opened 850,000, they countered 420,000, we asked 761,444, and we signed
    their 500,000 at round 4 -- of a game that runs to 99, in which waiting cost
    us nothing at all.

    Two faults, and the second is the larger. `costless_hold_share` is exactly
    0.50, so an even split meets the bar rather than missing it. And the
    open-game walk-down is keyed to `unbounded_soft_horizon` = 12 while the game
    ends at `open_horizon_cap` = 99, so the bar is spent by round 20 and then
    sits at the floor for seventy-nine rounds. The walk exists to price time
    pressure; at delta 1.0 there is none until the cap.
    """

    def _game(self, round_, offer=0.50, delta=1.0, phase="decision"):
        st = {"round": round_, "horizon_known": False, "phase": phase,
              "money_to_divide": 1_000_000.0, "complete_information": False,
              "messages_allowed": False, "current_player": "player_1",
              "proposer": "player_2", "history": [], "delta_1": delta,
              "last_offer": {"player_1_gain": offer * 1e6,
                             "player_2_gain": (1 - offer) * 1e6,
                             "proposer": "player_2", "round": round_}}
        return {"game_state": st, "your_player": "player_1",
                "game_family": "bargaining", "valid_actions": {"type": phase}}

    def test_the_flag_ships_off(self):
        from glee_agent import params
        assert params.BARGAINING.costless_open_holds_on is False

    def test_the_shipped_default_signs_an_even_split_immediately(self):
        assert play(self._game(4))["decision"] == "accept"

    def test_and_keeps_signing_it_all_the_way_down_the_game(self):
        # The fault this class exists for: the bar is spent long before the cap.
        for rd in (10, 20, 40, 60, 80):
            assert play(self._game(rd))["decision"] == "accept", rd

    def test_the_arm_refuses_it_while_refusing_is_free(self, hold_open):
        for rd in (1, 4, 10, 20):
            assert play(self._game(rd))["decision"] == "reject", rd

    def test_the_arm_still_relaxes_as_the_real_cap_approaches(self, hold_open):
        assert play(self._game(97))["decision"] == "accept"

    def test_and_takes_anything_at_the_cap_rather_than_book_a_zero(self, hold_open):
        assert play(self._game(98, offer=0.12))["decision"] == "accept"

    def test_it_does_not_touch_a_player_whose_clock_runs(self, hold_open):
        # delta 0.90: waiting is expensive, the walk-down is priced correctly,
        # and this arm must leave it alone.
        assert play(self._game(4, offer=0.50, delta=0.90))["decision"] == "accept"

    def test_it_stays_under_the_measured_refusal_ceiling(self):
        # Refusing 0.60+ at delta 1.0 returned -0.3057 of pot over 263 real
        # refusals (sigma -9.9). Whatever we hold for has to sit below that.
        from glee_agent import params
        assert params.BARGAINING.costless_open_share < params.BARGAINING.costless_hold_cap


class TestTheEndgameSeatIsPricedOnce:
    """At delta 0.95 over twelve rounds with the last proposal ours, riding to
    the end and demanding `final_round_demand` returns 0.97 * 0.95^11 = 0.5517
    of the pot in round-one money -- IF the responder signs.

    They sign 1,301 times out of 1,415 (91.9%). The other 114 took the $0, which
    was strictly worse for them, and asking less does not help: 90.1% sign an ask
    of 0.9 against 92.1% for 1.0. So the seat returns 0.5070, not 0.5517.

    It used to be shaved twice -- once by `accept_slack`, which prices "they may
    never concede" and so does not apply to a seat nobody can take from us, and
    not at all by the refusal risk that does apply. Now it is priced once, by the
    thing that actually happens.
    """

    def _bar(self, round_, delta=0.95, mx=12):
        from glee_agent.strategies import bargaining as B
        from glee_agent.params import BARGAINING as P
        st = {"round": round_, "max_rounds": mx, "horizon_known": True,
              "phase": "decision", "money_to_divide": 1.0,
              "complete_information": True, "messages_allowed": False,
              "current_player": "player_2", "proposer": "player_1", "history": [],
              "delta_2": delta, "delta_1": 0.90,
              "last_offer": {"player_2_gain": 0.35, "player_1_gain": 0.65,
                             "proposer": "player_1", "round": round_}}
        return max(B.stonewall_threshold(st, "player_2"),
                   B.hold_out_value(st, "player_2") * P.accept_slack,
                   B.endgame_hold_value(st, "player_2"),
                   B.costless_hold_value(st, "player_2"))

    def test_the_seat_is_worth_its_measured_return(self):
        from glee_agent.params import BARGAINING as P
        seat = P.final_round_demand * P.endgame_sign_rate * 0.95 ** 11
        assert abs(seat - 0.5070) < 0.001

    def test_the_bar_holds_that_value_across_the_game(self):
        # In round-one money the floor is flat: waiting is already priced into it.
        for rd in (5, 7, 9, 11):
            assert abs(self._bar(rd) * 0.95 ** (rd - 1) - 0.5070) < 0.002, rd

    def test_it_is_not_shaved_twice(self):
        from glee_agent.params import BARGAINING as P
        # Applying accept_slack on top would land at 0.4918.
        assert self._bar(9) * 0.95 ** 8 > 0.5070 * P.accept_slack + 0.005

    def test_a_seat_we_do_not_hold_is_worth_nothing(self):
        # player_1 opens, so player_1 proposes on odd rounds and player_2 on even
        # ones. Over twelve rounds the last proposal is therefore player_2's, and
        # player_1 is deciding on an even round -- get that parity wrong and the
        # state describes a game that cannot happen.
        from glee_agent.strategies import bargaining as B
        st = {"round": 4, "max_rounds": 12, "horizon_known": True,
              "phase": "decision", "money_to_divide": 1.0,
              "complete_information": True, "messages_allowed": False,
              "current_player": "player_1", "proposer": "player_2", "history": [],
              "delta_1": 0.95, "delta_2": 0.90,
              "last_offer": {"player_1_gain": 0.35, "player_2_gain": 0.65,
                             "proposer": "player_2", "round": 4}}
        assert B._final_round_is_ours(st, "player_1") is False
        assert B.endgame_hold_value(st, "player_1") == 0.0


class TestTheOpeningAskGrid:
    """Sampling the opening instead of computing it.

    As player_1 we sit at percentile 0.411 against 0.563 as player_2 over 23,069
    games, and it is not an information problem -- seeing the opponent's discount
    factor moves us 0.418 against 0.409 blind. With a KNOWN horizon we open at
    0.780 and it is signed at round 1 in 1.8% of games; on the open horizon we
    open at 0.631, it clears 45.0%, and we bank 0.465 against 0.384.

    That comparison cannot be de-confounded from the logs -- inside the known
    horizon our round-1 ask has sd 0.017 and has never once been below 0.78 in
    23,069 games. So this samples the opening rather than guessing a better one.
    """

    def _open(self, **kw):
        kw.setdefault("action_type", "offer")
        kw.setdefault("slot", "player_1")
        kw.setdefault("round_", 1)
        kw.setdefault("money", 1000)
        return bargaining_game(**kw)

    def _share(self, game):
        out = play(game)
        return out["alice_gain"] / 1000.0

    def test_the_arm_ships_off(self):
        assert P.opening_ask_grid is False
        assert P.opening_grid[-1] == -1.0
        assert P.opening_grid_known_horizon_only is True

    def test_the_shipped_opening_is_the_one_nobody_signs(self):
        # Not a preference: the number itself. 0.78+ on the known horizon.
        assert self._share(self._open(max_rounds=12, delta_1=0.95, delta_2=0.8)) >= 0.78

    def test_the_grid_moves_the_opening(self, opening_ask_grid):
        # Different games draw different entries, so across ids the opening is
        # no longer a single number.
        seen = set()
        for i in range(40):
            g = self._open(max_rounds=12, delta_1=0.95, delta_2=0.8)
            g["game_id"] = "grid-%d" % i
            seen.add(round(self._share(g), 3))
        assert len(seen) >= 3, seen

    def test_every_draw_is_on_the_grid_or_the_shipped_number(self, opening_ask_grid):
        from glee_agent.params import BARGAINING as BP
        allowed = {round(x, 3) for x in BP.opening_grid if x >= 0}
        for i in range(60):
            g = self._open(max_rounds=12, delta_1=0.95, delta_2=0.8)
            g["game_id"] = "grid-%d" % i
            got = round(self._share(g), 3)
            # Either a grid entry, or the -1.0 sentinel leaving the shipped
            # opening untouched -- which in this cell is 0.78 or above.
            assert got in allowed or got >= 0.78, got

    def test_the_draw_is_stable_for_a_game(self, opening_ask_grid):
        # Seeded from the game id, so replaying a log reproduces the opening.
        g = self._open(max_rounds=12, delta_1=0.95, delta_2=0.8)
        g["game_id"] = "stable-1"
        assert self._share(g) == self._share(g)

    def test_it_leaves_the_open_horizon_alone(self, opening_ask_grid):
        # There the opening already clears 45% of the time and banks 0.465.
        base = []
        for i in range(30):
            g = self._open(max_rounds=None, delta_1=0.95, delta_2=0.8)
            g["game_id"] = "open-%d" % i
            base.append(round(self._share(g), 4))
        assert len(set(base)) == 1, set(base)

    def test_it_only_touches_round_one(self, opening_ask_grid):
        later = []
        for i in range(30):
            g = self._open(max_rounds=12, round_=3, delta_1=0.95, delta_2=0.8)
            g["game_id"] = "later-%d" % i
            later.append(round(self._share(g), 4))
        assert len(set(later)) == 1, set(later)

    def test_it_never_offers_the_opponent_nothing(self, opening_ask_grid):
        for i in range(40):
            g = self._open(max_rounds=12, delta_1=1.0, delta_2=0.8)
            g["game_id"] = "floor-%d" % i
            out = play(g)
            assert out["bob_gain"] > 0
