"""Strategic information transmission: a credibility budget, spent on a schedule.

The seller sees each round's quality; the buyer sees only the prior `p` and the
history. The seller earns the price on every sale regardless of quality, so the
temptation is to recommend everything -- and a buyer who notices stops buying,
which is why reputation is the seller's real currency.

Seller. Bayesian persuasion gives the exact size of the lie the buyer will
tolerate. If the seller recommends every high-quality product and a fraction q
of the low-quality ones, a buyer seeing a recommendation puts probability
`p / (p + (1-p)q)` on high quality, and buys while that keeps expected value
above the price. Solving for q gives the budget below. We spend under it (an
exactly-indifferent buyer often passes anyway), ramp it up as rounds run out
because reputation is only worth holding while there is a future to spend it in,
and recommend everything on the final round, where there is none.

Buyer. Track how often a recommendation actually delivered, as a Beta posterior
anchored on `p`, and buy while expected value clears the price. Quality is
revealed only on rounds we bought, so the first rounds buy on a slightly
marginal expectation: the information is what prices every later round.
"""

from __future__ import annotations

import hashlib

from ..gamestate import clamp, history, number
from ..params import PERSUASION as P

# Phrases a seller only writes when steering us away from a sale.
_NEGATIVE_HINTS = (
    "not worth", "not recommend", "do not recommend", "don't recommend",
    "wouldn't recommend", "would not recommend", "not a good", "not great",
    "skip this", "sit this", "pass on this", "avoid", "poor quality",
    "low quality", "not buy", "don't buy", "do not buy",
)


def _is_positive(signal) -> bool:
    """Read a seller signal, in either binary or free-text mode."""
    if signal is None:
        return False
    text = str(signal).strip().lower()
    if not text:
        return False
    if text in {"yes", "true", "1", "buy", "recommend"}:
        return True
    if text in {"no", "false", "0", "pass"}:
        return False
    # Free text. Talking a buyer out of a sale costs the seller their own
    # revenue, so an explicit negative is the only signal worth reading
    # literally; everything else is the sales pitch we should expect by default.
    return not any(hint in text for hint in _NEGATIVE_HINTS)


def _rng_unit(*parts) -> float:
    """A deterministic pseudo-random number in [0, 1).

    Seeded from the game id and round so a replayed log produces the same
    decisions -- which is what makes the behavior analysis reproducible.
    """
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def lie_budget(p: float, price: float, v: float, u: float) -> float:
    """Largest fraction of low-quality products we can push and still be believed.

    Derived from the buyer's posterior after a recommendation. Returns 1.0 when
    the buyer's prior already justifies buying (nothing we say can hurt) and
    when the price exceeds even a certain-high value (nothing we say can help).
    """
    if v <= u:
        return 1.0
    threshold = (price - u) / (v - u)          # posterior on high needed to buy
    if threshold <= 0:
        return 1.0
    if threshold >= 1 or p >= threshold:
        return 1.0
    if p <= 0 or p >= 1:
        return 1.0 if p >= 1 else 0.0
    return clamp(p * (1.0 - threshold) / (threshold * (1.0 - p)), 0.0, 1.0)


def _seller_recommends(game: dict) -> bool:
    state = game["game_state"]
    quality = str(state.get("current_quality") or "").lower()
    if quality == "high":
        return True                            # never talk down a good product

    round_number = int(number(state, "round", 1) or 1)
    total_rounds = int(number(state, "total_rounds", round_number) or round_number)

    p = number(state, "p", 0.5) or 0.5
    price = number(state, "product_price", None)
    v = number(state, "v", None)
    u = number(state, "u", 0.0) or 0.0

    if price is None or v is None:
        budget = P.blind_lie_rate           # not told the buyer's values
    else:
        budget = lie_budget(p, price, v, u) * P.lie_budget_use

    if round_number >= total_rounds:
        return True                         # last round: no reputation left to protect

    span = max(1, total_rounds - 1)
    ramp = P.lie_ramp_start + (1.0 - P.lie_ramp_start) * ((round_number - 1) / span)
    return _rng_unit(game.get("game_id"), round_number) < budget * ramp


def _seller_message(game: dict) -> dict:
    recommend = _seller_recommends(game)
    if recommend:
        return {
            "message": (
                "I have looked this one over and I am happy to put my name on it. "
                "It is worth the price -- I would take it."
            )
        }
    return {
        "message": (
            "Straight answer: this one is not worth what I am asking. Sit this "
            "round out and I will tell you when a good one comes up."
        )
    }


def _buyer_credibility(game: dict, p: float) -> float:
    """Posterior probability that a recommended product is high quality.

    Counts only rounds we actually bought after a positive signal -- quality is
    hidden on rounds we passed, so those carry no evidence either way.
    """
    weight = P.belief_prior_weight
    high, low = p * weight, (1.0 - p) * weight
    for entry in history(game):
        if not entry.get("bought"):
            continue
        if not _is_positive(entry.get("seller_message")):
            continue
        quality = str(entry.get("quality") or "").lower()
        if quality == "high":
            high += 1.0
        elif quality == "low":
            low += 1.0
    total = high + low
    return clamp(high / total, 0.0, 1.0) if total > 0 else p


def _buyer_decision(game: dict) -> dict:
    state = game["game_state"]
    p = number(state, "p", 0.5) or 0.5
    price = number(state, "product_price", 0.0) or 0.0
    v = number(state, "v", None)
    u = number(state, "u", 0.0) or 0.0
    if v is None:
        return {"decision": "no"}

    signal = state.get("seller_message")
    if signal is not None and not _is_positive(signal) and P.trust_negative_signal:
        # Talking us out of a sale costs the seller their own revenue, so the
        # only reason to do it is that the product really is bad.
        return {"decision": "no"}

    belief = _buyer_credibility(game, p)
    expected = belief * v + (1.0 - belief) * u

    round_number = int(number(state, "round", 1) or 1)
    if round_number <= P.explore_rounds:
        # Buying is the only way to observe quality; pay a little for the read.
        return {"decision": "yes" if expected >= price * P.explore_tolerance else "no"}
    return {"decision": "yes" if expected > price else "no"}


def play(game: dict) -> dict:
    action_type = (game.get("valid_actions") or {}).get("type")
    if action_type == "seller_message":
        return _seller_message(game)
    if action_type == "seller_recommendation":
        return {"decision": "yes" if _seller_recommends(game) else "no"}
    return _buyer_decision(game)
