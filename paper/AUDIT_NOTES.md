# Audit notes accompanying the submitted paper

These notes describe analysis methods, implementation checks, and data
availability. Code checks use synthetic inputs; full empirical reproduction
requires the private datasets described below.

## Scope of the main result

Five policy builds had different rating histories. Their rounded plotted
coordinates imply an initial overall spread of about 85 points, a maximum near
88 about ten minutes into the window, and an endpoint spread near 46.
The figure's 45 snapshots are dependent repeated observations. This establishes
observed dispersion, not an identified statistical noise floor or a decomposition
into initialization, matchmaking and reference-pool effects. Raw snapshots,
per-family game counts, deployment hashes and the sampling protocol remain
necessary for a stronger analysis.

## Public analysis corrections

- `analysis/noise.py` now audits the actual rounded figure coordinates and can
  summarize a supplied original poll CSV. The former calendar-day rating-delta
  calculation did not generate the plotted histories. Figure-derived values
  are explicitly approximate, not newly recovered raw observations.
- `analysis/pers_pool.py` accepts its documented two positional inputs.
  Separate purchase-quality calculations require the explicit optional
  `--buyer-replays` argument. It reports row denominators and missingness,
  excludes missing payoffs instead of replacing them by zero, and does not
  classify missing quality as low.
- `analysis/human2.py` selects the largest discounted forgone payoff, rather
  than discounting the largest nominal offer after selection. Ties and the
  non-tie denominator are reported separately. This is a retrospective local
  comparison, not a demonstration of ex-ante optimal refusal behavior.
- `analysis/timeouts*.py` report observed outcomes/deltas, not causal costs.
  The obsolete fixed-target calculation used 1640 even though
  `2000 + 8000 * (0.05 - 0.5)` is -1600. Its inferred persistent cost was
  removed, not replaced by an unverified alternative.
- `analysis/power.py` labels `n = 18*sigma^2/effect^2` as an IID
  three-standard-error illustration. That threshold does not specify power;
  mean consecutive rating changes telescope to the endpoint difference over n.
- `analysis/breakeven.py` uses OLS, not weighted least squares, and does not
  call the fitted root a field median. Roots outside the feasible share range
  are not silently discarded. Bootstrap instability is retained and reported.
- `analysis/validate.py` reports both all-defined-root and historical
  range-filtered split-half diagnostics, plus exclusions. The historical
  correlation retained only cells whose two roots were both in [0, 1.3].
  The invalid comparison of all seats/horizons with one infinite-horizon
  proposer-share formula has been removed.
- `analysis/percentile.py` labels its inverse scale as a model-dependent
  equivalent, not a literal current payoff percentile.
- Parser diagnostics distinguish reclassified recorded purchases from the
  outcome of deploying a changed policy. Unknown quality is separately counted.

## Historical aggregate output

`data/breakeven_legacy_diagnostics.json` contains historical numerical
diagnostics. Its invalid SPE comparison column was
removed and its schema/provenance made explicit. For example, one retained root
near 0.79 has an IID bootstrap interval near [-4.31, 5.41]. Such an interval
provides little precision. The original output was already filtered, so it cannot
reconstruct the excluded cells. It is not the output of the corrected default
analysis.

## Interpretation boundaries

Purchase-conditioned quality is not message-understanding accuracy or an
equivalence test. Same-author human play is observational, not a general
human-machine experiment. Live comparisons, transcript reclassification and
local counterfactuals are different evidence types; their standardized statistics
do not establish a shared replication criterion or game-theoretic dominance.
The GLEE framework already documents quality-independent seller utility.
Bayesian-persuasion thresholds require assumptions about a known recommendation
policy and buyer response; without commitment they remain heuristic here.

## Reproducibility still unavailable

Private joined logs, human exports, rating snapshots, exact run configuration
metadata, and the original replay reconstruction pipeline are not supplied.
Anticipated organizer game data would not automatically recover all of these.
Correctness tests below use synthetic data; they do not validate the empirical
counts in the submitted paper. No test or figure-derived number is presented as
a replacement empirical result.

## Historical register

The change register retains contemporaneous observations and wording, with an
explicit warning. In particular, its early round-99 cap was superseded by the
observed round-96 limit; its causal/dominance/noise-floor statements are not
current validated conclusions. Earlier register hashes can refer to historical
local development commits that are not available in this public repository.
