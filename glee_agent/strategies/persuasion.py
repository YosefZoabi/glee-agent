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
from ..params import PERSUASION as P, SEND_MESSAGES

# Phrases a seller only writes when steering us away from a sale.
_NEGATIVE_HINTS = (
    # Explicit refusals.
    "not worth", "not recommend", "do not recommend", "don't recommend",
    "wouldn't recommend", "would not recommend", "not a good", "not great",
    "skip this", "sit this", "pass on this", "avoid", "poor quality",
    "low quality", "not buy", "don't buy", "do not buy",
    # Hedged refusals. Sellers rarely say "do not buy" -- they say the unit is
    # ordinary and leave the buyer to draw the conclusion. Reading only the
    # explicit form meant we bought products the seller had just warned us
    # about: measured across every round where quality was later revealed,
    # these phrasings delivered high quality 0-12% of the time, against 79-97%
    # for genuine recommendations. 165+ purchases of known-bad stock.
    "below our usual", "below my usual", "below usual", "not up to my usual",
    "not up to our usual", "isn't my best", "is not my best", "not my best",
    "ordinary unit", "nothing special", "unremarkable",
    "want to pass", "understand a pass", "understand if you",
    "not this round", "better to wait", "wait for a better",
    "want to skip", "hold off", "not the one",
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


def _template_key(message) -> str:
    """Collapse a seller message to the script it came from.

    Sellers reuse a handful of fixed strings, so exact text after normalising
    case, punctuation and whitespace identifies the template. Deliberately not
    fuzzy: a near-match is a different sentence, and two scripts that differ by
    one clause are exactly the pair we need to tell apart.
    """
    text = "".join(ch.lower() for ch in str(message) if ch.isalnum() or ch == " ")
    return " ".join(text.split())


def template_is_proven_bad(game: dict, message) -> bool:
    """True when THIS script has already paid us nothing, repeatedly.

    Counts only rounds we bought, because quality is revealed nowhere else.
    See `template_veto` for the 79,100-purchase measurement behind it.
    """
    if not P.template_veto:
        return False
    key = _template_key(message)
    if not key:
        return False
    bought = high = 0
    for entry in history(game):
        if not entry.get("bought"):
            continue
        if _template_key(entry.get("seller_message")) != key:
            continue
        bought += 1
        if str(entry.get("quality") or "").lower() == "high":
            high += 1
    return bought >= int(P.template_min_buys) and high == 0


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


def estimate_threshold(game: dict, p: float) -> tuple[float, float]:
    """Bracket the buyer's `tau` from their own decisions, when we are not told it.

    More than half our seller games never reveal the buyer's value, so `tau` is
    unknown and every rule built on it goes dark -- those games had the worst
    sale rate of any regime. But the buyer brackets it for us each round they
    answer a recommendation: buying at credibility `c` proves `tau <= c`, and
    refusing proves `tau > c`. That needs no posterior over `v`, just the
    interval their answers have already narrowed.

    Returns (lower, upper). An upper of 1.0 means they have never bought, so we
    know only that our credibility has not yet been enough.
    """
    weight = P.belief_prior_weight
    lower, upper = 0.0, 1.0
    seen = kept = 0
    for entry in history(game):
        # Their belief going INTO this round -- what they judged the offer on.
        credibility = (p * weight + kept) / (weight + seen)
        if _is_positive(entry.get("seller_message")):
            if entry.get("bought"):
                upper = min(upper, credibility)
            else:
                lower = max(lower, credibility)
        # Quality is revealed to them only by a purchase, so only that updates
        # the evidence they are reasoning from.
        if entry.get("bought"):
            seen += 1
            if str(entry.get("quality") or "").lower() == "high":
                kept += 1
    return lower, upper


def _blind_recommends(game: dict, p: float, round_number: int, total_rounds: int) -> bool:
    """Low-quality decision when the buyer's value was never disclosed."""
    lower, upper = estimate_threshold(game, p)
    if upper >= 1.0:
        recommended, _delivered, bought = _recommendation_record(game)
        if not bought and recommended >= P.non_buyer_evidence:
            # A long run of recommendations, none taken. Whatever their bar is,
            # we have not cleared it and staying honest has not moved them --
            # so the credibility we are protecting will never be spent.
            return True
        # Otherwise they have simply not bought YET. We have no ceiling on what
        # they need, and the only lever we have is to be worth believing.
        return False
    if lower > upper:
        # Bought at one credibility and refused at a higher one: not reading the
        # signal on its merits, so there is no threshold to respect.
        return True
    if p > upper:
        # Their own prior clears the bar they have shown us; silence only costs
        # us the sale.
        return True

    # Otherwise hold credibility above the bracketed bar, with the same margin
    # that decays as the remaining rounds lose value.
    weight = P.belief_prior_weight
    credibility, seen = _buyer_visible_credibility(game, p)
    posterior_if_caught = (credibility * (weight + seen)) / (weight + seen + 1)
    remaining = max(0, total_rounds - round_number)
    margin = P.credibility_margin * (remaining / max(1, total_rounds - 1))
    if posterior_if_caught < upper + margin:
        return False
    return _rng_unit(game.get("game_id"), round_number) < P.blind_lie_rate


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
        return _blind_recommends(game, p, round_number, total_rounds)

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
    if p >= tau or P.hard_regime_rations_on_mix:
        # The knife edge. `regime` sends p strictly above tau to "easy", so the
        # only way here with p >= tau is p == tau: their prior sits exactly on
        # their bar, and the ONLY thing that can push their posterior under it
        # is the mix of our own recommendations. So ration against that mix
        # directly -- keep the share of our recommendations that were genuinely
        # high at or above the bar plus a sliver -- rather than vetoing on
        # `posterior_if_caught`, which prices the risk of being caught out on a
        # dud. That proxy is right for a hard market, where credibility is the
        # whole game; here it throttles us to a realised 0.35-0.47 across 1,849
        # measured low rounds when the bar itself only asks for ~0.96, and each
        # round we decline is a sale handed back (a recommendation moves the buy
        # rate from 3.6% to 89.8%).
        #
        # This IS the quota the regression asks for -- rationing against the
        # lows actually seen, deterministically, so the realised rate cannot
        # overshoot on a run of luck the way a per-round coin flip does. It
        # front-loads honesty on its own: with nothing banked, delivered/(rec+1)
        # starts below the bar and only clears it once real high-quality
        # recommendations have accumulated. See TestSellerBudgetIsAQuota,
        # regression game 2e48f9f7 (p = tau = 0.80, 20 of 20 pushed, 0 sold).
        #
        # Under `hard_regime_rations_on_mix` the same rule takes the interior
        # too, where p < tau. The argument carries because the rule is stated in
        # the buyer's own terms: delivered/recommended IS the posterior a
        # recommendation induces, so holding it at tau holds them at their bar
        # whatever the prior was. What does NOT carry over is the credibility
        # gate below, whose anchor at p keeps it shut for longer than the game
        # lasts once p sits under the bar. See `hard_regime_rations_on_mix`.
        recommended, delivered, _bought = _recommendation_record(game)
        realised = delivered / (recommended + 1)
        return realised >= tau * (1.0 + P.knife_edge_margin)

    required = tau + P.credibility_margin * (remaining / max(1, total_rounds - 1))
    if posterior_if_caught < required:
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

    That argument assumes a buyer who reads. Against the actual field it does
    not hold: crossing from the binary channel to this one costs us 10 to 18
    points of sell rate in every value band, against the same opponents, while
    the field's sell rate goes UP. See `bare_recommendation`, which sends these
    games the two words the binary half sends instead.
    """
    recommends = _seller_recommends(game)
    if not SEND_MESSAGES or P.bare_recommendation:
        # Text mode is the same decision the binary half of these games sends as
        # a bare yes/no, so it is sent as a bare yes/no. Nothing is argued, and
        # nothing about us is volunteered. It cannot be empty: `safety.sanitize`
        # refills an empty seller_message with the fallback pitch, which would
        # put a sales line back on the wire.
        return {"message": "Recommended." if recommends else "Not recommended."}

    if not recommends:
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


def recommendation_rate(game: dict) -> float | None:
    """Fraction of rounds so far that the seller has recommended.

    Visible without buying anything, which is the entire point of it.
    """
    rounds = history(game)
    if not rounds:
        return None
    return sum(1 for entry in rounds if _is_positive(entry.get("seller_message"))) / len(rounds)


def signal_posterior(game: dict, p: float) -> float:
    """P(high | recommended), inferred from how hard the seller is rationing.

    A seller never talks down a high-quality product -- it costs them the sale
    and buys nothing -- so every high round sits among the recommended ones:

        P(high | recommended) = P(high) / P(recommended) = p / rate

    which needs no purchases at all. That matters because quality is revealed
    only on rounds we buy (0 of 2,606 unbought rounds ever showed it), so a
    belief that updates only on purchases has an absorbing state: in a hard
    market the prior starts below the buyer's bar by definition, we decline, the
    belief never moves, and we decline for the rest of the game. Measured over
    chunk 9: 79 games sat out end to end for a payoff of exactly zero, with the
    seller rationing honestly in most of them.

    It degrades in the right direction, too. A seller who recommends everything
    has rate = 1, the estimate collapses back to `p`, and we behave exactly as
    before -- correctly, because they told us nothing. Checked against the only
    ground truth available (quality on rounds we did buy): this predicts
    P(high | recommended) to a median 9.1% error against 13.7% for the bare
    prior, and in the rationing bucket the prior is off by fifty points.

    NOT CURRENTLY USED, and the reason is worth keeping. Wired into the buyer's
    prior for chunk 10 it did exactly what it was designed to do -- games where
    we never bought a single round fell from 34% to 17%, and hard-market buying
    rose from 16.6% of rounds to 30.8%. It also lost money. Those purchases came
    in at 71.2% high quality against a bar of 80.0%, 3.5 sigma below, where the
    old policy had sat at 79.4% and roughly broken even.

    Two errors produced that. First, `p / rate` is a CEILING on the posterior,
    not a point estimate: it is exact only if the seller recommends every single
    high-quality unit, and every deviation makes it optimistic. Second, and
    worse, it was validated against rounds we had CHOSEN to buy -- rounds where
    the belief already cleared the bar -- which says nothing about the marginal
    rounds it newly licenses. Shipping it beside the classifier fix compounded
    both: better negative detection lowers `rate`, which raises `p / rate`, so
    the estimator went live materially more aggressive than the version measured.

    Both objections are now answered, on rounds we did not choose. In the six
    cells where p*v > price the buyer takes EVERY recommendation, so the rate
    never enters the decision and the sample is unselected. There:

      h, the share of HIGH units the field praises, is 1.015 (sd 0.039) over 10
        cells -- so p/rate is a tight ceiling, not just an upper bound
      p/rate against realised quality is unbiased over 28 cell-buckets:
        +0.0010 (sd 0.0429)
      the RUNNING estimate, which is what actually ships, bucketed by the belief
        it held going INTO each round: +0.0389 (sd 0.0139) over 7 buckets, and
        conservative in every single one -- it understates the seller

    The rationing is a strong signal: sellers praising 25% of rounds come in
    91.1% high, those praising 99% come in 66.4%.

    Wired back in behind `rationing_belief`, additively -- it can only turn a
    refusal into a purchase -- and with a margin, since the estimate is
    optimistic exactly where it saturates.
    """
    rate = recommendation_rate(game)
    if rate is None or rate <= 0.0:
        return p
    raw = clamp(p / rate, 0.0, P.rationing_cap)
    seen = len(history(game))
    return clamp(p + (raw - p) * (seen / (seen + P.rate_prior_weight)), 0.0, 1.0)


def shrunk_ceiling(game: dict, p: float) -> float:
    """The most `signal_posterior` could return on this round, at any rationing.

    It shrinks p/rate toward `p` by seen/(seen + `rate_prior_weight`) and caps
    the raw ratio at `rationing_cap`, so however hard the seller rations, this
    is the ceiling. Comparing it to the bar says whether that estimator has any
    chance in this cell -- which is what decides where the break-even line is
    allowed to take over.
    """
    seen = len(history(game))
    return clamp(p + (P.rationing_cap - p) * (seen / (seen + P.rate_prior_weight)),
                 0.0, 1.0)


def certified_posterior(game: dict, p: float) -> float | None:
    """P(high | recommended) on the bare ceiling, with no shrinkage toward `p`.

    `signal_posterior` is the right estimator where the bar is loose. Where it
    is tight it cannot move: the seen/(seen + `rate_prior_weight`) shrinkage and
    `rationing_cap` together hold it under 0.894 at twenty rounds, and the four
    m <= 1.25 frozen cells need 0.920-0.958 once `rationing_margin` is added. So
    the arm that was supposed to cover those cells bought 0.000 rounds in all
    566 run47 games there, in ARM and control alike.

    This drops both. `p / rate` is a ceiling, so it is corrected by `h`, the
    share of HIGH units the field actually praises -- 1.015 (sd 0.039) over the
    ten cells where the buyer takes every recommendation and the sample is
    therefore unselected. That is the correction the ceiling needs; pulling the
    whole estimate back toward a prior the seller's rationing has already
    refuted is not.

    See `rationing_break_even` in params for the ground-truth pricing: 0.955
    realised against a 0.825 bar over 88 human buys, 5.9 sigma, clearing in all
    four cells separately.

    Returns None when there is not yet enough watching to read a rate.
    """
    if len(history(game)) < P.rationing_min_rounds:
        return None
    rate = recommendation_rate(game)
    if rate is None or rate <= 0.0:
        return None
    return clamp(P.rationing_h * p / rate, 0.0, 1.0)


def _buyer_credibility(game: dict, p: float) -> float:
    """Posterior probability that a recommended product is high quality.

    Counts only rounds we actually bought after a positive signal -- quality is
    hidden on rounds we passed, so those carry no evidence either way. What the
    passes DO carry is the seller's rationing, which `signal_posterior` reads,
    and which seeds the prior here instead of the bare `p`.
    """
    # `signal_posterior` was wired in here and is deliberately NOT any more --
    # see its docstring for what the live data did to it.
    base = p
    weight = P.belief_prior_weight
    high, low = base * weight, (1.0 - base) * weight
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
    return clamp(high / total, 0.0, 1.0) if total > 0 else base


def _buyer_decision(game: dict) -> dict:
    state = game["game_state"]
    p = number(state, "p", 0.5) or 0.5
    price = number(state, "product_price", 0.0) or 0.0
    v = number(state, "v", None)
    u = number(state, "u", 0.0) or 0.0
    if v is None:
        return {"decision": "no"}

    signal = state.get("seller_message")
    # A script that has already sold us nothing but low quality is a negative
    # signal whatever its words say -- and the words are the seller's to choose,
    # while the record is not. Vetoes ahead of every buy path below, including
    # the prior-clears-the-bar one, because 11.7% is under every cell's bar.
    if template_is_proven_bad(game, signal):
        return {"decision": "no"}
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

    if P.press_recommendations and price > 0 and             p * v + (1.0 - p) * u >= price * P.explore_tolerance:
        # The prior sits ON the bar, so blind buying is break-even -- but this
        # is not blind. The seller recommended, and conditional on that the hit
        # rate beats the prior, which makes every one of these a favourable bet.
        # Take them all rather than buying two and letting those decide the
        # rest, which is what leaves half our (1/3,3.00) games in the bottom
        # quarter.
        if v < price * P.press_cap_below_m:
            # Where a good buy pays only 0.2-0.25x, stop once well ahead: the
            # percentile curve is flat up there and the variance buys nothing.
            banked = number(state, "buyer_total_payoff", 0.0) or 0.0
            if banked >= P.press_profit_cap * price:
                return {"decision": "no"}
        return {"decision": "yes"}

    belief = _buyer_credibility(game, p)
    expected = belief * v + (1.0 - belief) * u

    round_number = int(number(state, "round", 1) or 1)
    if round_number <= P.explore_rounds:
        # Buying is the only way to observe quality; pay a little for the read.
        return {"decision": "yes" if expected >= price * P.explore_tolerance else "no"}
    if expected > price:
        return {"decision": "yes"}
    if P.rationing_belief:
        # Nothing was bought, so `belief` above is still the bare prior and will
        # stay there for the rest of the game -- an absorbing refusal. What the
        # seller declines to praise is visible without buying anything, so read
        # that instead. Strictly additive: this branch only ever converts a
        # refusal into a purchase, which makes the counterfactual a count.
        lifted = signal_posterior(game, p)
        if lifted * v + (1.0 - lifted) * u > price * (1.0 + P.rationing_margin):
            return {"decision": "yes"}
        # Cells where that shrunk estimate cannot reach the bar however hard the
        # seller rations. Only ever consulted on a round the seller recommended.
        if P.rationing_break_even and _is_positive(state.get("seller_message")):
            # Only where the shrunk estimator is arithmetically incapable of
            # clearing the bar. Without this the break-even line also fires in
            # (1/3,2.00) -- 952 rounds of the replay -- which is the cell
            # `rationing_belief` already wins at 7.1 sigma, and where the same
            # ground truth has this rule coming in at 0.453 against a 0.500 bar.
            # Stated as arithmetic rather than a cell list so it cannot drift.
            ceiling = shrunk_ceiling(game, p)
            if ceiling * v + (1.0 - ceiling) * u <= price * (1.0 + P.rationing_margin):
                # A lead bought here is fragile: at m=1.20 one low draw undoes
                # five good ones, and the field's mass sits at exactly zero, so
                # a game that ends negative ranks near the floor. Bank the rank.
                if v < price * P.break_even_cap_below_m:
                    banked = number(state, "buyer_total_payoff", 0.0) or 0.0
                    if banked >= P.break_even_profit_cap * price:
                        return {"decision": "no"}
                certified = certified_posterior(game, p)
                if certified is not None and certified * v + (1.0 - certified) * u > price:
                    return {"decision": "yes"}
    return {"decision": "no"}


def play(game: dict) -> dict:
    action_type = (game.get("valid_actions") or {}).get("type")
    if action_type == "seller_message":
        return _seller_message(game)
    if action_type == "seller_recommendation":
        return {"decision": "yes" if _seller_recommends(game) else "no"}
    return _buyer_decision(game)
