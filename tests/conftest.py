import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def rung_aware(monkeypatch):
    """Turn on rung-aware pricing for one test.

    The switch ships off, so every test that exercises the ladder has to say so
    -- which also keeps the default path honest in every other test.
    """
    import dataclasses
    from glee_agent import params
    from glee_agent.strategies import negotiation
    monkeypatch.setattr(negotiation, "P",
                        dataclasses.replace(params.NEGOTIATION, rung_aware=True))


@pytest.fixture
def schedule_only(monkeypatch):
    """Force the multiple-based schedule on, whatever the build ships.

    Tests that pin the fallback schedule must keep testing the fallback even in
    a build where `rung_aware` is switched on -- otherwise an arm that flips the
    flag reports failures for behaviour it changed on purpose, and the real
    signal is lost in the noise.
    """
    import dataclasses
    from glee_agent import params
    from glee_agent.strategies import negotiation
    monkeypatch.setattr(negotiation, "P",
                        dataclasses.replace(params.NEGOTIATION, rung_aware=False))


def _set_messages(monkeypatch, value):
    """Each strategy binds SEND_MESSAGES by value at import, so the flag is set
    on the strategy module rather than on `params`."""
    from glee_agent.strategies import bargaining, negotiation, persuasion
    for module in (bargaining, negotiation, persuasion):
        monkeypatch.setattr(module, "SEND_MESSAGES", value)


@pytest.fixture
def messages_on(monkeypatch):
    """Force the free-text channel on, whatever the build ships."""
    _set_messages(monkeypatch, True)


@pytest.fixture
def rationing_belief(monkeypatch):
    """Let the buyer read a seller's rationing when it has bought nothing."""
    import dataclasses
    from glee_agent import params
    from glee_agent.strategies import persuasion
    monkeypatch.setattr(persuasion, "P",
                        dataclasses.replace(params.PERSUASION, rationing_belief=True))


@pytest.fixture
def bare_recommendation(monkeypatch):
    """Persuasion alone goes bare, while bargaining and negotiation keep prose.

    This is the whole point of the flag: `SEND_MESSAGES` is global, so before it
    existed the only way to send a bare recommendation was to silence all three
    families at once.
    """
    import dataclasses
    from glee_agent import params
    from glee_agent.strategies import persuasion
    monkeypatch.setattr(persuasion, "P",
                        dataclasses.replace(params.PERSUASION, bare_recommendation=True))


@pytest.fixture
def messages_off(monkeypatch):
    """Force the silent build on, whatever the build ships.

    The silent path stays exercised even while messages ship on, so flipping
    `SEND_MESSAGES` produces exactly one failure -- the test that guards the
    default -- instead of a scatter of failures for behaviour changed on
    purpose.
    """
    _set_messages(monkeypatch, False)


@pytest.fixture
def rations_on_mix(monkeypatch):
    """Ration the whole hard persuasion market against the realised mix.

    Ships off, like `rung_aware`, so the interior behaviour it changes has to be
    asked for explicitly and every other test keeps exercising the credibility
    gate that is actually live.
    """
    import dataclasses
    from glee_agent import params
    from glee_agent.strategies import persuasion
    monkeypatch.setattr(persuasion, "P",
                        dataclasses.replace(params.PERSUASION,
                                            hard_regime_rations_on_mix=True))


@pytest.fixture
def hold_cap_on(monkeypatch):
    """Cap the open-game accept bar where waiting costs us.

    Ships off, so the bar every other test exercises stays the one that is live.
    """
    import dataclasses
    from glee_agent import params
    from glee_agent.strategies import bargaining
    monkeypatch.setattr(bargaining, "P",
                        dataclasses.replace(params.BARGAINING,
                                            discounted_hold_cap_on=True))


@pytest.fixture
def costless_cap_on(monkeypatch):
    """Cap the open-game accept bar where delay costs us nothing.

    Ships off: holding out at delta 1.0 is measurably right below 0.55 and only
    wrong above it, so this is an arm rather than a default.
    """
    import dataclasses
    from glee_agent import params
    from glee_agent.strategies import bargaining
    monkeypatch.setattr(bargaining, "P",
                        dataclasses.replace(params.BARGAINING,
                                            costless_hold_cap_on=True))


@pytest.fixture
def stonewall_caves(monkeypatch):
    """Restore the old behaviour: take a stonewaller's price the moment it pays.

    This is the inverse of the shipped default now that run37 turned
    `stonewall_needs_endgame` on, and it exists so the tests can still pin what
    the branch used to do.
    """
    import dataclasses
    from glee_agent import params
    from glee_agent.strategies import negotiation
    monkeypatch.setattr(negotiation, "P",
                        dataclasses.replace(params.NEGOTIATION,
                                            stonewall_needs_endgame=False))



@pytest.fixture
def hide_rung(monkeypatch):
    """Stop an unacceptable ask from naming our own rung."""
    import dataclasses
    from glee_agent import params
    from glee_agent.strategies import negotiation
    monkeypatch.setattr(negotiation, "P",
                        dataclasses.replace(params.NEGOTIATION,
                                            hide_rung_from_last_word=True))


@pytest.fixture
def sweep_counter(monkeypatch):
    """Answer a sweeper with a price his own inflation tells him to sign."""
    import dataclasses
    from glee_agent import params
    from glee_agent.strategies import bargaining
    monkeypatch.setattr(bargaining, "P",
                        dataclasses.replace(params.BARGAINING,
                                            sweep_counter_on=True))


@pytest.fixture
def settle_early(monkeypatch):
    """Charge a rejection what the record says it really costs."""
    import dataclasses
    from glee_agent import params
    from glee_agent.strategies import bargaining
    monkeypatch.setattr(bargaining, "P",
                        dataclasses.replace(params.BARGAINING, settle_early_on=True))


@pytest.fixture
def hold_open(monkeypatch):
    """Walk a costless-delay open game against the real cap, not a 12-round one."""
    import dataclasses
    from glee_agent import params
    from glee_agent.strategies import bargaining
    monkeypatch.setattr(bargaining, "P",
                        dataclasses.replace(params.BARGAINING,
                                            costless_open_holds_on=True))
