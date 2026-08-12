"""One module per game family. Each exposes `play(game) -> action`."""

from . import bargaining, negotiation, persuasion

__all__ = ["bargaining", "negotiation", "persuasion"]
