"""Where did the abandoned games come from, and what did they permanently cost?

Transient vs persistent matters here. The rating is an EMA, so a bad game is
pulled back by the games after it; the resting rating equals the mean game
rating. A fraction f of games scored at the 5th percentile (game rating
2000+8000(0.05-0.5) = 1640) therefore shifts the RESTING rating by about
f * (R - 1640), which is far smaller than the sum of the rating steps.
The exception is the end of the competition: a game abandoned in the last hours
is never averaged away, because the run stops.
"""
import collections
import json
import sys

rows = []
for path in sys.argv[1:]:
    d = json.load(open(path, encoding="utf-8"))
    rows.extend(d.values() if isinstance(d, dict) else d)


def mean(v):
    return sum(v) / len(v) if v else float("nan")


for track in ("agent", "human"):
    sel = [g for g in rows if (g.get("your_player_type") or "agent") == track]
    to = [g for g in sel
          if ((g.get("result") or {}).get("outcome")) == "timeout"
          and g.get("rating_delta") is not None]
    ok = [g for g in sel
          if ((g.get("result") or {}).get("outcome")) not in (None, "timeout")
          and g.get("rating_delta") is not None]
    if not to:
        continue
    print("=== %s track ===" % track.upper())
    n, N = len(to), len(to) + len(ok)
    f = n / N
    print("  abandoned %d of %d = %.3f%% of rated games" % (n, N, 100 * f))
    print("  rd|abandoned %+.3f   rd|played %+.3f   sum of steps %+.1f"
          % (mean([g["rating_delta"] for g in to]),
             mean([g["rating_delta"] for g in ok]),
             sum(g["rating_delta"] for g in to)))
    R = 2360 if track == "agent" else 2400
    print("  persistent shift in the RESTING rating ~ f*(R-1640) = %.1f points"
          % (f * (R - 1640)))
    days = collections.Counter((g.get("completed_at") or "")[:10] for g in to)
    print("  worst days: " + ", ".join("%s x%d" % (d, c)
                                       for d, c in days.most_common(5)))
    fam = collections.Counter(g.get("game_family") for g in to)
    print("  by family: %s" % dict(fam))
    # how bunched are they? a run-stop abandons everything in flight at once
    hrs = collections.Counter((g.get("completed_at") or "")[:13] for g in to)
    big = [(h, c) for h, c in hrs.items() if c >= 3]
    print("  hours holding >=3 abandonments: %d, covering %d of %d games"
          % (len(big), sum(c for _, c in big), n))
    print()
