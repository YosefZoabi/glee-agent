"""The human track: how the 2nd-place human played, against our own agent."""
import json, sys, collections, math, statistics
S = sys.argv[1]; J = sys.argv[2]

def L(p):
    d = json.load(open(S + "/" + p, encoding="utf-8"))
    return list(d.values()) if isinstance(d, dict) else d

hist = {h["game_id"]: h for h in L("human_hist_full.json")}
reps = {}
for f in ("human_replays.json", "human_replays_rand.json", "human_barg_recent.json", "human_persuasion.json"):
    d = json.load(open(S + "/" + f, encoding="utf-8"))
    reps.update(d)
def mean(v): return sum(v)/len(v) if v else float("nan")

print("=== HUMAN RECORD (all rated games) ===")
by = collections.defaultdict(list)
for h in hist.values(): by[h["game_family"]].append(h)
print("%-12s %7s %10s %12s" % ("family", "n", "rd/game", "date range"))
for f in sorted(by):
    v = by[f]; rd = [x["rating_delta"] for x in v if x.get("rating_delta") is not None]
    ds = sorted((x.get("completed_at") or "")[:10] for x in v)
    print("%-12s %7d %+10.3f  %s..%s" % (f, len(v), mean(rd), ds[0], ds[-1]))

# ---------------------------------------------------------------- bargaining
print("\n=== BARGAINING: human vs our agent, matched cells ===")
H = collections.defaultdict(list); Hacc = []
for g in reps.values():
    if g.get("game_family") != "bargaining": continue
    c = g.get("config") or {}; pot = c.get("money_to_divide"); me = g.get("your_player")
    if not pot or not me: continue
    d1, d2 = c.get("delta_1"), c.get("delta_2")
    du, dt = (d1, d2) if me == "player_1" else (d2, d1)
    hor = "known" if c.get("max_rounds") else "open"
    res = g.get("result") or {}
    pay = res.get("player_1_payoff" if me == "player_1" else "player_2_payoff")
    if pay is None: continue
    H[(hor, me, du, dt)].append((pay / pot, res.get("outcome"), res.get("agreed_round")))
    mk = "alice_gain" if me == "player_1" else "bob_gain"
    ar = res.get("agreed_round")
    for m in g.get("moves") or []:
        if m.get("move_type") != "offer": continue
        dd = m.get("move_data") or {}
        if mk not in dd: continue
        rnd = m.get("round") or 0
        ours = (rnd % 2 == 1) == (me == "player_1")
        if not ours:
            Hacc.append((dd[mk] / pot, rnd, bool(ar and rnd == ar), du, dt, hor))

A = collections.defaultdict(list)
for ln in open(J, encoding="utf-8"):
    r = json.loads(ln)
    if r["fam"] != "bargaining" or r.get("my_share") is None: continue
    A[("known" if r.get("hk") else "open", r["slot"], r.get("d_us"), r.get("d_them"))].append(
        (float(r["my_share"]), r.get("outcome"), r.get("agreed_round")))

print("%-6s %-9s %5s %5s | %6s %8s %7s | %6s %8s %7s | %7s"
      % ("hor","seat","d_us","d_th","hu n","hu bank","hu r","ag n","ag bank","ag r","diff"))
wins = losses = 0; diffs = []
for k in sorted(set(H) & set(A)):
    h, a = H[k], A[k]
    if len(h) < 25 or len(a) < 100: continue
    hb, ab = mean([x[0] for x in h]), mean([x[0] for x in a])
    hr = mean([x[2] for x in h if x[2]]); ar_ = mean([x[2] for x in a if x[2]])
    diffs.append(hb - ab); wins += hb > ab; losses += hb <= ab
    print("%-6s %-9s %5.2f %5.2f | %6d %8.3f %7.1f | %6d %8.3f %7.1f | %+7.3f"
          % (k[0], k[1], k[2], k[3], len(h), hb, hr, len(a), ab, ar_, hb - ab))
if diffs:
    print("\n  human beats the agent in %d of %d matched cells; mean advantage %+.3f of pot"
          % (wins, wins + losses, mean(diffs)))

print("\n=== HUMAN ACCEPT BAR (offers faced) vs the agent's ===")
b = collections.defaultdict(lambda: [0, 0])
for sh, rnd, acc, du, dt, hor in Hacc:
    b[min(int(sh * 20) / 20.0, 0.95)][0] += acc; b[min(int(sh * 20) / 20.0, 0.95)][1] += 1
print("  %-14s %7s %8s %10s" % ("offer faced", "n", "signed", "accept rate"))
for k in sorted(b):
    acc, n = b[k]
    if n < 15: continue
    print("  %.2f - %.2f  %7d %8d %10.2f  %s" % (k, k + .05, n, acc, acc / n, "#" * int(round(acc / n * 26))))
allh = [x for x in Hacc]
print("  human: faced %d offers, signed %.1f%%, mean share refused %.3f, mean share signed %.3f"
      % (len(allh), 100 * mean([1.0 if x[2] else 0.0 for x in allh]),
         mean([x[0] for x in allh if not x[2]]), mean([x[0] for x in allh if x[2]])))

nd = collections.Counter()
for k, v in H.items():
    for x in v: nd[x[1]] += 1
tot = sum(nd.values())
print("  human bargaining outcomes: " + ", ".join("%s %.1f%%" % (k, 100 * v / tot) for k, v in nd.most_common()))
