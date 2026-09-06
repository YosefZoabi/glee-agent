"""Descriptive slope and split-half diagnostics, including exclusions.

Neither positive slopes nor split-half correlation validates a recovered field
median. Historical cell keys omit exact known horizon. No cross-seat or
finite-horizon comparison with an infinite-horizon proposer formula is made.
"""
import argparse
import json
import statistics
from pathlib import Path
from common import bargaining_cells, correlation, fit


def stability(cells, min_games=400):
    pairs = []; below = degenerate = missing_time = 0
    for values in cells.values():
        if len(values) < min_games:
            below += 1
            continue
        if any(not row[2] for row in values):
            missing_time += 1
            continue
        ordered = sorted(values, key=lambda row: row[2]); middle = len(ordered)//2
        a, b = fit(ordered[:middle]), fit(ordered[middle:])
        if a is None or b is None or a['root'] is None or b['root'] is None:
            degenerate += 1
            continue
        pairs.append((a['root'], b['root']))
    retained = [(a, b) for a, b in pairs if 0 <= a <= 1.3 and 0 <= b <= 1.3]
    def result(values):
        return {"n_cells": len(values), "r": correlation([v[0] for v in values], [v[1] for v in values])}
    return {"all_defined_roots": result(pairs), "historical_filter_both_roots_in_0_to_1_3": result(retained),
            "excluded_by_historical_root_filter": len(pairs)-len(retained),
            "below_min_games": below, "undefined_half_fit": degenerate, "missing_timestamps": missing_time}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("joined", type=Path)
    args = parser.parse_args()
    cells = bargaining_cells(args.joined)
    fitted = [fit(v) for v in cells.values() if len(v) >= 200]
    valid = [v for v in fitted if v is not None]
    r2s = [v['r_squared'] for v in valid if v['r_squared'] is not None]
    output = {"cells_total": len(cells), "slope_cells": len(valid),
              "constant_payoff_cells": len(fitted)-len(valid),
              "positive_slope_cells": sum(v['slope'] > 0 for v in valid),
              "zero_slope_cells": sum(v['slope'] == 0 for v in valid),
              "negative_slope_cells": sum(v['slope'] < 0 for v in valid),
              "median_r_squared": statistics.median(r2s) if r2s else None,
              "chronological_split_half": stability(cells),
              "limitations": "Observational; historical cell key omits exact horizon; no dependence adjustment."}
    print(json.dumps(output, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
