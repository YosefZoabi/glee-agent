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


def buyer_threshold(price: float, v: float, u: float) -> float:
    """`tau`: the posterior on high quality a rational buyer needs to buy.

    Below it they lose money buying, above it they make money, and AT it they
    are exactly indifferent -- which in practice means they walk.
    """
    if v <= u:
        return 1.0
    return (price - u) / (v - u)


def regime(p: float, price: float | None, v: float | None, u: float) -> str:
    """Which persuasion problem are we actually in?

    "free"       price is at or below what even a bad product is worth, so there
                 is nothing to persuade anyone of -- recommend everything.
    "impossible" price is above what even a good product is worth. No posterior
                 clears the bar, so a rational buyer never buys and no signalling
                 policy can change that.
    "easy"       the prior alone clears the bar. Revealing a bad product can only
                 cost us a sale we already had.
    "hard"       the prior does not clear it, so recommendations have to carry
                 real information and credibility is the whole game.
    """
    if price is None or v is None:
        return "unknown"
    if price <= u:
        return "free"
    if price > v:
        return "impossible"
    # Strictly above, not at. Exactly at the threshold the buyer is indifferent,
    # and recommending everything then leaves their posterior sitting on the bar
    # rather than over it. Observed: p = tau = 0.8, we recommended all twenty
    # rounds, they bought none of them. Treating the knife edge as "hard" makes
    # us ration instead, which puts the posterior strictly above the bar.
    return "easy" if p > buyer_threshold(price, v, u) else "hard"


def _recommendation_record(game: dict) -> tuple[int, int, int]:
    """(recommended, of which high, purchases made on a recommendation)."""
    recommended = delivered = bought = 0
    for entry in history(game):
        if not _is_positive(entry.get("seller_message")):
            continue
        recommended += 1
        if str(entry.get("quality") or "").lower() == "high":
            delivered += 1
        if entry.get("bought"):
            bought += 1
    return recommended, delivered, bought


def _buyer_visible_credibility(game: dict, p: float) -> tuple[float, int]:
    """The buyer's own posterior on our recommendations, and its evidence count.

    Crucially this counts only rounds they BOUGHT. Quality is hidden on rounds
    they passed, so a lie is only ever caught by a purchase -- which is what
    makes the reputation cost real rather than notional. Smoothed by the same
    Beta prior our own buyer uses, so we are modelling a reader like ourselves
    rather than one who condemns us on a single sample.
    """
    seen = kept = 0
    for entry in history(game):
        if not entry.get("bought") or not _is_positive(entry.get("seller_message")):
            continue
        seen += 1
        if str(entry.get("quality") or "").lower() == "high":
            kept += 1
    weight = P.belief_prior_weight
    return (p * weight + kept) / (weight + seen), seen


def buyer_ignores_us(game: dict) -> bool:
    """Has the buyer refused recommendations that genuinely cleared their bar?

    Observed in 9 of 25 seller games, four of them with a perfect record: every
    single recommendation was high quality and they still bought nothing in
    twenty rounds. No signalling policy beats that, and it changes what our
    credibility is worth -- reputation is an asset only if it eventually buys a
    sale. Against a buyer who does not read the signal it buys nothing, so there
    is no reason to keep paying for it.
    """
    state = game["game_state"]
    p = number(state, "p", 0.5) or 0.5
    price = number(state, "product_price", None)
    v = number(state, "v", None)
    u = number(state, "u", 0.0) or 0.0
    if price is None or v is None:
        return False

    recommended, delivered, bought = _recommendation_record(game)
    if bought or recommended < P.non_buyer_evidence:
        return False
    # Only counts as being ignored if what we sent them was actually persuasive.
    posterior = delivered / recommended if recommended else 0.0
    return posterior >= buyer_threshold(price, v, u)


def _seller_recommends(game: dict) -> bool:
    state = game["game_state"]
    quality = str(state.get("current_quality") or "").lower()
    if quality == "high":
        return True                            # never talk down a good product

    round_number = int(number(state, "round", 1) or 1)
    total_rounds = int(number(state, "total_rounds", round_number) or round_number)
    if round_number >= total_rounds:
        return True                         # last round: no reputation left to protect

    p = number(state, "p", 0.5) or 0.5
    price = number(state, "product_price", None)
    v = number(state, "v", None)
    u = number(state, "u", 0.0) or 0.0

    market = regime(p, price, v, u)
    if market in ("free", "easy"):
        # Their prior already justifies buying, so a recommendation cannot make
        # them worse off than they were and silence only costs us the sale.
        return True
    if market == "impossible" or buyer_ignores_us(game):
        # Nothing we say changes a rational buyer here, and a buyer who ignores
        # a perfect signal has already shown ours is worthless. Reputation with
        # them is an asset that will never be spent, so stop funding it.
        return True
    if market == "unknown":
        return _rng_unit(game.get("game_id"), round_number) < P.blind_lie_rate

    # Hard market: credibility is the whole game. Recommending this low product
    # is worth it only when the immediate sale outweighs the reputation it costs
    # -- and the reputation cost is precisely the risk of dropping our posterior
    # under the buyer's bar, after which every remaining round pays nothing.
    tau = buyer_threshold(price, v, u)
    # What their belief becomes if they buy this one and find it is a dud --
    # the only way a lie is ever caught, and therefore the only way it costs us.
    weight = P.belief_prior_weight
    credibility, seen = _buyer_visible_credibility(game, p)
    posterior_if_caught = (credibility * (weight + seen)) / (weight + seen + 1)

    # Hold clear of the bar in proportion to what the rest of the game is worth.
    # With the whole game ahead, a lost reputation costs every future sale; on
    # the last rounds it costs almost nothing, so the margin decays to zero and
    # we get the endgame aggression without ever hard-coding a ramp.
    remaining = max(0, total_rounds - round_number)
    margin = P.credibility_margin * (remaining / max(1, total_rounds - 1))
    if posterior_if_caught < tau + margin:
        return False

    # Within the reputation budget, still ration by the static benchmark so a
    # run of luck cannot spend the whole allowance at once.
    budget = lie_budget(p, price, v, u) * P.lie_budget_use
    return _rng_unit(game.get("game_id"), round_number) < budget


def _seller_message(game: dict) -> dict:
    """Say something a buyer can check, rather than something they must trust.

    The template pitch is the weakest possible message: it carries no evidence
    and every seller sends it. Our record is verifiable -- the buyer watched the
    same rounds we did -- and their arithmetic is theirs to confirm. Both are
    strictly more persuasive than an assurance, and against an LLM buyer that is
    the whole difference. Observed: buyers refusing twenty straight rounds of
    genuinely honest recommendations, which is a failure to convince, not a
    failure to signal.
    """
    if not _seller_recommends(game):
        return {
            "message": (
                "Straight answer: this one is not worth what I am asking. Sit this "
                "round out and I will tell you when a good one comes up."
            )
        }

    state = game["game_state"]
    price = number(state, "product_price", None)
    v = number(state, "v", None)
    recommended, delivered, _ = _recommendation_record(game)

    parts = ["Recommending this one."]
    if recommended:
        parts.append(
            f"Track record so far: {delivered} of my {recommended} recommendations "
            f"were the good product -- you saw every one of them."
        )
    if price is not None and v is not None and v > price:
        parts.append(
            f"The arithmetic is yours to check: it is worth {v:,.0f} to you at a "
            f"price of {price:,.0f}, so a good one clears {v - price:,.0f}."
        )
    parts.append("Passing costs you nothing, but it earns you nothing either.")
    return {"message": " ".join(parts)}


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

    # Past the warning above, the prior is a floor. Buying every remaining round
    # realises exactly `p`: the seller chooses which products to praise, not
    # which ones exist, so nothing they do drags our unconditional hit rate
    # below it. When the prior alone clears the price, buying is +EV on
    # arithmetic that does not mention the opponent at all.
    #
    # The posterior could still talk us out of it, and did. It only updates on
    # rounds we BUY, so a couple of unlucky low draws pushed the belief under the
    # bar, which stopped us buying, which froze the belief there -- an absorbing
    # state next to a guaranteed profit. Twice observed against sellers who
    # recommended every single round, so the recommendation carried no
    # information and the prior was exactly right: -2,000,000 on a game paying
    # +333,333/round, and -4,000,000 on one paying +1,000,000/round.
    if p * v + (1.0 - p) * u > price:
        return {"decision": "yes"}

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
