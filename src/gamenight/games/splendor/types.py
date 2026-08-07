"""Explicit structural types for Splendor's `observation`/`legal_actions` shapes.

These are `TypedDict`s, not dataclasses -- the object your `choose_action` actually
receives at runtime is (and always will be) a plain dict, the same as every other
game in this repo (see `core/types.py`'s `Observation = dict[str, Any]`: the engine
can't type it generically because every game's shape differs). A `TypedDict` describes
that exact same dict with no conversion step, no wrapper object, and no runtime cost --
you get real editor autocomplete and type-checker coverage on `observation["public_state"]
["bank"]["white"]`-style access by just writing `observation: SplendorObservation`
instead of `observation: dict`, nothing else changes about how you read it.

Import what you need:

    from gamenight.games.splendor.types import SplendorObservation, SplendorAction

    def choose_action(self, observation: SplendorObservation, context: MatchContext) -> SplendorAction:
        legal_actions = observation["legal_actions"]
        ...

`SplendorAction` is a union of 6 `Literal`-tagged variants (one per `legal_actions`
shape) -- a type checker (and an LLM reading your code) can narrow on `action["type"]`
the same way you'd narrow any tagged union, e.g. `if action["type"] == "purchase_card":
...` tells the checker every field on `PurchaseCardAction` is now valid to read.

See `BOT_SPEC.md` for the authoritative prose reference and `EXAMPLES.md` for real
worked examples of every shape below.
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

Color = Literal["white", "blue", "green", "red", "black"]
TokenColor = Literal["white", "blue", "green", "red", "black", "gold"]
Phase = Literal["action", "discard", "noble_choice"]
ReserveSource = Literal["market", "deck"]


class CardView(TypedDict):
    """A development card wherever it appears (market, owned, or -- via
    `ReservedCardView` below -- reserved). `cost` only lists colors with a nonzero
    amount; a color absent from `cost` costs 0."""

    id: str
    tier: int
    bonus: Color
    points: int
    cost: dict[Color, int]


class ReservedCardView(CardView):
    """A `CardView` plus where it came from -- only ever attached to a reserved card,
    never a market/owned one. `"market"` means everyone at the table watched it leave
    the market the instant before it was reserved (not real hidden information, just
    made explicit instead of relying on memory); `"deck"` means it was reserved blind
    and no one but the owner has ever seen it -- genuinely secret, and the only actual
    hidden-information surface left in this game."""

    source: ReserveSource


class NobleView(TypedDict):
    id: str
    points: int
    requirement: dict[Color, int]  # bonus counts needed, e.g. {"white": 3, "blue": 3}


class TierView(TypedDict):
    face_up: list[CardView]  # up to 4 -- fewer once that tier's deck runs out
    remaining_in_deck: int  # face-down cards left in this tier, count only


class PlayerPublicView(TypedDict):
    """What's true about ANY player (including you) -- visible to everyone."""

    points: int
    bonuses: dict[Color, int]  # permanent discounts from owned cards
    tokens: dict[TokenColor, int]
    reserved_count: int  # total reserved, market-origin + blind-origin combined
    visible_reserved_cards: list[CardView]  # the market-origin subset, in full
    owned_count: int
    nobles: list[str]  # noble ids they've claimed


class PublicState(TypedDict):
    phase: Phase
    current_player: str
    turn_index: int
    done: bool
    winner: str | None
    final_round_trigger: str | None
    bank: dict[TokenColor, int]
    nobles: list[NobleView]
    market: dict[int, TierView]  # keys 1, 2, 3
    players: dict[str, PlayerPublicView]  # one entry per seat, 2 to 4 of them


class PrivateState(TypedDict):
    """Your own reserved cards, always in full (market- and blind-origin alike --
    you always know your own). This is the private/public split's *only* asymmetry:
    an opponent's `PlayerPublicView.visible_reserved_cards` shows you their
    market-origin reserves too, just not under `private_state` since they aren't
    yours; their blind-origin reserves are the one thing never shown to you."""

    your_reserved_cards: list[ReservedCardView]


class Context(TypedDict):
    opponent_ids: list[str]  # every other seat, in turn order (1 to 3 of them)
    colors: list[Color]  # ["white", "blue", "green", "red", "black"] -- gold is a wildcard, not a color
    reserve_limit: int  # 3
    token_limit: int  # 10 -- discard down to this if you go over
    win_threshold: int  # 15
    pending_noble_choices: list[str]  # noble ids, only non-empty during phase == "noble_choice"


class TakeTokensAction(TypedDict):
    type: Literal["take_tokens"]
    colors: list[Color]  # 3 distinct colors, or the same color twice -- never "gold"


class ReserveCardAction(TypedDict):
    type: Literal["reserve_card"]
    location: Literal["market", "deck"]
    tier: int
    card_id: NotRequired[str]  # present only when location == "market" -- a blind reserve doesn't know it yet


class PurchaseCardAction(TypedDict):
    type: Literal["purchase_card"]
    location: Literal["market", "reserved"]
    tier: int
    card_id: str


class DiscardTokenAction(TypedDict):
    type: Literal["discard_token"]
    color: TokenColor


class ChooseNobleAction(TypedDict):
    type: Literal["choose_noble"]
    noble_id: str


class PassAction(TypedDict):
    type: Literal["pass"]


SplendorAction = (
    TakeTokensAction | ReserveCardAction | PurchaseCardAction | DiscardTokenAction | ChooseNobleAction | PassAction
)


class SplendorObservation(TypedDict):
    public_state: PublicState
    private_state: PrivateState
    context: Context
    legal_actions: list[SplendorAction]
