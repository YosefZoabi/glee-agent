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
        help="Stop starting new games after this many complete. In-flight games still finish.",
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
    if args.max_games is not None:
        run_kwargs["max_games"] = args.max_games
    if args.max_time is not None:
        run_kwargs["max_time"] = args.max_time

    try:
        client.run(play, **run_kwargs)
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
