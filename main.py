"""Run the agent against the GLEE Competition platform.

    python main.py                          # all three families, until stopped
    python main.py --families bargaining    # one family
    python main.py --concurrency 8 --max-games 50

Stop with Ctrl-C: the queue is left explicitly on the way out. A queue entry we
abandon still gets matched, and that game times out and dents the rating.
"""

from __future__ import annotations

import argparse
import logging
import sys

from glee_agent import config, gamelog
from glee_agent.dispatcher import play

log = logging.getLogger("glee")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play the GLEE Competition.")
    parser.add_argument(
        "--families",
        nargs="+",
        choices=config.GAME_FAMILIES,
        default=list(config.GAME_FAMILIES),
        help="Game families to queue for (default: all three).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=6,
        help="Games in flight at once, across all families (default: 6).",
    )
    parser.add_argument(
        "--max-games",
        type=int,
        default=None,
        help="Play about this many games, then stop (overshoot bounded by one slice).",
    )
    parser.add_argument(
        "--max-time",
        type=float,
        default=None,
        help="Seconds to keep starting new games for. In-flight games still finish.",
    )
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Seconds between polls.")
    parser.add_argument("--log-level", default="INFO", help="DEBUG, INFO, WARNING, ...")
    return parser.parse_args(argv)


def play_exactly(client, strategy, *, families, target, concurrency, poll_interval,
                 slice_seconds=180.0):
    """Play about `target` games and stop, rather than four times that many.

    `run(max_games=N)` counts games as they COMPLETE, and its counter only
    advances for games that end on our own move -- one the opponent closes never
    increments it. So the cap fires late while the top-up keeps queueing: asking
    for 60 negotiation games started 119 of them. Equal-sized batches are the
    whole basis of comparing one tuning change against another, so we count
    games ourselves, from the dispatcher, where every game is seen exactly once.

    Stopping is the hard part, because `run()` has exactly two ways to return:
    a `max_games` or `max_time` limit is reached, at which point it leaves the
    queue and drains the games already in flight. There is no third one worth
    using -- `requeue=False` does not end the run, it only stops the top-up, so
    the loop polls an empty queue forever (observed: three games, then 74 idle
    minutes). Raising out of the strategy does escape, but it abandons the
    in-flight games into turn timeouts, and three of those buys a 30-minute
    crash-loop ban.

    So the run is cut into timed slices. Each `run()` call drains cleanly, we
    check our own count between slices, and the overshoot is bounded by however
    many games start inside one slice rather than being unbounded. The slice
    shrinks as the target approaches, so the last one overshoots least.

    Returns the number of distinct games actually played.
    """
    seen: set[str] = set()

    def counting(game: dict) -> dict:
        seen.add(game.get("game_id"))
        return strategy(game)

    while len(seen) < target:
        before = len(seen)
        remaining = target - len(seen)
        client.run(
            counting,
            game_families=families,
            concurrency=max(1, min(concurrency, remaining)),
            poll_interval=poll_interval,
            # A short slice near the end keeps the last batch from running past
            # the target; a long one early keeps the per-slice drain overhead
            # off the throughput.
            max_time=slice_seconds if remaining > concurrency else max(30.0, slice_seconds / 4),
        )
        if len(seen) == before:
            # A whole slice matched nothing -- an empty queue at this hour, or
            # the competition closed. Stop rather than spin.
            log.warning("No games matched in a full slice; stopping at %d of %d.",
                        len(seen), target)
            break
        log.info("Played %d of %d.", len(seen), target)
    return len(seen)


def _cooldown_resume_at(error) -> float | None:
    """Seconds to wait out an `agent_cooldown`, from the time the server names.

    A 403 on the queue join is not a reason to exit. The SDK joins queues before
    its play loop starts, so letting the error out strands every game we are
    already holding -- and those then time out, which is what earns the ban in
    the first place. Twice now a forced stop has cost us a thirty-minute outage
    that nobody was watching for.
    """
    import datetime as _dt
    import re as _re
    if getattr(error, "code", None) != "agent_cooldown":
        return None
    match = _re.search(r"(\d{4}-\d{2}-\d{2}T[\d:.]+)Z", str(error))
    if not match:
        return 300.0
    try:
        when = _dt.datetime.fromisoformat(match.group(1)).replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return 300.0
    now = _dt.datetime.now(_dt.timezone.utc)
    return max(0.0, (when - now).total_seconds())


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )

    # Imported here so the strategy modules and their tests stay importable
    # without the SDK installed.
    from glee_sdk import CompetitionClosedError, CompetitionNotOpenError, GleeAPIError, GleeClient

    try:
        key = config.api_key()
    except RuntimeError as error:
        log.error("%s", error)
        return 2

    turn_log = gamelog.configure()
    log.info("Logging turns to %s", turn_log)

    client = GleeClient(api_key=key)
    log.info(
        "Queueing for %s with concurrency %d.", ", ".join(args.families), args.concurrency
    )

    run_kwargs = {
        "game_families": args.families,
        "concurrency": args.concurrency,
        "poll_interval": args.poll_interval,
    }
    if args.max_time is not None:
        run_kwargs["max_time"] = args.max_time

    try:
        if args.max_games is not None:
            played = play_exactly(
                client,
                play,
                families=args.families,
                target=args.max_games,
                concurrency=args.concurrency,
                poll_interval=args.poll_interval,
            )
            log.info("Played %d games (asked for %d).", played, args.max_games)
        else:
            import time as _time
            deadline = None
            if args.max_time is not None:
                deadline = _time.monotonic() + float(args.max_time)
            while True:
                try:
                    client.run(play, **run_kwargs)
                    break
                except GleeAPIError as error:
                    wait = _cooldown_resume_at(error)
                    if wait is None:
                        raise
                    if deadline is not None:
                        left = deadline - _time.monotonic()
                        if left <= wait + 30.0:
                            log.error("Cooldown outlasts the run; stopping.")
                            break
                        run_kwargs["max_time"] = left - wait - 5.0
                    log.warning(
                        "Queue joins paused (agent_cooldown); waiting %.0fs and resuming.",
                        wait + 5.0,
                    )
                    _time.sleep(wait + 5.0)
    except KeyboardInterrupt:
        log.info("Interrupted -- leaving the queue.")
    except CompetitionNotOpenError as error:
        log.error("The competition has not opened yet (opens %s).", getattr(error, "competition_open_at", "?"))
        return 3
    except CompetitionClosedError as error:
        log.error("The competition has closed (closed %s).", getattr(error, "competition_close_at", "?"))
        return 3
    except GleeAPIError as error:
        log.error("API error %s (%s): %s", getattr(error, "status_code", "?"), getattr(error, "code", "?"), error)
        return 4
    finally:
        # `run()` leaves the queue itself, but not on every abrupt exit, and a
        # stale queue entry gets matched into a game we are no longer polling.
        try:
            client.leave_queue()
        except Exception:
            log.debug("leave_queue() failed on shutdown", exc_info=True)

    log.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
