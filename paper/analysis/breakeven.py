"""Exploratory OLS zero crossings with disclosed IID bootstrap uncertainty.

This does not identify the field median or an equilibrium. Historical grouping
matches horizon type, seat and discount factors, but omits exact round count.
No fitted-root range filter is applied; unstable and nonphysical roots are shown.
"""
import argparse
import json
import random
from pathlib import Path
from common import bargaining_cells, fit, mean


def estimate(pairs, draws=200, rng=None):
    rng = rng or random.Random(7)
    result = fit(pairs)
    if result is None:
        return {"root": None, "status": "constant_payoff", "n": len(pairs)}
    roots = []
    for _ in range(draws):
        boot = fit([pairs[rng.randrange(len(pairs))] for _ in pairs])
        if boot is not None and boot["root"] is not None:
            roots.append(boot["root"])
    roots.sort()
    interval = ([roots[int(.025 * len(roots))], roots[min(len(roots)-1, int(.975 * len(roots)))]]
                if roots else None)
    root = result["root"]
    result.update(n=len(pairs), mean_banked_share=mean([p[0] for p in pairs]),
                  iid_bootstrap_interval=interval, bootstrap_valid=len(roots), bootstrap_draws=draws,
                  root_in_unit_interval=root is not None and 0 <= root <= 1,
                  status="undefined_root" if root is None else "exploratory")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("joined", type=Path)
    parser.add_argument("--min-games", type=int, default=200)
    parser.add_argument("--bootstrap", type=int, default=200)
    parser.add_argument("--output", type=Path, help="Optional new JSON output; no file is overwritten by default.")
    args = parser.parse_args()
    if args.min_games < 2 or args.bootstrap < 1:
        parser.error("Need --min-games >= 2 and --bootstrap >= 1")
    cells = bargaining_cells(args.joined); rng = random.Random(7); rows = []
    for key, values in sorted(cells.items()):
        if len(values) >= args.min_games:
            rows.append({"cell": key, **estimate(values, args.bootstrap, rng)})
    result = {"method": "OLS, IID percentile bootstrap; exploratory, no dependence adjustment",
              "cell_key": ["horizon_type", "seat", "delta_us", "delta_them"],
              "cells_total": len(cells), "cells_below_min_games": len(cells)-len(rows),
              "root_range_filter": None, "rows": rows}
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
