"""Count negotiation walk-aways in untradable seats from a slot's turn logs.

Usage: python walkaway.py LOG_DIR [FIRST_DAY LAST_DAY]
       python walkaway.py logs 20260826 20260830

An untradable seat is defined exactly as in
glee_agent/strategies/negotiation.py::_untradable_seat: a seller on the top rung
or a buyer on the bottom rung of the shared value pool, which the agent can see
from its own value alone. Each game is classified as
  walked            - the agent took a walk-away decision,
  no_decision_turn  - the game ended before the agent had a decision turn,
  accepted          - the agent accepted an offer,
  decision_no_walk  - the agent had a decision turn and did not walk.
Games are assigned to the earliest log day they appear in.
"""
import collections
import json
import sys
from pathlib import Path

SHAPE = (80, 100, 120, 150)
SCALES = (1, 100, 10000)


def rung(value):
    for scale in SCALES:
        for index, base in enumerate(SHAPE):
            if abs(value - base * scale) < 1e-6:
                return index
    return None


def main():
    log_dir = Path(sys.argv[1])
    first, last = (sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ("00000000", "99999999")
    games = collections.defaultdict(lambda: {"untradable": None, "decisions": [], "day": "99999999"})
    for path in sorted(log_dir.glob("turns-*.jsonl")):
        day = path.stem.split("-")[1]
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if '"negotiation"' not in line:
                    continue
                turn = json.loads(line)
                if turn.get("game_family") != "negotiation":
                    continue
                game = games[turn["game_id"]]
                game["day"] = min(game["day"], day)
                state, me = turn["state"], turn["your_player"]
                role, value = state.get(f"{me}_role"), state.get(f"{me}_value")
                if role and value is not None and rung(float(value)) is not None:
                    index = rung(float(value))
                    game["untradable"] = (role == "seller" and index == len(SHAPE) - 1) or \
                                         (role == "buyer" and index == 0)
                if turn.get("action_type") == "decision":
                    game["decisions"].append(str(turn["action"].get("decision", "")).lower())
    counts = collections.Counter()
    for game in games.values():
        if not game["untradable"] or not (first <= game["day"] <= last):
            continue
        decisions = game["decisions"]
        if not decisions:
            counts["no_decision_turn"] += 1
        elif any("walk" in d for d in decisions):
            counts["walked"] += 1
        elif any("accept" in d for d in decisions):
            counts["accepted"] += 1
        else:
            counts["decision_no_walk"] += 1
    total = sum(counts.values())
    print(f"untradable games {total} ({first}..{last})")
    for key in ("walked", "no_decision_turn", "accepted", "decision_no_walk"):
        share = 100 * counts[key] / total if total else 0.0
        print(f"  {key:17s} {counts[key]:6d}  {share:5.1f}%")


if __name__ == "__main__":
    main()
