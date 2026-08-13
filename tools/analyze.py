"""Post-mortem over played games: where the payoff went, and what cost us.

    python tools/analyze.py                # analyse every game in logs/
    python tools/analyze.py --family bargaining
    python tools/analyze.py --refresh      # re-fetch results, ignoring the cache

Outcomes come from the API and are cached in `logs/results-cache.json`, because
the rate limit is 60 requests/minute per agent and a season's worth of games
would otherwise be re-fetched on every run.

The scoring rule is a percentile against the field on the SAME configuration in
the SAME role, so raw payoffs across games are not comparable and this tool
never averages them. It reports what IS comparable: the fraction of the pot we
took, whether a deal happened at all, and how much our own inflation cost us
between the offer we rejected and the one we signed.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from glee_agent import config  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CACHE = Path(config.LOG_DIR) / "results-cache.json"


# --------------------------------------------------------------------------
# loading


def turn_rows() -> list[dict]:
    rows = []
    for path in sorted(Path(config.LOG_DIR).glob("turns-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def games_since(since: str | None) -> list[str]:
    """Game ids in first-seen order, optionally only those started after `since`.

    A tuning run is only evidence about the code that played it, so comparing a
    new batch against games played by the old strategies is worse than useless.
    `since` is matched against each game's FIRST logged turn, so a game already
    in flight when the cutoff passed stays with the batch it belongs to.
    """
    first_seen: dict[str, str] = {}
    for row in turn_rows():
        first_seen.setdefault(row["game_id"], row.get("ts", ""))
    if since is None:
        return list(first_seen)
    return [game_id for game_id, ts in first_seen.items() if ts >= since]


def load_games(refresh: bool, since: str | None = None) -> dict[str, dict]:
    """{game_id: full game payload}, cached. Only completed games are cached."""
    cache = {}
    if CACHE.exists() and not refresh:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))

    wanted = games_since(since)
    missing = [g for g in wanted if g not in cache]
    if missing:
        from glee_sdk import GleeClient

        client = GleeClient(api_key=config.api_key())
        print(f"fetching {len(missing)} games not in cache...", file=sys.stderr)
        for game_id in missing:
            try:
                game = client.game_state(game_id)
            except Exception as error:
                print(f"  {game_id[:8]}: {error}", file=sys.stderr)
                continue
            # An active game's result is not final -- do not cache it.
            if game.get("status") == "active":
                continue
            cache[game_id] = game
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return {g: cache[g] for g in wanted if g in cache}


def _slot(game: dict) -> tuple[str, str]:
    us = game.get("your_player", "player_1")
    return us, "player_2" if us == "player_1" else "player_1"


def _payoffs(game: dict) -> tuple[float, float]:
    us, them = _slot(game)
    result = game.get("result") or {}
    return float(result.get(f"{us}_payoff", 0) or 0), float(result.get(f"{them}_payoff", 0) or 0)


# --------------------------------------------------------------------------
# per-family analysis


def analyse_bargaining(games: list[dict]) -> list[str]:
    notes = []
    shares, rounds, decay_losses, missed = [], [], [], []
    no_deals = 0

    for game in games:
        state = game.get("game_state") or {}
        result = game.get("result") or {}
        us, them = _slot(game)
        ours, theirs = _payoffs(game)
        pot = float(state.get("money_to_divide") or 0)
        if result.get("outcome") == "no_deal" or (ours == 0 and theirs == 0):
            no_deals += 1
            continue
        if not pot:
            continue

        nominal = float(result.get(f"agreed_{us}_gain", ours) or ours)
        shares.append(nominal / pot)
        agreed_round = int(result.get("agreed_round") or 1)
        rounds.append(agreed_round)

        # What our own inflation cost between the nominal split and the payout.
        if nominal > 0 and ours < nominal:
            decay_losses.append((nominal - ours, nominal, agreed_round, game["game_id"]))

        # The counterfactual that matters: the best offer they made us, valued at
        # the round it ARRIVED. Comparing an undiscounted offer against our
        # discounted payout is not a like-for-like comparison -- an offer first
        # made on round 2 was never available to us at its face value, and
        # accepting it on the spot still costs a round of inflation. Only a
        # genuinely better alternative counts as money we left behind.
        delta_me = state.get("delta_1" if us == "player_1" else "delta_2")
        delta_me = 1.0 if delta_me is None else float(delta_me)
        best_available, best_face, best_round = None, None, None
        for entry in state.get("history") or []:
            offer = entry.get("offer") or {}
            if entry.get("proposer") != them:
                continue
            face = offer.get(f"{us}_gain")
            if face is None:
                continue
            arrived = int(entry.get("round") or 1)
            value = float(face) * (delta_me ** max(0, arrived - 1))
            if best_available is None or value > best_available:
                best_available, best_face, best_round = value, float(face), arrived
        if best_available is not None and best_available > ours + 1e-6:
            missed.append((best_available - ours, best_face, best_round, ours, game["game_id"]))

    if shares:
        notes.append(f"  deals: {len(shares)}   no-deals: {no_deals}")
        notes.append(
            f"  nominal share of pot: median {statistics.median(shares):.1%}"
            f"  min {min(shares):.1%}  max {max(shares):.1%}"
        )
        notes.append(f"  settled on round: median {statistics.median(rounds):.0f}  max {max(rounds)}")
    if decay_losses:
        total = sum(d[0] / d[1] for d in decay_losses) / len(decay_losses)
        worst = max(decay_losses)
        notes.append(f"  INFLATION COST: mean {total:.1%} of the nominal split lost to delay")
        notes.append(
            f"    worst: {worst[3][:8]} lost {worst[0]:,.0f} of {worst[1]:,.0f}"
            f" nominal, settled round {worst[2]}"
        )
    if missed:
        missed.sort(reverse=True)
        total = sum(m[0] for m in missed)
        notes.append(
            f"  HELD OUT AND LOST on {len(missed)} game(s) -- an offer they made,"
            f" valued at the round it arrived, beat our payout. Total {total:,.0f}:"
        )
        for gap, face, arrived, got, game_id in missed[:6]:
            notes.append(
                f"    {game_id[:8]}: {face:,.0f} available round {arrived},"
                f" banked {got:,.0f}  (-{gap:,.0f})"
            )
    return notes


def analyse_negotiation(games: list[dict]) -> list[str]:
    notes = []
    no_deals, deals, margins = [], 0, []

    for game in games:
        state = game.get("game_state") or {}
        result = game.get("result") or {}
        us, _ = _slot(game)
        ours, _theirs = _payoffs(game)
        role = state.get(f"{us}_role", "?")
        outcome = result.get("outcome")

        if outcome == "no_deal" or ours == 0:
            history = state.get("history") or []
            # Was a profitable deal on the table? Only THEIR offers count -- our
            # own ask sitting unaccepted is not a deal we passed up.
            them = "player_2" if us == "player_1" else "player_1"
            best = None
            my_value = state.get(f"{us}_value")
            for entry in history:
                offer = entry.get("offer") or {}
                if offer.get("from_player") != them:
                    continue
                price = offer.get("price")
                if price is None or my_value is None:
                    continue
                profit = float(price) - float(my_value) if role == "seller" else float(my_value) - float(price)
                if best is None or profit > best:
                    best = profit
            horizon = state.get("max_rounds")
            label = f"{int(horizon)}-round" if horizon else "open-ended"
            no_deals.append((game["game_id"], role, label, best))
            continue

        deals += 1
        margins.append(ours)

    if deals:
        notes.append(f"  deals: {deals}   no-deals: {len(no_deals)}")
        notes.append(f"  profit: median {statistics.median(margins):,.2f}")
    if no_deals:
        notes.append(f"  NO-DEALS ({len(no_deals)}) -- each scores at the bottom of the percentile scale:")
        for game_id, role, label, best in no_deals:
            if best is None:
                verdict = "  (they never made us an offer)"
            elif best > 0:
                verdict = f"  REFUSED a profit of {best:,.2f} they actually offered"
            else:
                verdict = f"  (their best offer lost us {abs(best):,.2f} -- right to refuse)"
            notes.append(f"    {game_id[:8]}  as {role}, {label}{verdict}")
    return notes


def analyse_persuasion(games: list[dict]) -> list[str]:
    notes = []
    as_seller, as_buyer = [], []

    for game in games:
        state = game.get("game_state") or {}
        result = game.get("result") or {}
        us, _ = _slot(game)
        ours, theirs = _payoffs(game)
        role = state.get(f"{us}_role", "seller" if us == "player_1" else "buyer")
        rounds_total = int(result.get("rounds_total") or state.get("total_rounds") or 0)
        bought = int(result.get("rounds_bought") or 0)
        entry = (game["game_id"], ours, theirs, bought, rounds_total, result)
        (as_seller if role == "seller" else as_buyer).append(entry)

    if as_seller:
        rates = [b / t for _, _, _, b, t, _ in as_seller if t]
        notes.append(f"  as SELLER: {len(as_seller)} games, buyer bought {statistics.median(rates):.0%} of rounds (median)")
        cold = [e for e in as_seller if e[4] and e[3] / e[4] < 0.5]
        for game_id, ours, theirs, bought, total, _ in cold:
            notes.append(f"    {game_id[:8]}: only {bought}/{total} bought -- buyer stopped believing us")
    if as_buyer:
        rates = [b / t for _, _, _, b, t, _ in as_buyer if t]
        notes.append(f"  as BUYER: {len(as_buyer)} games, we bought {statistics.median(rates):.0%} of rounds (median)")
        for game_id, ours, theirs, bought, total, result in as_buyer:
            lows = result.get("bought_low")
            highs = result.get("bought_high")
            if lows is not None and highs is not None and bought and lows > highs:
                notes.append(
                    f"    {game_id[:8]}: bought {lows} low vs {highs} high -- we were being farmed"
                )
    return notes


# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--family", choices=("bargaining", "negotiation", "persuasion"))
    parser.add_argument("--refresh", action="store_true", help="Ignore the results cache.")
    parser.add_argument(
        "--since",
        help="Only games whose first turn is at or after this UTC ISO timestamp, "
             "e.g. 2026-08-12T23:10:00. Use it to score one tuning run on its own.",
    )
    args = parser.parse_args(argv)

    games = load_games(args.refresh, args.since)
    if not games:
        print("No completed games found. Run main.py first.")
        return 1

    by_family: dict[str, list[dict]] = defaultdict(list)
    for game in games.values():
        by_family[game.get("game_family", "?")].append(game)

    print(f"{len(games)} completed games\n")
    handlers = {
        "bargaining": analyse_bargaining,
        "negotiation": analyse_negotiation,
        "persuasion": analyse_persuasion,
    }
    for family, handler in handlers.items():
        if args.family and family != args.family:
            continue
        rows = by_family.get(family, [])
        if not rows:
            continue
        print(f"{family.upper()}  ({len(rows)} games)")
        wins = sum(1 for g in rows if _payoffs(g)[0] > _payoffs(g)[1])
        print(f"  out-earned the opponent in {wins}/{len(rows)}")
        for line in handler(rows):
            print(line)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
