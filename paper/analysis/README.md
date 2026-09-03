# Analysis scripts

Every number in the paper was produced by one of these scripts. Each is short
and single-purpose, so a reader can check the arithmetic behind a claim without
reading a framework.

## A note on the data

**These scripts do not run out of the box, and that is a real limitation.**
They read two private inputs:

| Symbol | What it is | Why it is not here |
| --- | --- | --- |
| `J` | `joined.jsonl` — 120,023 completed games joined to their per-game rating deltas | Built from `logs/turns-*.jsonl` plus the platform's results feed. Carries other competitors' transcripts and messages alongside my own. |
| `S` | a directory of `human_*.json` exports | My own human-track game history, pulled from the platform's history endpoint. |

So the scripts document *how* each number was computed and let a reader audit
the method, but they are not a one-command reproduction. Section 8 of the paper
states this. Anyone with their own GLEE logs can rebuild `J` in the same shape:
one JSON object per line, per game, carrying the configuration, the banked
share, and the rating delta.

The competition organizers have said they will publish the full game record for
every agent. Once that release happens it supersedes anything I could have
included here: it covers the entire field rather than one account, and it comes
from the party that actually ran the games.

## What each script produces

### The measurement problem (Section 3)

| Script | Produces | Paper location |
| --- | --- | --- |
| `noise.py` | Whether the spread across five byte-identical builds exceeds sampling error | Section 3, Appendix Figure A1 |
| `power.py` | `sd(rd)` per family and the sample a 3-sigma two-arm test needs | Section 3 (4.84 / 4.42 / 4.44; 6,743 / 5,632 / 5,689 per arm) |
| `percentile.py` | The final board re-expressed as the payoff percentile it is a transform of | Section 3 (ranks 3-7 span 0.41 percentile points) |

### Measuring without the leaderboard (Section 4)

| Script | Produces | Paper location |
| --- | --- | --- |
| `breakeven.py` | The break-even estimator: recovers the field-median outcome from `rating_delta` alone | Section 4(C), Appendix Table A3 |
| `validate.py` | Validation of that estimator, plus the field-versus-Rubinstein-SPE comparison | Section 4(C) (58/64 cells, median R-squared 0.60, split-half r = 0.741), Appendix Table A4 |

### What worked and what failed (Section 5)

| Script | Produces | Paper location |
| --- | --- | --- |
| `parserbug.py` | Reproduces the message-parser defect and prices the fix against both hint lists | Section 5 |
| `parser2.py` | Re-scores all 123,700 logged buyer rounds across three successive hint lists | Section 5 (270 purchases re-classified, 258 low quality) |
| `nego_pers.py` | Negotiation rating-per-game split by horizon, information, and role | Section 6(4), Appendix Table A6 |
| `timeouts.py` | First pass at abandonment cost, from the turn logs | superseded by `timeouts2.py` |
| `timeouts2.py` | Abandonment cost from the raw history feed, which keeps the games the turn logs never finished | Section 5 (80 of 109,881 games at -6.76 rd) |
| `timeouts3.py` | Splits that cost into transient versus persistent under the EMA | Section 5 (persistent shift about 0.5 points) |

`timeouts.py` is kept deliberately rather than deleted as superseded. It reads
only the turn logs, which never record a final turn for a game that was
abandoned, so its sample silently excludes much of what it was trying to
measure. `timeouts2.py` exists because of that, and goes to the raw history
feed instead. The pair is a worked instance of the sampling failure Section 4
warns about, so keeping the wrong version is part of the evidence.

### The human baseline (Section 7)

| Script | Produces | Paper location |
| --- | --- | --- |
| `human.py` | How the human track was played, measured against the agent's own games | Section 7 |
| `human2.py` | The paired within-game counterfactual for human versus agent, across all three families | Section 7 (bargaining seat 0.512 vs 0.720) |
| `table_human.py` | The bargaining half of Table 1: banked share by horizon and seat | Table 1 (left) |
| `pers_check.py` | Human buyer hit rate on purchases | Section 7 (0.738 over 2,745 rounds) |
| `pers_cmp.py` | What the persuasion buyer's payoff is worth in rating, per cell | Section 7 |
| `pers_pool.py` | The persuasion half of Table 1, pooled by whether buying blind pays (`m*p` versus 1) | Table 1 (right), including the t = -2.44 discipline result |

## Invocation

Scripts taking `J` take it as the first argument; scripts taking `S` take the
directory first, then `J`:

```powershell
python analysis/power.py       path\to\joined.jsonl
python analysis/pers_pool.py   path\to\human_exports\ path\to\joined.jsonl
```

`parser2.py` and `parserbug.py` import the shipped agent so they re-score
against the real hint list rather than a copy. They resolve the repository root
relatively, so they work from any working directory.
