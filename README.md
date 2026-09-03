# 7aidara_Gamma — a deterministic GLEE Competition agent

The agent I entered in the [GLEE Competition](https://glee-competition.com)
(NeurIPS 2026, IAB workshop), and the code behind the workshop paper
**"Below the Noise Floor: A Deterministic GLEE Agent and the Measurement
Problem It Exposed"** ([`paper/`](paper/)).

It finished **6th of the agent track** over 264,432 games. I also played the
human track by hand and finished **2nd**; the paper uses that as a same-author
human baseline, since both tracks draw from one shared opponent pool.

There is no language model in it. The three policies are 2,299 lines of Python
(858 bargaining, 660 negotiation, 781 persuasion) behind 114 parameters, with
another 1,700 lines of dispatcher, safety layer, state readers, and logging
around them, and 472 behavioural tests over the lot. No learning anywhere.
That was a deliberate choice, and the paper argues it was the right
one — a deterministic agent replays a logged game to exactly the same
decisions, which is what made offline evaluation possible once it became clear
the leaderboard could not measure anything at the effect sizes involved.

## Layout

| Path | What it is |
| --- | --- |
| [main.py](main.py) | CLI entry point: builds the client, runs the loop, leaves the queue |
| [glee_agent/dispatcher.py](glee_agent/dispatcher.py) | The one function `client.run()` calls; routes by `game_family` |
| [glee_agent/strategies/](glee_agent/strategies/) | One module per family, each exposing `play(game) -> action` |
| [glee_agent/params.py](glee_agent/params.py) | Every strategy tunable, in one file |
| [glee_agent/safety.py](glee_agent/safety.py) | `sanitize` repairs outgoing moves; `fallback` covers a crash |
| [glee_agent/gamestate.py](glee_agent/gamestate.py) | Readers over the filtered `game_state` the server sends |
| [glee_agent/gamelog.py](glee_agent/gamelog.py) | Append-only JSONL record of every decision |
| [tests/](tests/) | 472 strategy tests against synthetic games — no network, no SDK needed |
| [tools/](tools/) | Setup check, per-game transcript reader, post-mortem analysis |
| [paper/](paper/) | The paper, its LaTeX sources, and the analysis scripts behind every number |
| [paper/change-register.html](paper/change-register.html) | Every change considered across the competition: what it did, whether it was tested, and what came back |

Only `main.py` and `tools/check_setup.py` import `glee_sdk`, so the strategies
and their tests run without the SDK installed.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env        # then paste your key into it
python tools/check_setup.py   # verifies the key, plays nothing
```

`check_setup.py` calls `GET /api/agent/stats`, which is not competition-gated,
so it proves the key and the connection without entering a queue.

## Running

```powershell
python main.py                                   # all three families
python main.py --families bargaining negotiation # a subset
python main.py --concurrency 8 --max-games 50    # bounded session
python -m pytest                                 # the 472 tests
```

Stop with Ctrl-C. The queue is left explicitly on the way out: a stale queue
entry still gets matched, and that game then times out and dents the rating.
Every turn is appended to `logs/turns-<date>.jsonl`.

## Reading a game back

There is no spectator page, but the platform keeps the full transcript of every
game — including ones still running — on `GET /api/agent/games/{id}`, and
[show_game.py](tools/show_game.py) renders it:

```powershell
python tools\show_game.py --list          # every game played
python tools\show_game.py --list --live   # only games in progress
python tools\show_game.py c8cf3c48        # full transcript; an id prefix is enough
```

That prints each offer, each message, and each accept or reject with both
sides' payoffs, which is where a losing game explains itself. Two of the
paper's most valuable findings came from reading these rather than aggregates.

## What the strategies do

Payoff is scored as a percentile against the field on the *same configuration
in the same role*, adjusted for opponent strength. Two consequences shape every
decision. A $0 no-deal sits at the bottom of that scale, so closing a mediocre
deal beats holding out and missing. And configurations are drawn from a grid of
960 combinations, so nothing may be tuned to one game's numbers: the policies
are written in terms of the pot, the horizon, and the valuations, never in
absolute dollars.

**Bargaining** anchors on the infinite-horizon (Rubinstein) share, which is what
actually measures bargaining power — the patient player earns more. It opens
above that, concedes toward it as the horizon closes, and never concedes below a
floor the field will realistically sign. The finite-horizon recursion is
computed exactly in `proposer_share` but deliberately not used as the live
anchor: it swings between roughly 0.25 and 0.91 with the parity of the horizon,
which is correct only against an opponent playing the same equilibrium. The last
two rounds are handled explicitly instead. It never walks away, because walking
away pays exactly $0.

**Negotiation** prices at tradable rungs rather than guessing a reservation
price. Sorting every valuation the server dealt me showed they are not
continuous but drawn from three fixed four-rung pools — which the documentation
does not state — so my own value pins the whole ladder. When the game is
complete-information the zone of agreement is known exactly and it opens just
inside the opponent's limit; when the seller values the item above the buyer
there is no such zone, and it walks immediately, which is both the right outcome
and a freed concurrency slot.

**Persuasion** gives the seller an explicit credibility budget. Bayesian
persuasion says exactly what fraction of low-quality products can be recommended
before a rational buyer stops believing recommendations. The seller spends under
that budget and ramps up as rounds run out, because reputation is only worth
holding while there is a future to spend it in. The buyer tracks how often
recommendations actually delivered as a Beta posterior anchored on the prior,
counting only rounds it bought — quality is hidden otherwise — and buys on a
marginal expectation in the first rounds, because that purchase is the only way
to price the rest of the game.

## Platform behaviour worth knowing

None of this is documented; all of it was recovered from play, and the paper
treats that as a finding in its own right.

- **Rating decay.** Above 1,800 an agent needs 100 games per family in the
  trailing 48 hours or the rating bleeds hourly. Top-100 agents owe 10 games per
  day per family. Both are volume requirements: plan on long sessions.
- **Ratings freeze when idle.** A rating only moves on a finished game, which
  makes the end of the competition a stopping problem rather than a playing one.
- **Display versus raw rating.** `stats()` returns the rating shrunk toward
  1,000 by `g / (g + 30)`. A raw 1,400 over 5 games shows as about 1,057. It is
  not a bug and it converges.
- **Crash-loop cooldown.** Three consecutive games lost to your own turn timeout
  blocks queue joins for 30 minutes. `safety.py` exists to make that
  unreachable; no game in 264,432 was lost to an exception.
- **Rate limit.** 60 requests/minute per agent. Raise `--concurrency` rather
  than dropping `--poll-interval` for more throughput.
- **Open-horizon games are not open.** Games sold as unlimited stop at a round
  cap that pays *both* sides nothing.

## Tuning, and why there is so little of it

[params.py](glee_agent/params.py) holds every knob, so a tuning experiment is a
one-file diff. It is also the part of this repository I would most warn against
reusing as a template. The paper's central finding is that across 30+
interventions and 49 runs, only *strictly dominated* fixes ever replicated;
every parameter-tuning arm I ran measured nothing but noise. Separating two
policies that differ by 0.25 rating points per game at 3 sigma needs roughly
5,600 to 6,700 games per arm, which was more than a full run's budget.

The turn logs are the evidence base, and they are also what the required "Agent
Behavior Analysis" section is written from. That is why the persuasion seller's
randomisation is seeded from the game id and round rather than a global RNG: a
logged game replays to the same decisions.

## Data

`logs/` and the history exports are excluded from this repository. They contain
other competitors' game transcripts and messages alongside my own.
[paper/analysis/README.md](paper/analysis/README.md) documents what each
analysis script computes and the shape of the input it expects, so the method is
auditable even though the data cannot ship.

This is a gap with an end date: the competition organizers have said they will
release the full game record for every agent, so once that happens the
underlying data can be obtained from them directly rather than from me, for the
whole field rather than for one account.

## License

MIT for the code. The paper and the change register stay my copyright. See
[NOTICE](NOTICE) for exactly which files fall under which.
