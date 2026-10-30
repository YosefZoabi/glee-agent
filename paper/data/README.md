# Data released with the paper

## Figure 1 (camera-ready)

The identical-policy experiment ("run58") polled five slots together 45 times
between 2026-08-29 10:58 and 19:37 (as logged by the poller).

- `fig1_overall_snapshots.csv`: the 45 plotted overall ratings per slot. Values
  are decoded from the submitted figure's rounded TikZ coordinates by
  `../gen_fig.py`, so they are approximate (about +-0.1 rating point).
- `fig1_slots.csv`: each slot's lifetime game counter and overall rating at the
  first and last snapshot, as printed by the original poll analysis. The
  ranked agent was `7aidara_Gamma` (B5).

Not included: per-family ratings and game counts per snapshot, and per-slot
source, configuration and entry-point hashes. The family snapshots behind the
reported within-family spreads were kept in a local working directory and are
not part of this release; deployment hashes were not recorded.

## Historical diagnostics

- `breakeven_legacy_diagnostics.json`: historical break-even fit diagnostics
  that predate the corrected analysis; see the
  [audit notes](../AUDIT_NOTES.md) before using them.
