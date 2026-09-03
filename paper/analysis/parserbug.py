"""Reproduce the message-parser defect and price the fix.

The buyer classifies a free-text seller message as a recommendation unless it
matches a list of refusal phrases. The competition's final commit added a block
of phrases. This re-scores every logged buyer round against BOTH lists.
"""
import json, sys, collections
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from glee_agent.strategies.persuasion import _NEGATIVE_HINTS as AFTER

ADDED = ("not this one","below standard","wouldn't buy it","would not buy it",
         "pass this round","low-quality product","low quality product",
         "wouldn't be a fair trade","would not be a fair trade","there'll be better")
BEFORE = tuple(h for h in AFTER if h not in ADDED)

def positive(msg, hints):
    if msg is None: return False
    s = str(msg).strip().lower()
    if not s: return False
    return not any(h in s for h in hints)

rounds = flipped = flipped_bought = flipped_high = 0
good_lost = 0
bought_pos_before = collections.Counter()
cells = collections.Counter()
for ln in open(sys.argv[1], encoding="utf-8"):
    g = json.loads(ln)
    for h in g.get("history") or []:
        msg = h.get("seller_message")
        if msg is None: continue
        rounds += 1
        pb, pa = positive(msg, BEFORE), positive(msg, AFTER)
        q = h.get("quality")
        if h.get("bought") and q is not None:
            bought_pos_before[(pb, q)] += 1
        if pb and not pa:                       # the fix changes this round
            flipped += 1
            if h.get("bought"):
                flipped_bought += 1
                if q == "high":
                    flipped_high += 1; good_lost += 1
                elif q == "low":
                    cells[(g.get("m"), g.get("p"))] += 1
print("buyer rounds with a seller message : %d" % rounds)
print("rounds the added phrases re-classify: %d" % flipped)
print("  ... of which we BOUGHT             : %d" % flipped_bought)
print("  ... high quality (good units lost) : %d" % flipped_high)
print("  ... low quality  (duds refused)    : %d" % (flipped_bought - flipped_high))
if flipped_bought:
    print("  dud rate on the re-classified buys  : %.4f" % (1 - flipped_high / flipped_bought))
print("\nquality delivered, by what the OLD classifier said (bought rounds only):")
for pb in (True, False):
    hi = bought_pos_before[(pb, "high")]; lo = bought_pos_before[(pb, "low")]
    if hi + lo:
        print("  old says %-14s n=%-6d high %.4f" % ("RECOMMEND" if pb else "refuse", hi + lo, hi / (hi + lo)))
print("\nduds refused by cell (m, p):")
for k, v in sorted(cells.items(), key=lambda x: -x[1])[:10]:
    print("  m=%-5s p=%-6s %d" % (k[0], k[1], v))
