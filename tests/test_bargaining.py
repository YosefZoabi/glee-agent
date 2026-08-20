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

    def test_a_patient_player_still_walks_its_high_bar_down(self):
        # The walk-down itself is not gone: at delta 1.0 the bar starts above
        # `min_accept_share`, and holding it forever is what pays $0.
        early = play(self._standing(0.36, 1, delta=1.0))["decision"]
        late = play(self._standing(0.36, 40, delta=1.0))["decision"]
        assert (early, late) == ("reject", "accept")

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
        # The floor must not become the round-99 stalemate it replaced.
        assert play(self._offer(0.48, round_=20))["decision"] == "accept"

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
