"""Break-even estimator: recover the FIELD MEDIAN outcome from rating_delta alone.

rd = eta*(2000 + 8000*(pct - 0.5) - R) is strictly increasing in the percentile
pct, and pct is the rank of our payoff among all payoffs on the SAME config in
the SAME role. So the outcome value x* at which E[rd | outcome = x] = 0 is the
outcome whose percentile equals the one the agent's own rating already sits at
-- i.e. the field's median for that cell, recovered with NO counterfactual and
NO survivorship (every game contributes, including no-deals at share 0).

Fit: weighted least squares of rd on the banked share within the cell, then
solve for the root. Reported with a bootstrap CI.
"""
import json, sys, collections, random, statistics

PATH = sys.argv[1]
rows = collections.defaultdict(list)
for ln in open(PATH, encoding="utf-8"):
    r = json.loads(ln)
    if r["fam"] != "bargaining":
        continue
    if r.get("rd") is None or r.get("my_share") is None:
        continue
    if r.get("d_us") is None or r.get("d_them") is None:
        continue
    key = ("open" if not r.get("hk") else "known", r["slot"], r["d_us"], r["d_them"])
    rows[key].append((float(r["my_share"]), float(r["rd"])))


def root(pairs):
    n = len(pairs)
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    if sxx <= 0 or abs(sxy) < 1e-12:
        return None
    b = sxy / sxx
    a = my - b * mx
    return -a / b


def spe(du, dt):
    den = 1.0 - du * dt
    return 0.5 if den <= 1e-9 else (1.0 - dt) / den


random.seed(7)
print("%-6s %-9s %5s %5s %7s %8s %14s %8s %7s"
      % ("hor", "seat", "d_us", "d_them", "n", "we bank", "field median", "SPE", "gap"))
out = []
for key in sorted(rows):
    hor, seat, du, dt = key
    pairs = rows[key]
    if len(pairs) < 200:
        continue
    x = root(pairs)
    if x is None or not (0.0 <= x <= 1.2):
        continue
    boots = []
    for _ in range(200):
        s = [pairs[random.randrange(len(pairs))] for _ in range(len(pairs))]
        rb = root(s)
        if rb is not None:
            boots.append(rb)
    boots.sort()
    lo, hi = boots[int(.025 * len(boots))], boots[int(.975 * len(boots))]
    ours = sum(p[0] for p in pairs) / len(pairs)
    s = spe(du, dt)
    print("%-6s %-9s %5.2f %5.2f %7d %8.3f  %.3f [%.2f,%.2f] %8.3f %+7.3f"
          % (hor, seat, du, dt, len(pairs), ours, x, lo, hi, s, ours - x))
    out.append((hor, seat, du, dt, len(pairs), ours, x, lo, hi, s))
json.dump(out, open("breakeven_out.json", "w"), indent=1)
