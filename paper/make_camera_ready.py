"""Derive the camera-ready source from the submitted paper.

Reads submitted/glee_competition_paper.tex, which stays untouched, and writes
glee_competition_paper.tex next to this script. Every edit below is an exact,
asserted replacement, so a reader can audit what changed between the reviewed
submission and the camera-ready version.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
src = (HERE / "submitted" / "glee_competition_paper.tex").read_text(encoding="utf-8")
EDITS = []


def edit(old, new, label):
    EDITS.append((old, new, label))


# --- format required for the camera-ready (organizer instructions) ----------
edit(r"""% Preserve the supplied non-anonymous preprint presentation.
% Competition-track anonymity requirements must be checked at submission.
\IfFileExists{neurips_2026.sty}{%
  \usepackage[preprint]{neurips_2026}%
}{""",
r"""% Camera-ready format required by the GLEE competition organizers.
\IfFileExists{neurips_2026.sty}{%
  \usepackage[sglblindworkshop, final]{neurips_2026}%
}{""", "style options")

edit(r"""\title{Below the Noise Floor: A Deterministic GLEE Agent\\
       and the Measurement Problem It Exposed}""",
r"""\workshoptitle{Interpreting Agent Behavior (IAB) -- GLEE Competition Track}

\title{Same Policy, Different Ratings:\\
       A Deterministic GLEE Agent and\\
       the Measurement Problem It Exposed}""", "workshop title, camera-ready title")

edit(r"""pdftitle={Below the Noise Floor: A Deterministic GLEE Agent and the Measurement Problem It Exposed}""",
r"""pdftitle={Same Policy, Different Ratings: A Deterministic GLEE Agent and the Measurement Problem It Exposed}""",
     "pdf title")

edit(r"""%  Below the Noise Floor
""", r"""%  Same Policy, Different Ratings (submitted as "Below the Noise Floor")
""", "header comment title")

edit(r"""  Yosef Zoabi\\
  \texttt{yosef.zoabi@campus.technion.ac.il}\\""",
r"""  Yosef Zoabi\\
  Faculty of Data and Decision Sciences\\
  Technion -- Israel Institute of Technology, Haifa, Israel\\
  \texttt{yosef.zoabi@campus.technion.ac.il}\\""", "affiliation")

edit(r"""%  PAGE LIMIT
%    Main body = pages 1-4, ending at \section{Conclusion}.
%    References are unlimited. Everything after \appendix is
%    SUPPLEMENTARY -- delete it if the chairs enforce "references only".""",
r"""%  PAGE LIMIT (camera-ready)
%    Main body = pages 1-5, ending at \label{endmain}.
%    References and appendices are unlimited.""", "header comment")

# --- abstract: the headline is the inherited gap, the terminal gap and the
#     dispersion that accrued during the window (both reviewers) -------------
edit(r"""negotiation and persuasion. In a simultaneous 8.6-hour comparison, five identical
policy builds accumulated approximately 3,000 games each yet differed by as much
as 88 overall rating points and 293 within a game family. This documents substantial
leaderboard dispersion without a policy change, while leaving the contributions of
initialization, matchmaking and a changing reference pool unresolved. Decision-level""",
r"""negotiation and persuasion. In a simultaneous 8.6-hour comparison, five slots
running the same policy each played about 3,000 games. They began 85 overall
rating points apart because their rating histories differed, so the 88-point
maximum spread largely reflects that inherited gap. They ended 46 points apart,
and the slot that started last finished first. Under a simplified rating model,
at most 6--21 points of the starting gap should have persisted, so most of the
terminal spread accrued during the window; separating matchmaking, sampling and a
changing reference pool would still require reset ratings. Decision-level""", "abstract")

# --- introduction ------------------------------------------------------------
edit(r"""Here, five simultaneous identical-policy controls reveal rating dispersion in a
live competition, and offline audits distinguish changed behavior from changes
that never affected an action.""",
r"""Here, five simultaneous identical-policy controls reveal rating dispersion in a
live competition that is large relative to the effects of tuning, and offline
audits distinguish changed behavior from changes that never affected an action.""", "intro")

# --- section 2: define the persuasion quantities before m.p regimes appear,
#     and the untradable seat before the walk-away rate (reviewer yxm9) -------
edit(r"""prices at possible tradable rungs. Independent uniform draws on that ladder
predict positive surplus in $6/16=37.5\%$ of value pairs; independence of roles
alone would not imply that rate. When observed information rules out profitable
trade, the policy walks away.""",
r"""prices at possible tradable rungs. Independent uniform draws on that ladder
predict positive surplus in $6/16=37.5\%$ of value pairs; independence of roles
alone would not imply that rate. A seller holding the top rung, or a buyer holding
the bottom one, has no possible counterparty. The agent can see this from its own
value alone, so in such an \emph{untradable seat} it names an out-of-pool price
on a proposal turn and walks away at its next decision turn.""", "untradable seat")

edit(r"""\textbf{Persuasion.} Consistent with GLEE's documented payoff structure, the
competition seller received the full price on a sale regardless of quality""",
r"""\textbf{Persuasion.} In each cell a buyer values a high-quality unit at $m$ times
its price and a low-quality unit at nothing, and $p$ is the prior probability of
high quality, so buying blind has positive expected value exactly when $m\cdot p>1$.
Consistent with GLEE's documented payoff structure, the
competition seller received the full price on a sale regardless of quality""", "define m")

edit(r"""budget with the horizon. The buyer combines message parsing with within-game
purchase outcomes and recommendation frequency; quality is hidden after a decline.""",
r"""budget with the horizon. The buyer combines message parsing with within-game
purchase outcomes and recommendation frequency, and vetoes message templates that
have only delivered low quality (Appendix Table~\ref{tab:ladder}); quality is
hidden after a decline.""", "cite ladder")

edit(r"""configured by 114 tunables. Parameters are fixed during a run; within-game state""",
r"""configured by 114 tunables; its development fleet logged 264,432 games
(Appendix Table~\ref{tab:volume}). Parameters are fixed during a
run; within-game state""", "cite volume")

# --- section 3: rewritten around the inherited and accrued dispersion -------
edit(r"""\section{Identical policies, different leaderboard histories}
Five byte-identical builds were polled together for 8.6 hours, producing 45
simultaneous snapshots over approximately 3,000 games per agent. The overall
min--max spread averaged 48.1 points and reached 88.0; the largest within-family
spread was 292.9 (Figure~\ref{fig:noise}). These are descriptive spreads, not
confidence intervals. The five agents had different initial ratings and match
histories, and successive polls are dependent. The experiment measures their
joint effect with sampling and pool changes, rather than isolating one source
of noise.
""",
r"""\section{Identical policies, different leaderboard histories}
\label{sec:noise}
Because only an account's best slot is ranked, I spent five slots as simultaneous
controls on the final full day of the competition. All five ran the same policy
(Appendix~\ref{app:lim} describes how far that identity was verified) and were
polled together 45 times over 8.6 hours while each played 2,945--3,195 games.
Their rating states were not reset: they started between 2177 and 2263, an
85.3-point overall spread, and ended between 2299 and 2344, a 45.8-point spread.
The overall spread averaged 48.1 points, and its 88.0-point maximum came ten
minutes into the window, so the maximum reflects the inherited gap rather than
divergence. Measured from each slot's own start (Figure~\ref{fig:noise}b), the
five gained between $+39$ and $+167$ points; the slot that started lowest
finished highest, every slot led at least one snapshot, and the 45 snapshots
showed 31 distinct orderings of the five. Within single families the spread
reached 292.9 points.
""", "section 3 opening")

edit(r"""\caption{Overall ratings of five identical policy builds over 8.6 hours.
Shading is the observed min--max envelope, not an uncertainty interval.
The mean spread is 48.1 points and its maximum is 88.0. Initial rating states
were not reset.}""",
r"""\caption{Five slots running the same policy, polled together 45 times over 8.6
hours. (a)~Overall rating; shading is the observed min--max envelope, not an
uncertainty interval. Rating states were not reset: B$_1$--B$_5$ started at 2204,
2205, 2263, 2200 and 2177 (spread 85.3) and ended at 2299, 2302, 2302, 2321 and
2344 (spread 45.8). (b)~Change since each slot's first snapshot,
$R_i(t)-R_i(0)$.}""", "figure caption")

edit(r"""Competition scoring compares payoffs within a configuration and role and adjusts
for opponent strength. For interpreting late-stage updates, I used the simplified
EMA model $R_{t+1}=(1-\eta)R_t+\eta g_t$, with $\eta\approx0.002$ inferred from
rating deltas and $g_t$ denoting an adjusted game target. At constant $\eta$, its
half-life is $\log(0.5)/\log(1-\eta)\approx346$ family games. Under independent,
stationary targets, its effective sample size is $(2-\eta)/\eta=999$; lifetime
game volume therefore need not describe the information in the current rating.
These are model implications, not a reconstruction of every server update.
""",
r"""Competition scoring compares payoffs within a configuration and role and adjusts
for opponent strength, and the overall rating is the unweighted mean of the three
family ratings, which I verified against the leaderboard API. To interpret
updates I use a simplified per-family EMA, $R_{t+1}=(1-\eta)R_t+\eta g_t$, with
$\eta\approx0.002$ inferred from rating deltas and $g_t$ an adjusted game target
on the rating scale. This is an approximation I fitted, not the documented server
rule, and every conclusion that relies on it is model-dependent. At constant
$\eta$ an offset decays by $(1-\eta)^n$ after $n$ family games, a half-life of
about 346 games. Under independent, stationary targets the effective sample size
is $(2-\eta)/\eta=999$; lifetime game volume therefore need not describe the
information in the current rating.

Applied to Figure~\ref{fig:noise}, the model separates inherited from accrued
dispersion. If each slot's games split evenly across families, about 1,000 per
family, between 7\% and 25\% of each starting offset should persist (for 1,300
down to 700 family games), which is 6--21 points of the 85.3-point gap.
Subtracting each slot's modelled residual from its final rating leaves a
49--64-point spread, so most terminal dispersion accrued during the window.
Varying $\eta$ from 0.0015 to 0.0025, half-lives of 462 to 277 games, widens
these ranges to 3--30 and 47--73 points without changing that conclusion. This
decomposition depends on the rating model, the assumed split and rounded
plotted values, and within the accrued part matchmaking, sampling and pool
changes remain jointly confounded. All of these spreads describe dependent
snapshots; they are neither confidence intervals nor an identified noise floor.
""", "EMA and decomposition")

edit(r"""The reference pool changes as games enter it, making unmatched cross-time
comparisons confounded. Selecting or freezing a high-scoring slot also makes
stopping time part of the evaluation protocol.""",
r"""The reference pool changes as games enter it, making unmatched cross-time
comparisons confounded. Over this window the five slots also rose by 104 points
on average without any policy change, so an unmatched before-and-after comparison
would have credited about 100 points to whatever changed at its start. Selecting
or freezing a high-scoring slot also makes stopping time part of the evaluation
protocol.""", "common drift")

# --- section 4: replay validates implementation, not policy value (w8XP) ----
edit(r"""\textbf{Decision-level replay.} The reference policy reproduced 4,272 of 4,272
bargaining and 13,056 of 13,056 negotiation decisions in the audited cohorts.
Replay then counted actions changed by a candidate flag, rather than how often
its condition held. One condition fired on 43\% of eligible games yet changed
0 of 13,056 decisions; another changed 0 of 13,479. Exact replay validates the
implementation on logged states, not the outcome of unobserved trajectories.""",
r"""\textbf{Decision-level replay.} The reference policy reproduced 4,272 of 4,272
bargaining and 13,056 of 13,056 negotiation decisions in the audited cohorts.
Replay then counted the actions a candidate flag would change, rather than how
often its condition held. One condition fired on 43\% of eligible games yet
changed 0 of 13,056 decisions; another changed 0 of 13,479. Both had already
consumed a live window. Counting changed actions takes minutes and should precede
any live arm. Replay validates the implementation on logged states; it does not
estimate a policy's value, because a changed action alters the states that
follow.""", "replay")

# --- section 5: evidence labels, seller arm unit and interval (yxm9) --------
edit(r"""Across 30+ interventions and 49 runs, the clearest improvements concerned
implementation repairs and structural policy changes (Appendix
Table~\ref{tab:ledger}). Their evidence types differ; none of the empirical
comparisons alone establishes game-theoretic dominance. Seven consecutive tuning
arms yielded no reliable improvement in the comparisons used. A seller lie-rate
arm also showed no reliable difference across three runs ($t=-0.29$), which does
not establish equivalence.""",
r"""Across 30+ interventions and 49 runs, the clearest improvements concerned
implementation repairs and structural policy changes (Appendix
Table~\ref{tab:ledger}; Table~\ref{tab:register} lists the recorded
interventions, including the null and abandoned ones). Their evidence types
differ; none of the empirical comparisons alone establishes game-theoretic
dominance. From 21 August my shipping rule required a standardized effect of 3
or two agreeing rounds against simultaneous controls, a rule the final-morning
change below broke; hypotheses and cell inclusion rules were not fixed before
outcomes were inspected, so all reported statistics are exploratory. Seven consecutive tuning arms
yielded no reliable improvement in the comparisons used. A seller arm that
raised the rate of recommending low-quality units to 100\% sold 11.13 units per
game against 10.64 for controls at about 40\%, yet across 29 agent-runs, with
push rate and per-game rating change centred within each run, its slope was
$-0.048$ rating points per game per 100 percentage points of push (s.e.\ 0.162,
$t=-0.29$; 95\% interval $-0.37$ to $+0.27$). The interval admits a small gain
or loss, so this does not establish equivalence.""", "section 5 seller arm")

# --- section 6: walk-away rate conditioned on the agent-observable seat -----
edit(r"""\textbf{Observed behavior.} Bargaining settled at median round 2, with 1.5\%
no-deals and mean banked share 0.429. Negotiation walked away in 79.8\% of
untradable seats and agreed in 20--24\% of hidden-value games versus 85--89\%
with complete information. The persuasion buyer bought 17.4 units per game
where buying blind had positive expected value, versus 2.2 where it did not.""",
r"""\textbf{Observed behavior.} Bargaining settled at median round 2, with 1.5\%
no-deals and mean banked share 0.429. In one slot's logs after the walk-away rule
shipped (26--30 August), negotiation walked away in all 1,380 untradable seats in
which it reached a decision turn; the other 324 untradable games ended before it
had one, so the 81.0\% overall rate reflects games that ended first rather than
departures from the rule. Negotiation agreed in 20--24\% of hidden-value games versus 85--89\%
with complete information. The persuasion buyer bought 17.4 units per game
where buying blind had positive expected value ($m\cdot p>1$), versus 2.2 where it
did not.""", "walk-away")

# --- section 7: m.p notation ---------------------------------------------------
edit(r"""matched on horizon type, seat and discount factors; persuasion pools by $mp$,""",
r"""matched on horizon type, seat and discount factors; persuasion pools by $m\cdot p$,""", "mp text")
edit(r"""player 1 & 14 & 0.444 & 0.447 & $mp>1$ & $+24.22$ & $+22.10$ & $+1.31$\\
player 2 & 13 & 0.512 & 0.720 & $mp=1$ & $+2.99$ & $+2.56$ & $+0.56$\\
 & & & & $mp<1$ & $-0.61$ & $+0.18$ & $-2.44$\\""",
r"""player 1 & 14 & 0.444 & 0.447 & $m\cdot p>1$ & $+24.22$ & $+22.10$ & $+1.31$\\
player 2 & 13 & 0.512 & 0.720 & $m\cdot p=1$ & $+2.99$ & $+2.56$ & $+0.56$\\
 & & & & $m\cdot p<1$ & $-0.61$ & $+0.18$ & $-2.44$\\""", "mp table")
edit(r"""the known-horizon second seat, and my negative mean persuasion payoff where
$mp<1$, are consistent""",
r"""the known-horizon second seat, and my negative mean persuasion payoff where
$m\cdot p<1$, are consistent""", "mp text 2")

# --- limitations and conclusion ---------------------------------------------
edit(r"""This is one account, one human participant and a changing competition pool.
The identical-policy experiment does not reset rating history or isolate
matchmaking;""",
r"""This is one account, one human participant and a changing competition pool.
The identical-policy experiment does not reset rating history or isolate
matchmaking, and its split into inherited and accrued dispersion rests on a
fitted rating model;""", "limitations")

edit(r"""The useful finding is narrower than a universal failure of leaderboard
evaluation: substantial rating dispersion occurred without policy changes,
and behavioral audits exposed failures that score summaries alone obscured.""",
r"""The useful finding is narrower than a universal failure of leaderboard
evaluation: substantial rating dispersion occurred without policy changes, most
of it accrued within one window rather than inherited, and behavioral audits
exposed failures that score summaries alone obscured.""", "conclusion")

# --- appendix: standardized statistics are exploratory labels (w8XP) -------
edit(r"""Complete-info ultimatum & Larger demand in a one-round known-surplus seat;
reported $+3.42\sigma$, $n=214$. Acceptance remains an opponent decision.\\
Rung-aware pricing & Two reported live comparisons: $+3.9\sigma$ and
$+4.1\sigma$.\\
Free-clock accept floor & Observed gain $+0.0458$ of pot in 108 games,
reported $7.7\sigma$, with none worse in that cohort. No discounting does not
eliminate termination or rejection risk.\\""",
r"""Complete-info ultimatum & Larger demand in a one-round known-surplus seat;
standardized effect $+3.42$, $n=214$. Acceptance remains an opponent decision.\\
Rung-aware pricing & Two live comparisons with standardized effects $+3.9$
and $+4.1$.\\
Free-clock accept floor & Observed gain $+0.0458$ of pot in 108 games,
standardized effect $7.7$, with none worse in that cohort. No discounting does
not eliminate termination or rejection risk.\\""", "ledger sigma")
edit(r"""reclassification do not establish a common replication standard or
game-theoretic dominance. Standardized statistics are reported as exploratory
effect-to-noise summaries.}""",
r"""reclassification do not establish a common replication standard or
game-theoretic dominance. A standardized effect is an exploratory
effect-to-noise ratio, not a confirmatory significance level.}""", "ledger caption")
edit(r"""also changed from $-3.11\sigma$ to $-0.82\sigma$ to $+3.02\sigma$ when the
minimum-count filter admitted 3, 33 or 44 cells.""",
r"""also changed its standardized effect from $-3.11$ to $-0.82$ to $+3.02$ when
the minimum-count filter admitted 3, 33 or 44 cells.""", "simpson sigma")

# --- appendix: slot identity (yxm9) ------------------------------------------
edit(r"""can make intended and deployed behavior differ. A reference build passing
tests does not establish that every concurrent slot ran that build. Exact
replay is tied to the logged cohort and policy version.""",
r"""can make intended and deployed behavior differ. A reference build passing
tests does not establish that every concurrent slot ran that build. In the
identical-policy experiment of Section~\ref{sec:noise}, all five slots were
deployed from one reference build by a script that sets every flag explicitly
and checks it from inside each slot's own directory before launch. Per-slot
source, configuration and entry-point hashes were not recorded, so slot identity
rests on that procedure rather than on per-slot verification. Exact replay is
tied to the logged cohort and policy version.""", "slot identity")

# --- appendix: intervention register (reviewer yxm9 asked for a ledger of all
#     interventions, including the null ones) -------------------------------
edit(r"""\begin{table}[H]
\centering\small
\caption{Selected complete-information seller cells from a 10,740-game""",
r"""\begin{table}[H]
\centering\footnotesize
\caption{Intervention register, from the change register kept during the
competition and the project notes. It is a historical record, not a validated
ledger: evidence types, units and cohorts differ, no entry was pre-registered,
and the actions an intervention changed were counted only where replay is
listed. Standardized effects are exploratory effect-to-noise ratios.}
\label{tab:register}
\begin{tabular}{@{}p{0.235\linewidth}p{0.255\linewidth}p{0.30\linewidth}p{0.11\linewidth}@{}}
\toprule
Intervention & Evidence (unit, cohort) & Recorded result & Status\\
\midrule
\multicolumn{4}{@{}l}{\emph{Bargaining}}\\
Round-cap accept collapse & Logs, then replay of a run-37 arm & Caught 11 of 11 games that would have hit the zero-payoff cap; the cap was later observed at round 96, not 99 & shipped\\
Final-proposer seat price & Full record, 1,415 games & 91.9\% signed; seat worth 0.507 of pot, not 0.552 & shipped\\
Accept slack 0.97 to 0.99 & Simulator, 14,000 games & Inert within the simulator spread & shipped\\
Free-clock accept floor & Replay, runs 41--42, 1,285 games & $+0.0458$ of pot on 108 refusals, none worse & shipped\\
Settle-early bundle & Unbundled replay & Whole gain came from the accept floor; other knobs added nothing & dropped\\
Bounded-only accept bar & Live arm, then control & $+2.20$ and $+1.61$ became $-0.015$ and $+0.026$ of pot & reverted\\
Lower opening demand & 9,370 games, within-cell & Pays only where a refused round is costly & unchanged\\
Free-delay holds and cap & Simulator; run 37 & Gate opened twice in five hours & unmeasured\\
Counter to sweepers & Run 39, 14 minutes & Drained before a measurement & unmeasured\\
Discounted hold cap & 389 historical refusals & Refusing cost $0.0464$ of pot & built, off\\
\multicolumn{4}{@{}l}{\emph{Negotiation}}\\
Rung-aware pricing & Two live comparisons & Standardized effects $+3.9$, $+4.1$ & shipped\\
Complete-info ultimatum & Live arm, 214 games & Standardized effect $+3.42$ & shipped\\
Stonewall holds to endgame & Run 37, paired within game, 23 games & 12 better, 11 equal, 0 worse & shipped\\
Untradable-seat walk-away & One slot's logs, 26--30 Aug & Walked all 1,380 seats with a decision turn & shipped\\
Late concession, complete info & Replay & Changes 25.5\% of bounded complete-info decisions & armed\\
Hide rung from last word & Run 37 & Close rate halved to 4.2\%; premise was a survivorship artifact & off\\
Midpoint rail & Construction & Cannot bind given the ladder & removed\\
Stonewall respects ultimatum & Construction & Unreachable condition & dead code\\
Known-zone floor & Replay, 13,056 decisions & Changed 0 decisions & inert\\
Rung shade 0.30--0.50 & Fleet-wide, no control & Ratings fell 100--385 points & reverted\\
\multicolumn{4}{@{}l}{\emph{Persuasion}}\\
Negative-signal parser & Re-scoring, 123,700 buyer rounds & 270 purchases reclassified, 258 low quality & shipped\\
Hard-regime rationing & Replay, 13,479 seller turns & Changed 0 decisions & inert\\
Low-quality push to 100\% & 29 agent-runs, centred within run & Slope $-0.048$ (s.e.\ 0.162) & not shipped\\
Lie budget 0.90 and 1.00 & Live arms & No reliable difference & null\\
``Buyers punish lies'' & Observational & Reversed: purchase selection, not punishment & retracted\\
\multicolumn{4}{@{}l}{\emph{Other tuning arms}}\\
Patience floor, accept bar (twice), stall clock, anchor grace, messages off, last-word demand & Live arms against simultaneous controls & None exceeded the control spread & null\\
\bottomrule
\end{tabular}
\end{table}

\begin{table}[H]
\centering\small
\caption{Selected complete-information seller cells from a 10,740-game""", "register table")

# --- appendix: reproducibility manifest for Figure 1 (both reviewers) ------
edit(r"""one-command reproduction. Tables retain their analysis-specific cohorts, and
aggregate counts should not be substituted for the denominators of individual
comparisons.""",
r"""one-command reproduction. Tables retain their analysis-specific cohorts, and
aggregate counts should not be substituted for the denominators of individual
comparisons.

For the identical-policy experiment, a regenerable record needs, per snapshot
and slot, a timestamp, the overall and three family ratings, cumulative games by
family and role, and the deployed source, configuration and entry-point hashes.
The camera-ready release adds the 45 plotted overall ratings and each slot's game
counter and rating at the first and last snapshot
(\texttt{paper/data}). The family-level snapshots behind the
within-family spreads are not part of the release, and deployment hashes were
not recorded.""", "manifest")

# --- review pass approved by the author (items 1-5) -------------------------
# 4. move the weakest main-text diagnostic to the appendix
edit(r"""

\textbf{Exploratory break-even fits.} Regressing rating delta on banked payoff
within a cell supplied diagnostic zero crossings (Appendix
Table~\ref{tab:breakeven}). Slopes were positive in 58 of 64 cells, with median
$R^2=0.60$ and split-half correlation $r=0.741$. These describe regularity in
the logged sample. A root depends on rating history, opponent adjustments and
the reference pool; it is not generally a recovered field median. A fourth
diagnostic estimates aggregate quality among declined persuasion rounds from
the known prior (Appendix~\ref{app:lim}).
""", r"""
""", "move break-even out")
edit(r"""\section{Additional methods and limits}
\label{app:lim}
""", r"""\section{Additional methods and limits}
\label{app:lim}
\textbf{Exploratory break-even fits.} Regressing rating delta on banked payoff
within a cell supplied diagnostic zero crossings (Table~\ref{tab:breakeven}).
Slopes were positive in 58 of 64 cells, with median $R^2=0.60$ and split-half
correlation $r=0.741$. These describe regularity in the logged sample. A root
depends on rating history, opponent adjustments and the reference pool; it is
not generally a recovered field median.

""", "break-even into appendix")

# 5. lighter hedging where a caveat was repeated
edit(r"""made 23,617 refusals informative about acceptance rules, including continuations
ending without agreement. This is a local, retrospective comparison; it does not
identify the value of every alternative policy or prove ex-ante optimality.
Repeated refusals within one game share an outcome.""",
r"""made 23,617 refusals informative about acceptance rules, including continuations
ending without agreement. The comparison is local and retrospective: it does not
value every alternative policy or prove ex-ante optimality, and refusals within
one game share an outcome.""", "terminal acceptance hedge")
edit(r"""100--385 negotiation rating points over five hours. Without a concurrent
untreated control, the full decline cannot be attributed to the parameter alone.
Operationally, the lesson is to retain a control.""",
r"""100--385 negotiation rating points over five hours. With no concurrent control
I cannot attribute the full decline to the parameter; the operational lesson is
to keep one.""", "final morning hedge")
edit(r"""averaged $-6.76$ and summed to about $-541$; the sum is not their persistent
effect on an EMA rating.""",
r"""averaged $-6.76$ and summed to about $-541$; the sum overstates their persistent
effect on an EMA rating (Appendix~\ref{app:measurement}).""", "abandonment hedge")
edit(r"""This is one account, one human participant and a changing competition pool.
The identical-policy experiment does not reset rating history or isolate
matchmaking, and its split into inherited and accrued dispersion rests on a
fitted rating model; exploratory fits and pooled tests do not remove all dependence or
selection. Repeated tuning and flexible cell filters increase the risk of
selective findings. The public repository provides policies, tests and analysis
scripts, but full empirical reproduction requires private game records and
deployment metadata; anticipated organizer data do not by themselves resolve
that gap.""",
r"""This is one account, one human participant and a changing competition pool.
The identical-policy experiment did not reset ratings or isolate matchmaking, and
its split into inherited and accrued dispersion rests on a fitted rating model.
Pooled tests do not remove all dependence, and repeated tuning with flexible cell
filters raises the risk of selective findings. The repository provides policies,
tests and analysis scripts, but full empirical reproduction needs private game
records and deployment metadata that organizer data alone would not supply.

\textbf{Lessons for entrants.} Five practices would have saved most of my wasted
windows. (1)~Replay a candidate change over logged states and count the actions
it changes before giving it a live window. (2)~Run at least three simultaneous
controls: with two, one arm read as a standardized effect of $+2.1$ until a third
control erased it. (3)~Judge a change by outcomes in the cells it can affect, not
by rating movement. (4)~Before trusting a rate, ask what a game must do to enter
its denominator; three of my measurements excluded by construction the cases
that would have contradicted them. (5)~Never pool games across a change; each
version needs its own window.

\textbf{Suggestions for live competitions.} Four changes would make a live
leaderboard more informative: publishing the exact rating update; reporting each
rating with an uncertainty or an effective game count; letting an entrant start
a control slot from a common rating; and exposing per-family game counts and
scores against a fixed reference pool.""", "limitations, lessons, suggestions")
edit(r"""The useful finding is narrower than a universal failure of leaderboard
evaluation: substantial rating dispersion occurred without policy changes, most
of it accrued within one window rather than inherited, and behavioral audits
exposed failures that score summaries alone obscured.
Simultaneous controls, explicit estimands, replay and transcript inspection
provide complementary evidence when live experimental windows are short.""",
r"""The finding is not that leaderboards fail. It is that identical policies ended
tens of rating points apart, mostly through divergence within a single window,
while behavioral audits exposed failures that score summaries hid. When
experimental windows are short, simultaneous controls, explicit estimands,
replay and transcript inspection supply evidence that a rating cannot.""", "conclusion rewrite")

# --- second review pass (independent ChatGPT review, accepted points) -------
edit(r"""In a simultaneous 8.6-hour comparison, five slots
running the same policy each played about 3,000 games.""",
r"""In a simultaneous 8.6-hour comparison, five slots
deployed from the same reference build each played about 3,000 games.""", "r2 abstract build")
edit(r"""and the slot that started last finished first. Under a simplified rating model,
at most 6--21 points of the starting gap should have persisted, so most of the
terminal spread accrued during the window; separating matchmaking, sampling and a
changing reference pool would still require reset ratings.""",
r"""and the slot that started last finished first. Under a fitted rating model and
assumed game counts, only 6--21 points of the starting gap would persist, which
suggests that most of the terminal spread accrued during the window; matchmaking,
sampling and changes in the reference pool remain unresolved.""", "r2 abstract model")
edit(r"""Here, five simultaneous identical-policy controls reveal rating dispersion in a
live competition that is large relative to the effects of tuning, and offline
audits distinguish changed behavior from changes that never affected an action.""",
r"""Here, five simultaneous identical-policy controls reveal rating dispersion in a
live competition, and offline audits distinguish interventions that changed
logged decisions from those that left every decision unchanged.""", "r2 intro")
edit(r"""A seller holding the top rung, or a buyer holding
the bottom one, has no possible counterparty. The agent can see this from its own
value alone,""",
r"""For a seller holding the top rung, or a buyer holding
the bottom one, no counterparty value permits a strictly profitable trade. The
agent can see this from its own value alone,""", "r2 untradable")
edit(r"""All five ran the same policy
(Appendix~\ref{app:lim} describes how far that identity was verified)""",
r"""All five were deployed from the same reference build
(Appendix~\ref{app:lim} describes how far that identity was verified)""", "r2 sec3 build")
edit(r"""Measured from each slot's own start (Figure~\ref{fig:noise}b), the
five gained between $+39$ and $+167$ points; the slot that started lowest
finished highest, every slot led at least one snapshot, and the 45 snapshots
showed 31 distinct orderings of the five. Within single families the spread
reached 292.9 points.""",
r"""Measured from each slot's own start (Figure~\ref{fig:noise}b), the
five gained between $+38.8$ and $+166.9$ points, so their gains ended 128.1
points apart after peaking near 135; the slot that started lowest finished
highest, every slot led at least one snapshot, and the 45 snapshots showed 31
distinct orderings of the five. Within single families the spread reached 292.9
points. The polls recorded each slot's family ratings and total game counter; I
did not retain per-family or per-role game counts.""", "r2 sec3 gains")
edit(r"""\caption{Five slots running the same policy, polled together 45 times over 8.6
hours.""",
r"""\caption{Five slots deployed from the same reference build, polled together 45
times over 8.6 hours.""", "r2 caption build")
edit(r"""B$_1$--B$_5$ started at 2204,
2205, 2263, 2200 and 2177 (spread 85.3) and ended at 2299, 2302, 2302, 2321 and
2344 (spread 45.8).""",
r"""B$_1$--B$_5$ started at 2203.9,
2204.5, 2262.7, 2200.1 and 2177.4 (spread 85.3) and ended at 2298.5, 2301.8,
2301.5, 2321.0 and 2344.3 (spread 45.8).""", "r2 caption decimals")
edit(r"""Applied to Figure~\ref{fig:noise}, the model separates inherited from accrued
dispersion. If each slot's games split evenly across families, about 1,000 per
family, between 7\% and 25\% of each starting offset should persist (for 1,300
down to 700 family games), which is 6--21 points of the 85.3-point gap.
Subtracting each slot's modelled residual from its final rating leaves a
49--64-point spread, so most terminal dispersion accrued during the window.""",
r"""Applied to Figure~\ref{fig:noise}, the model separates inherited from accrued
dispersion. With $\bar R(0)$ the five slots' mean starting rating and
$\lambda=(1-\eta)^n$ the share of an offset that survives $n$ family games, I
compute each slot's adjusted final rating $R_i(T)-\lambda\,[R_i(0)-\bar R(0)]$.
Taking about 1,000 games per family as an illustrative equal split and varying it
from 700 to 1,300, $\lambda$ falls from 25\% to 7\%: 6--21 points of the
85.3-point starting gap would persist, and the adjusted final ratings span
49--64 points, so most terminal dispersion accrued during the window. These are
scenarios rather than observed exposures, and the adjusted and observed spreads
are not additive components.""", "r2 decomposition formula")
edit(r"""An available offer can be evaluated
exactly at its decision point: accepting banks
$\mathrm{share}\,\delta^{r-1}$.""",
r"""An available offer can be evaluated
exactly at its decision point: accepting a share $s$ in round $r$ banks
$s\,\delta^{r-1}$.""", "r2 acceptance notation")
edit(r"""One condition fired on 43\% of eligible games yet
changed 0 of 13,056 decisions; another changed 0 of 13,479.""",
r"""A known-zone floor fired on 43\% of eligible negotiation
games yet changed 0 of 13,056 decisions, and hard-regime rationing changed 0 of
13,479 seller decisions.""", "r2 replay names")
edit(r"""Across 30+ interventions and 49 runs, the clearest improvements concerned
implementation repairs and structural policy changes (Appendix
Table~\ref{tab:ledger}; Table~\ref{tab:register} lists the recorded
interventions, including the null and abandoned ones).""",
r"""Across 30+ interventions and 49 runs, I obtained the clearest diagnostic
evidence for implementation repairs and structural policy changes (Appendix
Table~\ref{tab:ledger}); Table~\ref{tab:register} records these alongside the
null, abandoned and retracted interventions.""", "r2 sec5 opening")
edit(r"""outcomes were inspected, so all reported statistics are exploratory.""",
r"""outcomes were inspected, so all reported statistics are exploratory. A
standardized effect here is an estimated difference divided by its estimated
standard error on the unit listed for it, without adjustment for dependence or
multiple comparisons.""", "r2 define standardized effect")
edit(r"""A seller arm that
raised the rate of recommending low-quality units to 100\% sold 11.13 units per
game against 10.64 for controls at about 40\%, yet across 29 agent-runs, with
push rate and per-game rating change centred within each run, its slope was
$-0.048$ rating points per game per 100 percentage points of push (s.e.\ 0.162,
$t=-0.29$; 95\% interval $-0.37$ to $+0.27$).""",
r"""A seller arm that
raised the rate of recommending low-quality units to 100\% sold 11.13 units per
game against 10.64 for controls at about 40\%. Rating did not follow: regressing
per-game rating change on push rate across 29 agent-runs, one observation per
slot per run with both centred within each run, gave a slope of $-0.048$ rating
points per game per 100 percentage points of push (OLS s.e.\ 0.162, which ignores
dependence among slots in a run; $t=-0.29$; 95\% interval $-0.37$ to $+0.27$).""", "r2 seller arm")
edit(r"""123,700 buyer rounds reclassified 270 purchases, 258 of them low quality.
Another transcript exposed an acceptance gate opening at round 97 in negotiations
that terminated at 96.""",
r"""123,700 buyer rounds reclassified 270 purchases, 258 of them low quality; this
reclassifies recorded purchases and does not estimate what deploying the corrected
parser earned. Another transcript exposed an acceptance gate opening at round 97
in open-horizon games that the server ended at round 96.""", "r2 parser chain")
edit(r"""In one slot's logs after the walk-away rule
shipped (26--30 August), negotiation walked away in all 1,380 untradable seats in
which it reached a decision turn; the other 324 untradable games ended before it
had one, so the 81.0\% overall rate reflects games that ended first rather than
departures from the rule.""",
r"""In one slot's logs after the walk-away rule
shipped (26--30 August), negotiation walked away in all 1,380 untradable games
that reached its decision turn. Another 324 ended earlier, giving an overall rate
of 81.0\% with no observed departure from the rule.""", "r2 walk-away")
edit(r"""The reference snapshot passed them; the final-night working
tree, carrying experimental flags, failed 27.""",
r"""The reference snapshot passed all 472; a different software
state, the final-night working tree carrying experimental flags, failed 27.""", "r2 tests")
edit(r"""403 of 469 seller games reached a round-10 agreement at low
surplus (Appendix Table~\ref{tab:endgame}).""",
r"""403 of 469 seller games reached a round-10 agreement, banking a
mean 0.0433 of buyer value (Appendix Table~\ref{tab:endgame}).""", "r2 endgame metric")
edit(r"""The finding is not that leaderboards fail. It is that identical policies ended
tens of rating points apart, mostly through divergence within a single window,""",
r"""The finding is not that leaderboards fail. It is that slots deployed from one
reference build ended tens of rating points apart, with most of that gap opening
within a single window under the fitted model,""", "r2 conclusion qualifier")
edit(r"""as low as 0.118 in the known-horizon player-1 regime. It is distinct from the
exact-replay cohorts reported in the main text.}""",
r"""as low as 0.118 in the known-horizon player-1 regime. It is distinct from the
exact-replay cohorts reported in the main text. Differences are computed before
rounding.}""", "r2 table A3 rounding")
edit(r"""Free-clock accept floor & Observed gain $+0.0458$ of pot in 108 games,
standardized effect $7.7$, with none worse in that cohort.""",
r"""Free-clock accept floor & Mean gain $+0.0458$ of pot over 108 refusals in a
1,285-game replay, standardized effect $7.7$, with none worse.""", "r2 table A4 unit")
edit(r"""& $+0.0458$ of pot on 108 refusals, none worse &""",
r"""& Mean $+0.0458$ of pot over 108 refusals, none worse &""", "r2 table A5 unit")
edit(r"""Lie budget 0.90 and 1.00 & Live arms & No reliable difference & null\\
``Buyers punish lies'' & Observational & Reversed: purchase selection, not punishment & retracted\\
\multicolumn{4}{@{}l}{\emph{Other tuning arms}}\\
Patience floor, accept bar (twice), stall clock, anchor grace, messages off, last-word demand & Live arms against simultaneous controls & None exceeded the control spread & null\\""",
r"""Lie budget 0.90 and 1.00 & Live arms & The lever moved less than the control spread & null\\
``Buyers punish lies'' & Observational & Explained by purchase selection; buyer responses not separately identified & retracted\\
\multicolumn{4}{@{}l}{\emph{Other tuning arms (live arms against simultaneous controls)}}\\
Patience floor & Live arm & Clamped downstream to a 2-point move & null\\
Accept bar, two arms & Live arms & Within the control spread & null\\
Stall clock & Live arm & Within the control spread; counts not recorded & null\\
Anchor grace & Live arm & Within the control spread; counts not recorded & null\\
Bargaining messages off & Live arm & Within the control spread; counts not recorded & null\\
Last-word demand & Live probe & Acceptance flat: 94.8\% at 0.97 against 90.2\% at 0.90 & null\\""", "r2 table A5 tuning rows")
edit(r"""within-family spreads are not part of the release, and deployment hashes were
not recorded.""",
r"""within-family spreads are not part of the release, and deployment hashes were
not recorded. The server's exact update rule was not available to me; the API
reports each game's rating change, from which a target $g_t$ can be backed out
only under an assumed $\eta$. Matching the five slots on configuration, role and
opponent strength would need every slot's per-game records, and the turn logs I
retained cover one slot, so the comparison in Section~\ref{sec:noise} stays
descriptive.

\textbf{Cohorts.} Analyses draw on different records, and a count from one
should not serve as a denominator for another: 264,432 unique games in the
fleet's turn logs (Table~\ref{tab:volume}); 120,023 games joined to their rating
deltas (the delta calculations above); 109,881 rated games in the account's
history feed, which also covers games without a completed final turn
(abandonment); 6,185 buyer replays holding 123,700 rounds (parser re-scoring and
Table~\ref{tab:ladder}); and the persuasion purchases behind
Table~\ref{tab:human}.""", "r2 appendix D availability and cohorts")

out = src
for old, new, label in EDITS:
    count = out.count(old)
    if count != 1:
        raise SystemExit(f"[{label}] expected exactly one match, found {count}")
    out = out.replace(old, new)

(HERE / "glee_competition_paper.tex").write_text(out, encoding="utf-8")
print(f"applied {len(EDITS)} edits")
