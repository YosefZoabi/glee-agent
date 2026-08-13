"""Read back a game the agent played -- every offer, message, and decision.

    python tools/show_game.py --list          # games we have played, newest last
    python tools/show_game.py c8cf3c48        # full transcript (id prefix is enough)
    python tools/show_game.py --list --live   # only games still in progress

The platform keeps the whole transcript on `GET /api/agent/games/{id}`, including
games still running -- polling this while a game is live is how you watch a deal
happen. Game ids come from the local turn log, so `--list` shows what this
machine has played; a transcript is fetched fresh from the server every time.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from glee_agent import config  # noqa: E402

# Windows consoles default to cp1252, and opponent names contain emoji.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _money(value: object) -> str:
    if not isinstance(value, (int, float)):
        return str(value)
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _played_game_ids() -> list[tuple[str, str]]:
    """(game_id, family) for every game in the turn logs, in first-seen order."""
    seen: dict[str, str] = {}
    for path in sorted(Path(config.LOG_DIR).glob("turns-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            seen.setdefault(row["game_id"], row.get("game_family", "?"))
    return list(seen.items())


def _opponent_name(game: dict) -> str:
    opponent = game.get("opponent") or {}
    if opponent.get("type") == "hidden" or not opponent.get("name"):
        return "hidden"
    return str(opponent["name"])


def _us_them(game: dict) -> tuple[str, str]:
    slot = game.get("your_player", "player_1")
    return slot, "player_2" if slot == "player_1" else "player_1"


def _render_bargaining(history: list[dict], us: str) -> None:
    for entry in history:
        offer = entry.get("offer") or {}
        proposer = entry.get("proposer")
        who = "US " if proposer == us else "THEM"
        ours = offer.get(f"{us}_gain")
        theirs = offer.get(f"{'player_2' if us == 'player_1' else 'player_1'}_gain")
        print(f"  r{entry.get('round'):<3} {who} offers  us {_money(ours)} / them {_money(theirs)}")
        if offer.get("message"):
            print(f"           \"{offer['message']}\"")
        decision = entry.get("decision")
        if decision:
            decider = "THEM" if proposer == us else "US "
            print(f"           -> {decider} {str(decision).upper()}")


def _render_negotiation(history: list[dict], us: str) -> None:
    for entry in history:
        offer = entry.get("offer") or {}
        who = "US " if offer.get("from_player") == us else "THEM"
        print(f"  r{entry.get('round'):<3} {who} asks  {_money(offer.get('price'))}")
        if offer.get("message"):
            print(f"           \"{offer['message']}\"")
        decision = entry.get("decision")
        if decision:
            decider = "US " if entry.get("decided_by") == us else "THEM"
            line = f"           -> {decider} {decision}"
            if entry.get("counteroffer") is not None:
                line += f", counters {_money(entry['counteroffer'])}"
            print(line)


def _render_persuasion(history: list[dict], us: str, roles: dict) -> None:
    seller = "US " if roles.get("seller") == us else "THEM"
    buyer = "US " if roles.get("buyer") == us else "THEM"
    for entry in history:
        quality = entry.get("quality")
        # The buyer only learns quality in rounds they bought.
        shown = quality if quality is not None else "?"
        print(f"  r{entry.get('round'):<3} {seller} (seller) says, product is {shown}:")
        print(f"           \"{entry.get('seller_message')}\"")
        bought = entry.get("bought")
        mark = "BUYS" if bought else "passes"
        print(
            f"           -> {buyer} (buyer) {mark}"
            f"   [seller +{_money(entry.get('seller_payoff'))},"
            f" buyer +{_money(entry.get('buyer_payoff'))}]"
        )


def show(client, game_id: str) -> int:
    game = client.game_state(game_id)
    state = game.get("game_state") or {}
    us, them = _us_them(game)
    result = game.get("result") or {}

    print("=" * 72)
    print(f"{game['game_family']}  {game['game_id']}")
    print(f"we are {us}  vs  {_opponent_name(game)}   [{game.get('status')}]")

    setup = {
        k: state[k]
        for k in (
            "money_to_divide", "max_rounds", "total_rounds", "delta_1", "delta_2",
            "complete_information", "horizon_known", "player_1_value", "player_2_value",
            "product_price", "p", "v", "u",
        )
        if k in state
    }
    if setup:
        print("setup: " + "  ".join(f"{k}={v}" for k, v in setup.items()))
    print("-" * 72)

    history = state.get("history") or []
    if not history:
        print("  (no moves yet)")
    elif game["game_family"] == "bargaining":
        _render_bargaining(history, us)
    elif game["game_family"] == "negotiation":
        _render_negotiation(history, us)
    else:
        roles = {
            state.get("player_1_role", "seller"): "player_1",
            state.get("player_2_role", "buyer"): "player_2",
        }
        _render_persuasion(history, us, roles)

    print("-" * 72)
    if result:
        ours = result.get(f"{us}_payoff")
        theirs = result.get(f"{them}_payoff")
        print(f"OUTCOME: {result.get('outcome')}   us {_money(ours)}  /  them {_money(theirs)}")
        extra = {k: v for k, v in result.items() if not k.endswith("_payoff") and k != "outcome"}
        if extra:
            print("         " + "  ".join(f"{k}={v}" for k, v in extra.items()))
    else:
        print("OUTCOME: still in progress")
    return 0


def listing(client, live_only: bool) -> int:
    rows = _played_game_ids()
    if not rows:
        print("No games in logs/ yet -- run main.py first.")
        return 1
    for game_id, family in rows:
        try:
            game = client.game_state(game_id)
        except Exception as error:  # a game can age out of the API
            print(f"{game_id[:8]}  {family:<11}  <unavailable: {error}>")
            continue
        status = game.get("status")
        if live_only and status != "active":
            continue
        us, them = _us_them(game)
        result = game.get("result") or {}
        outcome = result.get("outcome", "-")
        ours = _money(result.get(f"{us}_payoff", "-"))
        theirs = _money(result.get(f"{them}_payoff", "-"))
        print(
            f"{game_id[:8]}  {family:<11} {us}  vs {_opponent_name(game):<10}"
            f" {status:<10} {outcome:<10} us={ours:>14}  them={theirs:>14}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("game_id", nargs="?", help="Game id, or any unique prefix of one.")
    parser.add_argument("--list", action="store_true", help="List games instead of showing one.")
    parser.add_argument("--live", action="store_true", help="With --list, only games in progress.")
    args = parser.parse_args(argv)

    from glee_sdk import GleeClient

    try:
        client = GleeClient(api_key=config.api_key())
    except RuntimeError as error:
        print(error)
        return 2

    if args.list or not args.game_id:
        return listing(client, args.live)

    matches = [gid for gid, _ in _played_game_ids() if gid.startswith(args.game_id)]
    if not matches:
        matches = [args.game_id]  # not in our logs; try it verbatim
    elif len(matches) > 1:
        print(f"'{args.game_id}' matches {len(matches)} games; use a longer prefix.")
        return 1
    return show(client, matches[0])


if __name__ == "__main__":
    sys.exit(main())
