"""IID sensitivity illustration, not a policy-strength sample-size guarantee."""
import argparse
import math
import statistics
from collections import defaultdict
from pathlib import Path
from common import jsonl


def illustrative_n(sigma, effect, standard_errors=3):
    if sigma < 0 or effect <= 0 or standard_errors <= 0:
        raise ValueError("Require sigma >= 0, effect > 0 and standard_errors > 0.")
    return math.ceil(2 * (standard_errors * sigma / effect) ** 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("joined", type=Path)
    parser.add_argument("--effect", type=float, default=0.25)
    args = parser.parse_args()
    if args.effect <= 0:
        parser.error("--effect must be positive")
    groups = defaultdict(list)
    for row in jsonl(args.joined):
        if row.get("rd") is not None:
            groups[row["fam"]].append(float(row["rd"]))
    print("family n sd(delta_R) idealized_equal_n_per_arm")
    for family, values in sorted(groups.items()):
        if len(values) < 2:
            print(f"{family} {len(values)} insufficient_observations")
            continue
        sigma = statistics.stdev(values)
        print(f"{family} {len(values)} {sigma:.6f} {illustrative_n(sigma, args.effect)}")
    print("Assumptions: independent equal-variance arms; expected difference = 3 standard errors.")
    print("Power is unspecified. Rating deltas telescope and depend on starting ratings.")
    print("These are neither a validated detection bound nor a stable policy-strength outcome.")


if __name__ == "__main__":
    main()
