"""The final board, expressed in the payoff percentile it is a transform of.

game_rating = 2000 + 8000*(pct - 0.5), and with tens of thousands of games per
family eta has decayed and R has converged, so the displayed rating inverts to
pct = 0.5 + (R - 2000)/8000. One percentile point is 80 rating points.
"""
BOARD = [("grok 4.6", 2594.5), ("Agent 5", 2591.2), ("C-agent", 2386.2),
         ("gill bates", 2376.1), ("Athena", 2371.3), ("7aidara_Gamma", 2360.8),
         ("theta", 2353.4)]
FAMILIES = [("bargaining", 2127.9), ("negotiation", 2818.0), ("persuasion", 2136.3)]


def pct(r):
    return 0.5 + (r - 2000.0) / 8000.0


print("final agent track, as payoff percentile")
for i, (n, r) in enumerate(BOARD, 1):
    print("  %d  %-15s %7.1f   %.4f" % (i, n, r, pct(r)))

top = pct(BOARD[0][1]) - pct(BOARD[-1][1])
mid = pct(BOARD[2][1]) - pct(BOARD[-1][1])
gap5 = pct(2371.3) - pct(2360.8)
print("\n  rank 1 to rank 7 spans      %.4f  (%.2f percentile points)" % (top, 100 * top))
print("  rank 3 to rank 7 spans      %.4f  (%.2f percentile points)" % (mid, 100 * mid))
print("  our 10.5-point miss of 5th  %.4f  (%.2f percentile points)" % (gap5, 100 * gap5))

print("\nour own three families")
for n, r in FAMILIES:
    print("  %-12s %7.1f -> %.4f" % (n, r, pct(r)))
mean_r = sum(r for _, r in FAMILIES) / 3
print("  %-12s %7.1f -> %.4f" % ("overall", mean_r, pct(mean_r)))
print("\n  a 346-point rating collapse = %.2f percentile points" % (346 / 80.0))
