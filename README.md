# GLEE Competition agent

An agent for the [GLEE Competition](https://glee-competition.com) agent track:
one strategy module per game family, a dispatcher that routes each incoming game
to the right one, and a safety layer that guarantees we never forfeit a game to a
bug.

## Setup

Python is not installed on this machine yet. Install it once:

```powershell
winget install Python.Python.3.12
```

Then, from this directory, in a new terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env      # then paste your key into .env
python tools/check_setup.py      # proves the key works, plays nothing
```

`check_setup.py` calls `GET /api/agent/stats`, which is not competition-gated,
so it verifies the key and the connection without entering a queue.

## Running

```powershell
python main.py                                   # all three families
python main.py --families bargaining negotiation # a subset
python main.py --concurrency 8 --max-games 50    # bounded session
```

Stop with Ctrl-C. The queue is left explicitly on the way out — a stale queue
entry still gets matched, and that game times out and dents the rating.

Every turn is appended to `logs/turns-<date>.jsonl`.

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
| [tools/check_setup.py](tools/check_setup.py) | Verify key and connectivity without playing |
| [tests/](tests/) | Strategy tests against synthetic games — no network, no SDK needed |

Only [main.py](main.py) and [tools/check_setup.py](tools/check_setup.py) import
`glee_sdk`, so the strategies and their tests run before the SDK is installed.

```powershell
python -m pytest
```

## What the strategies do

Everything below is scored the same way: the payoff becomes a percentile against
the field on the *same configuration in the same role*, adjusted for opponent
strength. Two consequences shape every decision here. A $0 no-deal sits at the
bottom of that scale, so closing a mediocre deal beats holding out for a good one
and missing. And configurations are drawn from a grid of 960 combinations, so
nothing may be tuned to one game's numbers — the policies are written in terms of
the pot, the horizon, and the valuations, never in absolute dollars.

**Bargaining** anchors on the infinite-horizon (Rubinstein) share, which is what
actually measures bargaining power: the patient player earns more. It opens above
that, concedes toward it as the horizon closes, and never concedes below a floor
the field will realistically sign. The finite-horizon recursion is computed
exactly in `proposer_share` but deliberately not used as the live anchor — it
swings between roughly 0.25 and 0.91 with the parity of the horizon, which is
correct only against an opponent playing the same equilibrium. The last two
rounds are handled explicitly instead. It never walks away, because walking away
pays exactly $0.

**Negotiation** runs a concession schedule from an anchor toward a thin margin,
clipped so it never prices below our own valuation and never un-concedes. When
the game is complete-information, the zone of agreement is known exactly, so it
opens just inside the opponent's limit instead of guessing; when the seller
values the item above the buyer there is no such zone, and it walks away
immediately — the right outcome, and a freed concurrency slot.

**Persuasion** gives the seller an explicit credibility budget: Bayesian
persuasion says exactly what fraction of low-quality products can be recommended
before a rational buyer stops believing recommendations. It spends under that
budget, ramps up as rounds run out because reputation is only worth holding while
there is a future to spend it in, and recommends everything on the final round.
The buyer tracks how often recommendations actually delivered as a Beta posterior
anchored on the prior, counting only rounds it bought — quality is hidden
otherwise — and buys on a marginal expectation in the first rounds, because that
purchase is the only way to price the rest of the game.

## Tuning

[params.py](glee_agent/params.py) holds every knob, so a tuning experiment is a
one-file diff. The turn logs are the evidence: they are also what the workshop
paper's required "Agent Behavior Analysis" section is written from, which is why
the persuasion seller's randomisation is seeded from the game id and round rather
than a global RNG — a logged game replays to the same decisions.

## Operational notes

- **Rating decay.** Above 1,800 an agent needs 100 games per family in the
  trailing 48 hours or the rating bleeds hourly. Top-100 agents owe 10 games per
  day per family. Both are volume requirements: plan on long sessions, not short
  ones.
- **Display vs. raw rating.** `stats()` returns the rating shrunk toward 1,000 by
  `g / (g + 30)`. A raw 1,400 over 5 games shows as ~1,057. It is not a bug and
  it converges.
- **Crash-loop cooldown.** Three consecutive games lost to our own turn timeout
  blocks queue joins for 30 minutes. `safety.py` exists to make that unreachable.
- **Rate limit.** 60 requests/minute per agent. Raise `--concurrency` rather than
  dropping `--poll-interval` when you want more throughput.

## Not built yet

- A local self-play harness. Tuning currently costs real games; a faithful local
  engine for the three families would let the schedules be searched offline.
- An LLM strategy. The dispatcher takes any callable, so an LLM-backed family
  drops in beside the rule-based ones — with the same `sanitize`/`fallback`
  guarantee around it.
- Opponent modelling across games. The turn logs carry the opponent name in the
  half of games where identity is disclosed, which is the raw material for it.
