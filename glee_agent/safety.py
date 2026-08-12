"""The layer that guarantees we always submit something legal.

Two failure modes cost a lot more than a bad move does. Five invalid moves ends
the game as a no-deal, and so does missing the 120-second turn clock -- both are
scored at the 5th percentile, the bottom of the scale. A crashing strategy is
therefore worse than a mediocre one, and three consecutive self-inflicted
timeouts also trip a 30-minute cooldown on queue joins.

So every action goes through `sanitize` on the way out, and any strategy that
raises is replaced by `fallback`, which returns a move that is legal by
construction for whatever the platform is asking for.
"""

from __future__ import annotations

from .gamestate import me as my_slot, messages_allowed, number, split_exactly

try:
    # Stay in step with the SDK if it is installed, but do not depend on it:
    # this module and its tests must run before anything is pip-installed.
    from glee_sdk import MAX_MESSAGE_LEN as MAX_MESSAGE_CHARS
except ImportError:
    MAX_MESSAGE_CHARS = 2000


def _allowed_values(game: dict, field: str) -> set[str] | None:
    """Allowed values for a field, when `valid_actions.fields` spells them out."""
    fields = (game.get("valid_actions") or {}).get("fields")
    if not isinstance(fields, dict):
        return None
    spec = fields.get(field)
    if isinstance(spec, (list, tuple, set)):
        return {str(value) for value in spec}
    if isinstance(spec, dict):
        for key in ("values", "enum", "options", "choices"):
            candidate = spec.get(key)
            if isinstance(candidate, (list, tuple, set)):
                return {str(value) for value in candidate}
    return None


def fallback(game: dict) -> dict:
    """A legal, defensible move for the current turn, used when all else fails.

    Every branch prefers closing over stalling: a mediocre agreed payoff beats
    the $0 that an abandoned game books.
    """
    state = game.get("game_state") or {}
    action_type = (game.get("valid_actions") or {}).get("type") or ""
    slot = my_slot(game)

    if action_type == "offer":
        if game.get("game_family") == "bargaining":
            money = number(state, "money_to_divide", 0.0) or 0.0
            mine, theirs = split_exactly(money, 0.5)
            return (
                {"alice_gain": mine, "bob_gain": theirs}
                if slot == "player_1"
                else {"alice_gain": theirs, "bob_gain": mine}
            )
        my_value = number(state, f"{slot}_value", None)
        offered = number(state.get("last_offer") or {}, "price", None)
        price = my_value if my_value is not None else (offered if offered is not None else 0.0)
        return {"product_price": round(float(price), 2)}

    if action_type == "seller_message":
        return {"message": "Here is this round's product at the usual price."}
    if action_type == "seller_recommendation":
        return {"decision": "yes"}

    if game.get("game_family") == "negotiation":
        return {"decision": "AcceptOffer"}
    if game.get("game_family") == "persuasion":
        # Buyer: fall back to the prior, which is always visible to us.
        p = number(state, "p", 0.0) or 0.0
        v = number(state, "v", 0.0) or 0.0
        u = number(state, "u", 0.0) or 0.0
        price = number(state, "product_price", 0.0) or 0.0
        return {"decision": "yes" if p * v + (1 - p) * u > price else "no"}
    return {"decision": "accept"}


def sanitize(game: dict, action: dict) -> dict:
    """Repair an action in place of rejecting it.

    A strategy that returns a slightly-off move -- gains that miss the pot by a
    cent, a message past the cap, a stray message in a no-messages game -- should
    cost us nothing, so we fix it rather than spend one of five attempts.
    """
    if not isinstance(action, dict):
        return fallback(game)

    action = dict(action)
    family = game.get("game_family")
    action_type = (game.get("valid_actions") or {}).get("type") or ""
    state = game.get("game_state") or {}

    if "message" in action:
        message = action["message"]
        if message is None or (family in ("bargaining", "negotiation") and not messages_allowed(game)):
            action.pop("message")
        else:
            text = str(message)
            if len(text) > MAX_MESSAGE_CHARS:
                text = text[: MAX_MESSAGE_CHARS - 1].rstrip()
            action["message"] = text

    if action_type == "seller_message" and not str(action.get("message") or "").strip():
        action["message"] = fallback(game)["message"]

    if family == "bargaining" and action_type == "offer":
        money = number(state, "money_to_divide", 0.0) or 0.0
        alice = number(action, "alice_gain", None)
        bob = number(action, "bob_gain", None)
        if alice is None and bob is None:
            return sanitize(game, {**fallback(game), **{k: v for k, v in action.items() if k == "message"}})
        if alice is None:
            alice = money - (bob or 0.0)
        if bob is None or abs((alice + bob) - money) > 1e-9:
            # The gains must sum to the pot exactly. Treat Alice's stated gain as
            # the intent and let the remainder settle on Bob's side.
            alice = max(0.0, min(money, alice))
            alice, bob = split_exactly(money, alice / money if money else 0.5)
        action["alice_gain"], action["bob_gain"] = alice, bob

    if family == "negotiation" and "product_price" in action:
        price = number(action, "product_price", None)
        if price is None:
            action.pop("product_price")
        else:
            action["product_price"] = round(max(0.0, price), 2)

    allowed = _allowed_values(game, "decision")
    if allowed and str(action.get("decision")) not in allowed:
        recovered = fallback(game).get("decision")
        action["decision"] = recovered if str(recovered) in allowed else sorted(allowed)[0]

    return action
