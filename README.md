# 7aidara_Gamma — GLEE competition agent and paper

The paper was accepted as a Spotlight in the competition track of the IAB
workshop at NeurIPS 2026.

[Read the camera-ready paper](paper/camera_ready/glee_competition_paper_camera_ready.pdf) ·
[What changed after review](paper/camera_ready/README.md) ·
[Read the submitted paper](paper/glee_competition_paper.pdf) ·
[Paper sources and build](paper/README.md) ·
[Analysis instructions](paper/analysis/README.md) ·
[Audit notes](paper/AUDIT_NOTES.md)

The agent finished sixth in the GLEE agent track; the author finished second in
the human track. The development fleet logged 264,432 games across multiple
builds, not all on the single ranked slot. The paper is an observational case
study of rating dispersion and behavioral auditing, not a proof that leaderboard
evaluation generally fails or that a deterministic agent is universally better.

The submitted PDF's checksum is recorded in
[submission.json](paper/submission.json). Analysis methods and data availability
are described in the accompanying documentation.

## Agent

The agent calls no language model. Python policies handle bargaining,
negotiation and persuasion, with deterministic within-game state updates and
game-ID-seeded seller randomization. Parameters were tuned during development;
“no language model” does not mean no adaptation or no empirical tuning.

- Bargaining uses a Rubinstein-inspired anchor, empirical floors and endgame
  rules. The infinite-horizon formula is not an equilibrium prediction for
  every finite-horizon seat, and reaching the last proposal does not guarantee acceptance.
- Negotiation uses the observed discrete valuation ladder and known surplus
  where available. A 37.5% positive-surplus rate requires independent uniform
  draws on the four-rung pool; independence of role assignment alone is insufficient.
- Persuasion combines a commitment-inspired seller threshold heuristic with
  a buyer's message parsing and within-game outcomes. GLEE's lack of commitment
  prevents a general Bayesian-persuasion optimality claim. Purchase-conditioned
  quality does not establish message-understanding accuracy.

The runnable code uses the final-night configuration.

## Layout

| Path | Purpose |
| --- | --- |
| `main.py` | CLI game loop; running it can enter the live platform queue |
| `glee_agent/` | Policies, parameters, dispatcher, state readers, safety, logging |
| `tests/` | Historical reference expectations and analysis regression tests |
| `tools/` | Setup check, transcript reader, post-mortem analysis |
| `paper/` | Exact submitted PDF, matching NeurIPS 2026 sources, build/check script |
| `paper/camera_ready/` | Camera-ready PDF, the scripted edits from the submission, Figure 1 data |
| `paper/analysis/` | Corrected observational analysis code; inputs and limits documented |
| `paper/change-register.html` | Incomplete historical notebook, with audit qualifications |

## Setup and running

Python 3.12 was used during the competition. The SDK is needed only for platform
operations, not for the offline policy or analysis tests.

```sh
python -m venv .venv
# Activate the virtual environment using your shell's command.
pip install -r requirements.txt
# Copy .env.example to .env and set your own key locally.
python tools/check_setup.py
```

`check_setup.py` requests account statistics and does not play a game.
Do not commit credentials or paste them into issues. Platform availability,
limits, scoring behavior and competition dates may have changed.

To operate an agent only when the platform permits it:

```sh
python main.py
python main.py --families bargaining negotiation
python main.py --concurrency 8 --max-games 50
```

Stop with Ctrl-C. The loop attempts to leave the queue; cleanup is not a guarantee
that in-flight games cannot time out. Local turn logs may contain other
participants' transcripts and should remain private.

## Tests and configuration provenance

```sh
python -m pytest --agent-profile=reference
python -m pytest tests/test_paper_analysis.py
python -m pytest --agent-profile=final-night
```

The default `reference` profile explicitly restores the parameter values from
the preserved pre-final-night commit `84285c72751c2d24fa400082650dd7f207993bd4`,
disables three later-added experimental gates, and exercises the historical
472 test expectations. The reference profile is test-only; it does not alter
the defaults used by `main.py`. The test summary identifies the selected profile.

The `final-night` profile leaves the executable defaults untouched. Against
the historical 472 expectations it produces **445 passes and 27 failures**.
These disagreements are reported openly, not skipped or marked as expected
failures. They include experimental defaults and changed behavior; they are
not all evidence of crashes. Passing a reference suite is not proof of the
optimality, deployment identity, or results of a competition build.

Additional tests check the revised analysis, input validation, figure audit and
submitted-file integrity using synthetic data, not private competition outcomes.

## Evidence and limitations

The strongest observations are simultaneous rating dispersion, exact replay on
specified logged cohorts, and concrete parser/termination-limit failures.
Initialization, changing opponents and reference pools confound the rating
experiment. A mean rating delta is not a stationary measure of policy strength.
The same-author human comparison does not isolate perceptual ability.

The public analysis has no complete original joins/replay pipeline, raw rating
polls, or complete run manifest. Anticipated organizer data do not automatically
resolve deployment provenance or private-input gaps. See the
[analysis README](paper/analysis/README.md) for what is actually executable.

Historical operational observations (including timeout caps, rating/display
rules and cooldowns) must not be mistaken for a current authoritative API
specification. The [competition site](https://glee-competition.com/) is the
organizer's source.

## License

MIT for software; manuscript and historical change register remain the author's
copyright. See [NOTICE](NOTICE) for scope. The NeurIPS style retains its own terms.
