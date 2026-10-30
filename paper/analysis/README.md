# Analysis scripts and reproducibility

These scripts support inspection of the methods; full reproduction of the
reported results requires the private inputs described below.
Read [audit notes](../AUDIT_NOTES.md) before comparing new outputs with the paper.

## Inputs

All examples are run from the repository root. Paths can be absolute.
No API key or network request is needed for analysis.

| Name | Format and meaning |
| --- | --- |
| `J` | UTF-8 JSONL, one completed agent-game record per line: `fam`, `agent`, `ts`, `rd`, `slot`, `role`, `my_pay`, `price`, `my_share`, `d_us`, `d_them`, `hk`, `max_rounds`, `m`, `p`, `buys`, `outcome` as applicable. Shares/payoffs must use the submitted analyses' banked, discounted definitions. |
| `S` | Directory of private JSON exports. `human_persuasion.json`, `human_replays.json`, `human_replays_rand.json`, `human_barg_recent.json` map IDs to game objects; `human_hist_full.json` is a list. Game objects carry `config`, `state`, `your_player`, `moves`, `result`. |
| `B` | Buyer-replay JSONL: each game has a `history` list with `seller_message`, `bought`, `quality`; `m` and `p` identify a cell where available. This is a distinct cohort, not J. |
| `H` | Finalized raw history JSON, list or ID-keyed mapping, including timeouts; fields include `game_id`, `your_player`, `your_player_type`, `rating_delta`, `completed_at`, `result.outcome`. Conflicting overlapping snapshots are rejected. |
| `L` | Directory of one slot's turn logs, `turns-YYYYMMDD.jsonl`, as written by the agent's logger (private; contains opponents' moves). |
| `P` | Original simultaneous-poll CSV: `elapsed_hours,agent,overall`; optionally `bargaining,negotiation,persuasion`. Every timestamp must contain the same agent set. Deployment identity must be established separately. |

J's refusal analysis additionally requires `faced` entries
`[round, nominal_share, action]`. The raw exports' `moves` must distinguish
offer rounds and results. Keep private inputs outside the repository.

## Runnable without private data

```sh
python paper/analysis/noise.py
python paper/analysis/percentile.py
python paper/submitted/build.py --check
python paper/build.py --check
python -m pytest tests/test_paper_analysis.py
```

`noise.py` reads the rounded coordinates in `../submitted/fig_noise.tex`, calibrates
their axes, and reports approximate initial/mean/max/final spreads. Compiling
the submitted TikZ source reproduces the figure. This is **not** recovery of the
original polling dataset, and does not validate the family maximum or game counts.

```sh
python paper/analysis/noise.py --snapshots /private/polls.csv
python paper/analysis/noise.py --snapshots /private/polls.csv --metric bargaining
```

## Commands requiring private inputs

| Script and invocation | Output and limitation |
| --- | --- |
| `python paper/analysis/power.py J` | Rating-delta SD and an idealized IID sample-size illustration; not power or policy-strength validation. |
| `python paper/analysis/breakeven.py J` | OLS roots and IID bootstrap diagnostics as JSON on stdout; no root-range filtering. Optional `--output NEW.json` refuses to overwrite an existing file. |
| `python paper/analysis/validate.py J` | Slopes, R-squared, chronological split-half correlations and all exclusions; includes the historical root filter for comparison. |
| `python paper/analysis/nego_pers.py J` | Observational negotiation/persuasion summaries and calendar-day bargaining spread. Not Figure 1's simultaneous poll analysis. |
| `python paper/analysis/parserbug.py B` | Final hint-list reclassification with high/low/unknown quality among selected purchases; not deployed utility gains. |
| `python paper/analysis/parser2.py B` | Three hint-list versions and selected-purchase quality; no counterfactual unseen trajectory. |
| `python paper/analysis/timeouts.py J` | Diagnostic of joined-log coverage; cannot measure omitted abandoned games. |
| `python paper/analysis/timeouts2.py H [H ...]` | Deduplicated raw-history outcome counts and recorded deltas. |
| `python paper/analysis/timeouts3.py H [H ...]` | Timeout-only count, recorded delta sum and clock-hour clustering. No persistent-cost estimate. |
| `python paper/analysis/human.py S J` | Observational human-game summaries; shared historical configuration cells, not matched opponents/times. |
| `python paper/analysis/human2.py S J` | Best discounted forgone-offer comparisons with explicit ties; additional observational summaries. |
| `python paper/analysis/table_human.py S J` | Bargaining half of Table 1; equally weighted shared cells, requiring >=25 human and >=100 agent games per cell. |
| `python paper/analysis/pers_check.py S` | Purchase-conditioned human quality and missing-quality counts. |
| `python paper/analysis/pers_cmp.py S J` | Observational cell-level persuasion means. Requires only `human_persuasion.json` within S. |
| `python paper/analysis/pers_pool.py S J` | Table 1 persuasion means, per-row n and descriptive Welch-form t; missing payoffs are excluded. |
| `python paper/analysis/pers_pool.py S J --buyer-replays B` | The same table plus separate agent purchase-quality counts. |
| `python paper/analysis/walkaway.py L 20260826 20260830` | Section 6 walk-away counts in untradable seats (seat defined as in `glee_agent/strategies/negotiation.py`), split into walked, no decision turn, accepted and other. One slot only. |

`human.py` and `human2.py` use all five named S exports;
`table_human.py` uses the three bargaining replay mappings.
The shorthand J/S/B/H in the table must be replaced with real paths.

Historical bargaining keys match horizon type, seat and discount factors, not
the exact known round limit. Persuasion's pooled regimes use a tolerance:
`mp < .995`, `.995 <= mp < 1.005`, and `mp >= 1.005`.
Those groupings are disclosed, not advertised as exact controlled matching.
No displayed t or bootstrap interval accounts for all time/opponent dependence.

## Missing links in the evidence chain

The public release does not include the original joined-log builder, all
decision-replay reconstruction code, a complete 49-run ledger, raw rating polls,
or private transcripts. The historical aggregate JSON in `../data/breakeven_legacy_diagnostics.json` predates
these corrections. Tests check code on synthetic cases, not empirical results.
Organizer data availability, if it changes, must be checked rather than assumed.
