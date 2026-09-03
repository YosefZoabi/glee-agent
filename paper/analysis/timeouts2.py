"""Abandonment cost, from the raw history feed (which keeps the games the turn
logs never finished). Abandoning scores at the 5th percentile.
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
    if not sel:
        continue
    print("=== %s track: %d games ===" % (track.upper(), len(sel)))
    by = collections.defaultdict(list)
    for g in sel:
        o = ((g.get("result") or {}).get("outcome")) or g.get("status") or "?"
        rd = g.get("rating_delta")
        if rd is not None:
            by[o].append(rd)
    tot = sum(len(v) for v in by.values())
    print("%-18s %8s %9s %10s" % ("outcome", "n", "share", "rd/game"))
    for o, v in sorted(by.items(), key=lambda x: -len(x[1])):
        print("%-18s %8d %8.3f%% %+10.3f" % (o, len(v), 100 * len(v) / tot, mean(v)))

    ABANDON = {"timeout", "abandoned", "invalid", "forfeit", "error", "cancelled",
               "incomplete", "expired"}
    ab, ok = [], []
    for o, v in by.items():
        (ab if str(o).lower() in ABANDON else ok).extend(v)
    if ab:
        gap = mean(ab) - mean(ok)
        print("\n  abandoned %d of %d (%.3f%%)   rd|abandoned %+.3f   rd|played %+.3f"
              % (len(ab), tot, 100 * len(ab) / tot, mean(ab), mean(ok)))
        print("  gap %+.3f rating points per abandoned game -> %+.1f points of"
              " cumulative drag\n" % (gap, gap * len(ab)))
    else:
        print("  no abandoned games recorded\n")
