"""All strategy tunables in one place.

Every knob the three strategy modules read lives here, so tuning a family is a
one-file edit and the diff for a tuning experiment is legible. Nothing here
touches the network or the SDK.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BargainingParams:
    # Used for the opponent's inflation rate in incomplete-information games,
    # where `delta_2` (or `delta_1`) is absent from our view of the state.
    # `None` means "assume the opponent's is the same as ours".
    assumed_opponent_delta: float | None = None

    # Round-1 demand as a fraction of the pot. We open above the subgame-perfect
    # share and walk down to it, because the field (LLMs and humans) concedes.
    opening_demand: float = 0.85
    # Higher = hold the opening demand longer before collapsing to the SPE share.
    concession_exponent: float = 1.6
    # Never leave the opponent literally nothing -- a 0 offer reads as an insult
    # and buys a rejection we pay inflation for.
    min_opponent_share: float = 0.03

    # The equilibrium share swings wildly with the parity of the horizon: with a
    # known even number of rounds the opponent proposes last and theory says we
    # take a quarter of the pot. Against a field that converges near an even
    # split, conceding that far is a pure loss, so these two clamp the theory to
    # what the field will actually sign.
    never_concede_below: float = 0.45
    min_accept_share: float = 0.35

    # Accept at this multiple of our continuation value. Slightly below 1.0
    # because one more round of inflation is a real cost and the opponent may
    # not concede at all.
    accept_slack: float = 0.97
    # With this many rounds left, a no-deal ($0, bottom-percentile) outranks any
    # theoretical gain, so we accept anything at or above `endgame_floor`.
    endgame_rounds: int = 2
    endgame_floor: float = 0.08
    # The mirror image on the offering side. Theory says the last proposer can
    # take everything, because the responder's alternative is $0 -- but an
    # opponent who rejects out of pique costs us the whole pot, so the last
    # offers stay large without being insulting.
    endgame_demand_cap: float = 0.55
    final_round_demand: float = 0.72

    # Open-ended games have no forced endgame; pretend one exists here so the
    # concession schedule still moves.
    unbounded_soft_horizon: int = 12


@dataclass(frozen=True)
class NegotiationParams:
    # Incomplete information: opening ask/bid as a multiple of our own value.
    seller_open_multiple: float = 1.9
    buyer_open_multiple: float = 0.45
    # Floor on the margin we still hold at the end of the concession schedule.
    seller_floor_multiple: float = 1.06
    buyer_floor_multiple: float = 0.94
    concession_exponent: float = 1.5

    # Complete information: shade this far inside the opponent's known limit so
    # the offer leaves them a visible reason to accept.
    zopa_shade: float = 0.04

    # Accept when the offer is at least this fraction of our current target
    # profit. Below 1.0 so we do not reject an offer that is one dollar shy.
    accept_slack: float = 0.9
    # Last N rounds: any positive profit beats the $0 that a no-deal pays.
    endgame_rounds: int = 2

    unbounded_soft_horizon: int = 10
    # Fallback price scale when our own value is 0 and the opponent has not
    # offered yet, so no other number in the state can set the scale.
    default_scale: float = 100.0


@dataclass(frozen=True)
class PersuasionParams:
    # --- Seller -------------------------------------------------------------
    # Fraction of the Bayesian-persuasion lying budget we actually use. The full
    # budget makes the buyer exactly indifferent; an indifferent buyer who is an
    # LLM often passes anyway, so we stay under it.
    lie_budget_use: float = 0.75
    # Lying rate ramps from `lie_ramp_start` x budget early to the full budget
    # at the end, because reputation only has value while rounds remain.
    lie_ramp_start: float = 0.35
    # Used when the seller is not told v and u and so cannot compute the budget.
    blind_lie_rate: float = 0.25

    # --- Buyer --------------------------------------------------------------
    # Strength of the prior on seller honesty, in pseudo-observations. Low =
    # adapt fast to a liar, high = forgive noise.
    belief_prior_weight: float = 4.0
    # Buy on a marginal expected value during the first rounds: a purchase is
    # the only way to observe quality, and that information prices every later
    # round.
    explore_rounds: int = 2
    explore_tolerance: float = 0.85
    # A seller who signals "no" gives up their own revenue, so the signal is
    # credible; only override it if it has proven to be noise.
    trust_negative_signal: bool = True


BARGAINING = BargainingParams()
NEGOTIATION = NegotiationParams()
PERSUASION = PersuasionParams()
