from __future__ import annotations

from gamenight.core.types import MatchContext
from gamenight.games.splendor.types import CardView, SplendorAction, SplendorObservation

COLORS = ["white", "blue", "green", "red", "black"]


class GreedyBot:
    """A layered-heuristic Splendor bot: buy > reserve > take tokens > pass.

    No optimal strategy is known for Splendor (see ../../README.md's "Is Splendor
    Solved?" section) -- this is the same kind of "clearly better than random,"
    well-studied-heuristic bot the other games' GreedyBots use, shaped to Splendor's
    actual turn structure (one main action, then an automatic discard/noble sub-step
    the engine drives on its own -- see BOT_SPEC.md's phase table):

    - **Purchase, when possible**: converting tokens into permanent points/bonuses is
      almost always good. Win immediately if a purchase reaches the win threshold;
      otherwise prefer the highest-point affordable card, tie-broken toward the
      cheapest (fewest total gems) so tokens aren't wasted on an equally-good buy.
    - **Reserve, when nothing's affordable**: grab the highest-point card currently
      face-up (denying it to the opponent and banking a future purchase, plus the free
      gold token that comes with reserving).
    - **Take tokens, as a fallback**: prefer "3 different" over "2 same" (more
      flexible), weighted toward whichever colors the current market actually demands
      -- see `_color_demand`.
    - **Discard** (when forced over the 10-token limit): give up whichever color is
      currently held in the largest amount, keeping gold last (it substitutes for
      anything).
    - **Noble choice** (when more than one qualifies at once): take the first one
      offered -- in this implementation every noble is worth the same 3 points, so
      there's no scoring difference between them.
    """

    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: SplendorObservation, context: MatchContext) -> SplendorAction:
        legal_actions = observation["legal_actions"]
        phase = observation["public_state"]["phase"]

        if phase == "discard":
            return self._choose_discard(observation, legal_actions)
        if phase == "noble_choice":
            return legal_actions[0]
        return self._choose_main_action(observation, legal_actions)

    # -- main action: purchase > reserve > take tokens > pass -------------------------

    def _choose_main_action(
        self, observation: SplendorObservation, legal_actions: list[SplendorAction]
    ) -> SplendorAction:
        purchases = [a for a in legal_actions if a["type"] == "purchase_card"]
        if purchases:
            return self._best_purchase(observation, purchases)

        reserves = [a for a in legal_actions if a["type"] == "reserve_card"]
        if reserves:
            return self._best_reserve(observation, reserves)

        takes = [a for a in legal_actions if a["type"] == "take_tokens"]
        if takes:
            return self._best_take(observation, takes)

        return legal_actions[0]  # the {"type": "pass"} safety valve

    def _best_purchase(self, observation: SplendorObservation, purchases: list[SplendorAction]) -> SplendorAction:
        cards_by_id = self._all_visible_cards(observation)
        win_threshold = observation["context"]["win_threshold"]
        my_points = observation["public_state"]["players"][observation["public_state"]["current_player"]]["points"]

        def score(action: SplendorAction):
            card = cards_by_id[action["card_id"]]
            wins_now = my_points + card["points"] >= win_threshold
            total_cost = sum(card["cost"].values())
            return (wins_now, card["points"], -total_cost)

        return max(purchases, key=score)

    def _best_reserve(self, observation: SplendorObservation, reserves: list[SplendorAction]) -> SplendorAction:
        cards_by_id = self._all_visible_cards(observation)

        def score(action: SplendorAction):
            if action["location"] == "deck":
                return (action["tier"], -1)  # blind reserve: prefer the highest tier, no points to compare
            card = cards_by_id[action["card_id"]]
            return (card["points"], card["tier"])

        return max(reserves, key=score)

    def _best_take(self, observation: SplendorObservation, takes: list[SplendorAction]) -> SplendorAction:
        demand = self._color_demand(observation)

        def score(action: SplendorAction):
            colors = action["colors"]
            distinct = len(set(colors)) == len(colors)
            return (distinct, sum(demand.get(c, 0) for c in colors))

        return max(takes, key=score)

    @staticmethod
    def _all_visible_cards(observation: SplendorObservation) -> dict[str, CardView]:
        cards: dict[str, CardView] = {}
        for tier_info in observation["public_state"]["market"].values():
            for card in tier_info["face_up"]:
                cards[card["id"]] = card
        for card in observation["private_state"]["your_reserved_cards"]:
            cards[card["id"]] = card
        return cards

    @staticmethod
    def _color_demand(observation: SplendorObservation) -> dict[str, int]:
        """Total gem amount each color is currently priced at across the face-up
        market -- a cheap proxy for "which colors will I actually need soon."
        """
        demand = {color: 0 for color in COLORS}
        for tier_info in observation["public_state"]["market"].values():
            for card in tier_info["face_up"]:
                for color, amount in card["cost"].items():
                    demand[color] += amount
        return demand

    # -- discard: give up whatever you're holding the most of, gold last -------------

    def _choose_discard(
        self, observation: SplendorObservation, legal_actions: list[SplendorAction]
    ) -> SplendorAction:
        current_player = observation["public_state"]["current_player"]
        tokens = observation["public_state"]["players"][current_player]["tokens"]

        def score(action: SplendorAction):
            color = action["color"]
            return (color != "gold", tokens[color])

        return max(legal_actions, key=score)
