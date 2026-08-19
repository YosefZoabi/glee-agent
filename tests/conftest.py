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
