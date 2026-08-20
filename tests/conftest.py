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
def messages_off(monkeypatch):
    """Force the silent build on, whatever the build ships.

    The silent path stays exercised even while messages ship on, so flipping
    `SEND_MESSAGES` produces exactly one failure -- the test that guards the
    default -- instead of a scatter of failures for behaviour changed on
    purpose.
    """
    _set_messages(monkeypatch, False)
