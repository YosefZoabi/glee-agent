"""What did abandoned games cost? Abandonment scores at the 5th percentile.

Two sources of abandonment in this project:
  1. games in flight when a run was stopped or force-killed;
  2. turn timeouts from rate limits / restarts.

`rating_delta` is recorded per game, so the cost is directly measurable: compare
the mean rd of abandoned games against the mean rd of completed games in the same
family, and multiply by the count. No counterfactual needed, because the rating
step is linear in the game rating.
"""
import collections
import json
import math
import sys

J = sys.argv[1]
by_out = collections.defaultdict(list)
by_fam = collections.defaultdict(lambda: collections.defaultdict(list))
for ln in open(J, encoding="utf-8"):
    r = json.loads(ln)
    if r.get("rd") is None:
        continue
    o = (r.get("outcome") or "?")
    by_out[o].append(r["rd"])
    by_fam[r["fam"]][o].append(r["rd"])


def mean(v):
    return sum(v) / len(v) if v else float("nan")


print("=== every outcome the agent logged, with its mean rating delta ===")
print("%-22s %8s %10s %10s" % ("outcome", "n", "share", "rd/game"))
tot = sum(len(v) for v in by_out.values())
for o, v in sorted(by_out.items(), key=lambda x: -len(x[1])):
    print("%-22s %8d %9.2f%% %+10.3f" % (o, len(v), 100 * len(v) / tot, mean(v)))

ABANDON = {"timeout", "abandoned", "invalid", "forfeit", "error", "cancelled"}
print("\n=== cost of abandonment ===")
grand_n = grand_cost = 0.0
print("%-12s %8s %10s %10s %12s %12s" %
      ("family", "aband n", "rd|aband", "rd|played", "gap", "total cost"))
for fam in sorted(by_fam):
    ab, ok = [], []
    for o, v in by_fam[fam].items():
        (ab if o.lower() in ABANDON else ok).extend(v)
    if not ab:
        print("%-12s %8d %10s %10.3f %12s %12s" % (fam, 0, "-", mean(ok), "-", "-"))
        continue
    gap = mean(ab) - mean(ok)
    print("%-12s %8d %+10.3f %+10.3f %+12.3f %+12.1f"
          % (fam, len(ab), mean(ab), mean(ok), gap, gap * len(ab)))
    grand_n += len(ab)
    grand_cost += gap * len(ab)
print("\nabandoned games %d of %d (%.3f%%); cumulative rating cost %+.1f points"
      % (grand_n, tot, 100 * grand_n / tot, grand_cost))
print("(a rating step is eta*(game_rating - R), so summed deltas are the drag on"
      " the EMA at the moment they landed, not a permanent offset.)")
