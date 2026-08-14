"""`--max-games` must mean roughly that, and must terminate.

Two separate failures, both observed live.

The SDK's own cap counts games as they COMPLETE, and its counter only advances
for games ending on our own move -- one the opponent closes never increments it.
So the cap fires late while the queue top-up keeps running: a run asked for 60
negotiation games and started 119. Equal-sized batches are the whole basis of
comparing one tuning change against another.

The first fix for that used `requeue=False`, on the reading that it makes a
`run()` call play only what it queued and return. It does not: it stops the
top-up but never ends the run, so the loop polls an empty queue forever. Live,
that was three games and then 74 idle minutes. `run()` returns on a `max_games`
or `max_time` limit and on nothing else, so the run has to be sliced.
"""

from __future__ import annotations

import pytest

from main import play_exactly


class FakeClient:
    """Stands in for GleeClient.run, which plays for `max_time` and returns.

    Each call hands the strategy one turn per game in the slice, which is all
    `play_exactly` relies on -- it counts distinct game ids, not moves.
    """

    def __init__(self, *, available=1000, per_slice=4):
        self.available = available          # games the queue can still match
        self.per_slice = per_slice          # games that start within one slice
        self.calls = []                     # (concurrency, max_time) per run()
        self._next_id = 0

    def run(self, strategy, *, game_families, concurrency, poll_interval, max_time=None, **kwargs):
        assert max_time is not None, "without a limit, run() never returns"
        assert kwargs.get("requeue", True) is not False, (
            "requeue=False stops the top-up without ending the run"
        )
        self.calls.append((concurrency, max_time))
        batch = min(self.per_slice, self.available)
        self.available -= batch
        for _ in range(batch):
            self._next_id += 1
            strategy({"game_id": f"game-{self._next_id}", "game_family": game_families[0]})


def _strategy(game):
    return {"decision": "accept"}


class TestPlaysAboutTheGamesAsked:
    @pytest.mark.parametrize("target", [60, 1, 7, 100])
    def test_stops_within_one_slice_of_the_target(self, target):
        client = FakeClient(per_slice=4)
        played = play_exactly(
            client, _strategy, families=["negotiation"],
            target=target, concurrency=12, poll_interval=1,
        )
        assert target <= played < target + 4

    def test_terminates_rather_than_polling_forever(self):
        # The bug this replaces did not overshoot -- it hung. Any bound on the
        # call count proves the loop ends.
        client = FakeClient(per_slice=4)
        play_exactly(client, _strategy, families=["bargaining"],
                     target=40, concurrency=12, poll_interval=1)
        assert len(client.calls) <= 12

    def test_every_slice_carries_a_time_limit(self):
        # The only two ways run() returns are max_games and max_time. Omitting
        # both is the hang.
        client = FakeClient()
        play_exactly(client, _strategy, families=["persuasion"],
                     target=20, concurrency=6, poll_interval=1)
        assert all(max_time and max_time > 0 for _, max_time in client.calls)

    def test_the_last_slice_is_shortened_to_overshoot_less(self):
        client = FakeClient(per_slice=1)
        play_exactly(client, _strategy, families=["bargaining"],
                     target=10, concurrency=4, poll_interval=1)
        early = client.calls[0][1]
        last = client.calls[-1][1]
        assert last < early

    def test_never_asks_for_more_concurrency_than_it_still_owes(self):
        client = FakeClient(per_slice=1)
        play_exactly(client, _strategy, families=["bargaining"],
                     target=3, concurrency=10, poll_interval=1)
        assert [c for c, _ in client.calls] == [3, 2, 1]

    def test_a_distinct_game_is_only_counted_once(self):
        # The dispatcher sees many turns per game; the cap counts games.
        client = FakeClient(per_slice=5)
        seen = []

        def repeated(game):
            seen.append(game["game_id"])
            _strategy(game)
            _strategy(game)
            return _strategy(game)

        played = play_exactly(client, repeated, families=["persuasion"],
                              target=5, concurrency=5, poll_interval=1)
        assert played == 5
        assert len(seen) == 5

    def test_stops_instead_of_spinning_when_nothing_matches(self):
        # An empty queue must end the run, not loop forever asking for games.
        client = FakeClient(available=3, per_slice=4)
        played = play_exactly(client, _strategy, families=["persuasion"],
                              target=50, concurrency=10, poll_interval=1)
        assert played == 3
        assert len(client.calls) <= 3

    def test_passes_the_families_through(self):
        client = FakeClient(per_slice=3)
        seen = []
        play_exactly(client, lambda g: seen.append(g["game_family"]),
                     families=["persuasion"], target=3, concurrency=3, poll_interval=1)
        assert set(seen) == {"persuasion"}
