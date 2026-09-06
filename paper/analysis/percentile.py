"""Illustrative inverse of an assumed game-target scale for a historical board.

This is not the actual current payoff percentile: ratings are smoothed and
opponent-adjusted, and display transformations/reference-pool drift may apply.
"""
BOARD = [("grok 4.6", 2594.5), ("Agent 5", 2591.2), ("C-agent", 2386.2),
         ("gill bates", 2376.1), ("Athena", 2371.3), ("7aidara_Gamma", 2360.8),
         ("theta", 2353.4)]
FAMILIES = [("bargaining", 2127.9), ("negotiation", 2818.0), ("persuasion", 2136.3)]


def pct(r):
    return 0.5 + (r - 2000.0) / 8000.0


print("historical board, as model-dependent percentile equivalents")
for i, (n, r) in enumerate(BOARD, 1):
    print("  %d  %-15s %7.1f   %.4f" % (i, n, r, pct(r)))

top = pct(BOARD[0][1]) - pct(BOARD[-1][1])
mid = pct(BOARD[2][1]) - pct(BOARD[-1][1])
gap5 = pct(2371.3) - pct(2360.8)
print("\n  rank 1 to rank 7 spans      %.4f  (%.2f model-equivalent percentile points)" % (top, 100 * top))
print("  rank 3 to rank 7 spans      %.4f  (%.2f model-equivalent percentile points)" % (mid, 100 * mid))
print("  our 10.5-point miss of 5th  %.4f  (%.2f model-equivalent percentile points)" % (gap5, 100 * gap5))

print("\nour own three families")
for n, r in FAMILIES:
    print("  %-12s %7.1f -> %.4f" % (n, r, pct(r)))
mean_r = sum(r for _, r in FAMILIES) / 3
print("  %-12s %7.1f -> %.4f" % ("overall", mean_r, pct(mean_r)))
print("\n  a 346-point rating collapse = %.2f model-equivalent percentile points" % (346 / 80.0))
