# Camera-ready version (IAB @ NeurIPS 2026, GLEE Competition Track)

[Read the camera-ready PDF](glee_competition_paper_camera_ready.pdf).

The submitted paper in `../` is kept unchanged. This folder derives the
camera-ready version from it:

```sh
python paper/camera_ready/gen_fig.py            # two-panel Figure 1 + data/
python paper/camera_ready/make_camera_ready.py  # asserted edits -> glee_competition_paper.tex
cd paper/camera_ready && pdflatex glee_competition_paper && pdflatex glee_competition_paper
```

`make_camera_ready.py` applies every change as an exact, asserted replacement of
the submitted text, so the script itself is the diff between the reviewed
submission and this version. Main text ends on page 5 (one extra page is allowed
for the camera-ready); references and appendices follow.

## Changes in response to the reviews

| Reviewer point | Change |
|---|---|
| Figure 1 plots absolute ratings; the largest spread sits at the first snapshot (both reviewers) | Figure 1 now has two panels: (a) overall ratings, (b) change since each slot's first snapshot, R_i(t) - R_i(0). Starting and ending ratings are in the caption. |
| Report starting ratings, initial and terminal spreads, spread after normalizing, rank changes (w8XP) | Section 3 reports the 85.3-point starting spread, 45.8-point ending spread, that the 88.0 maximum came ten minutes in (so it is inherited), gains of +39 to +167, 31 distinct orderings, every slot leading at least once, and each slot's game count (2,945-3,195). |
| Separate inherited offsets from dispersion accrued during the window (both) | Section 3 applies the stated EMA: only 6-21 points of the starting gap should persist, leaving a 49-64-point accrued spread. Labelled model-dependent. |
| "Noise floor" overstates what the experiment identifies (w8XP) | Text now says dispersion throughout and states the spreads are not an identified noise floor. The title is kept by the author's choice. |
| Byte-identical claim vs. verification of a reference build only (yxm9) | "Byte-identical builds" replaced by "slots running the same policy"; Appendix B states the deployment procedure and that per-slot hashes were not recorded. |
| Simplified EMA must stay clearly separate from the server rule (w8XP) | Section 3 says it is a fitted approximation, not the documented rule, and that conclusions using it are model-dependent; adds that overall = unweighted mean of the three family ratings (verified against the leaderboard API). |
| Replay is implementation validation, not policy-value estimation (w8XP) | Section 4 says so explicitly and recommends counting changed actions before any live arm. |
| sigma labels could be misread as confirmatory (w8XP) | All "sigma" labels became "standardized effect", defined as an exploratory effect-to-noise ratio. |
| Seller-arm statistic: unit of analysis and interval missing (yxm9) | Section 5 gives the unit (29 agent-runs, centred within run), slope -0.048 (s.e. 0.162) and 95% interval -0.37 to +0.27, plus the sales difference. |
| Which hypotheses/inclusion rules were pre-specified (w8XP) | Section 5 states the shipping rule from 21 August, that the final-morning change broke it, and that hypotheses and cell filters were not pre-specified. |
| Intervention ledger for the 30+ interventions (yxm9) | New Appendix Table A5: intervention register by family with evidence type, unit/cohort, recorded result and status, including null, abandoned and retracted entries. |
| Define m before the m.p regimes (yxm9) | Section 2 defines m and p and the m.p > 1 condition; notation is m.p throughout. |
| Is the 79.8% walk-away rate conditioned on agent-observable unprofitability? (yxm9) | Section 2 defines the untradable seat from the agent's own value. Section 6 replaces 79.8% with a reproducible count from one slot's logs: it walked in all 1,380 such seats where it had a decision turn; the 81.0% overall rate reflects games that ended first. |
| How sensitive are the EMA conclusions to eta? (w8XP) | Section 3: for eta 0.0015-0.0025 the inherited residual is 3-30 points and the accrued spread 47-73; the conclusion holds. |
| Release a sanitized snapshot table (yxm9) / reproducibility manifest (w8XP) | `data/` releases the 45 plotted overall ratings and per-slot counters; Appendix D lists what a regenerable record needs and what is missing. |

Author's revision pass: the exploratory break-even fits moved from Section 4 to
Appendix B; Section 8 gained "Lessons for entrants" and "Suggestions for live
competitions"; repeated caveats were condensed.

Second review pass (an independent LLM review against both reviews): exact
decomposition formula and scenario framing; one-decimal ratings in the caption;
peak and terminal spread of the gains; "deployed from the same reference build"
used consistently; named the two inert interventions; defined the standardized
effect; regression unit and standard-error caveat for the seller arm; unit fixed
to "108 refusals"; parser re-scoring separated from deployment benefit;
untradable seat defined by strictly profitable trade; tuning arms given separate
rows; availability of the server rule, matching feasibility and a cohort
crosswalk added to Appendix D.

Formatting required by the organizers: `\usepackage[sglblindworkshop, final]{neurips_2026}`,
`\workshoptitle{Interpreting Agent Behavior (IAB) -- GLEE Competition Track}`,
author affiliation added, Agent Behavior Analysis section retained.

## Provenance of the new numbers

- Starting/ending ratings, game counters and the 88.0 / 48.1 spreads: the
  original poll analysis of run58 (five slots, 45 polls, 2026-08-29).
- Figure 1 values, rank orderings and the inherited/accrued decomposition:
  `gen_fig.py`, from the submitted figure's rounded coordinates (+-0.1 point).
- Walk-away counts: one slot's turn logs (`logs/turns-202608{26..30}.jsonl`,
  not distributed), untradable seat defined exactly as in
  `glee_agent/strategies/negotiation.py::_untradable_seat`.
- Seller-arm slope and sales: project notes from 2026-08-28.
- Intervention register: `../change-register.html` and the project notes.
