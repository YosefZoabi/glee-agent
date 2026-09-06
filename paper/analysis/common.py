"""Dependency-free helpers for observational diagnostics; no network access."""
import argparse
import json
import math
import statistics
from pathlib import Path


def inputs(description, *names):
    parser = argparse.ArgumentParser(description=description)
    for name in names:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    for name in names:
        path = getattr(args, name)
        if not path.exists():
            parser.error(f"{name} does not exist: {path}")
    return args


def jsonl(path):
    with open(path, encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def mean(values):
    return statistics.mean(values) if values else float("nan")


def correlation(x, y):
    if len(x) < 2 or len(y) != len(x):
        return None
    mx, my = mean(x), mean(y)
    sx = sum((a - mx) ** 2 for a in x)
    sy = sum((b - my) ** 2 for b in y)
    return (sum((a - mx) * (b - my) for a, b in zip(x, y)) /
            math.sqrt(sx * sy)) if sx > 0 and sy > 0 else None


def fit(pairs):
    """OLS; the root is an agent-conditioned zero crossing, not a field median."""
    if len(pairs) < 2:
        return None
    mx, my = mean([p[0] for p in pairs]), mean([p[1] for p in pairs])
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    syy = sum((p[1] - my) ** 2 for p in pairs)
    if sxx <= 0:
        return None
    slope = sxy / sxx
    root = mx - my / slope if abs(slope) > 1e-12 else None
    return {"root": root, "slope": slope,
            "r_squared": sxy * sxy / (sxx * syy) if syy else None}


def bargaining_cells(path):
    """Historical key omits exact horizon; retained for comparison, explicitly disclosed."""
    from collections import defaultdict
    cells = defaultdict(list)
    for row in jsonl(path):
        fields = ("my_share", "rd", "d_us", "d_them", "slot")
        if row.get("fam") != "bargaining" or any(row.get(k) is None for k in fields):
            continue
        key = ("known" if row.get("hk") else "open", row["slot"], row["d_us"], row["d_them"])
        cells[key].append((float(row["my_share"]), float(row["rd"]), row.get("ts") or ""))
    return cells


def discounted_offer(share, round_number, delta):
    if round_number < 1 or not 0 < delta <= 1:
        raise ValueError("Offer round must be positive and delta in (0, 1].")
    return float(share) * float(delta) ** (round_number - 1)


def buyer_seat(game):
    me = game.get("your_player")
    role = (game.get("state") or {}).get("player_1_role")
    return ((me == "player_1" and role == "buyer") or
            (me == "player_2" and role == "seller"))


def history_rows(paths):
    """Deduplicate repeated exports; reject conflicting snapshots rather than double count."""
    rows = {}
    for path in paths:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        entries = value.items() if isinstance(value, dict) else [(None, r) for r in value]
        for fallback_id, row in entries:
            identity = row.get("game_id") or row.get("id") or fallback_id
            if identity is None:
                raise ValueError(f"Missing game_id/id in {path}")
            key = (identity, row.get("your_player"), row.get("your_player_type", "agent"))
            if key in rows and rows[key] != row:
                raise ValueError(f"Conflicting snapshots for {identity}; select one finalized export.")
            rows[key] = row
    return list(rows.values())
