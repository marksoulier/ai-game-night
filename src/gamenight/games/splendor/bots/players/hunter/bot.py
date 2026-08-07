from __future__ import annotations

from gamenight.core.types import MatchContext
from gamenight.games.splendor.types import CardView, SplendorAction, SplendorObservation

COLORS = ["white", "blue", "green", "red", "black"]


class PlayerBot:
    """Hunter's aggressive points Splendor bot.

    Strategy:
    - Buy early cards freely to establish bonuses.
    - After the first couple cards, prefer cards whose bonus-adjusted cost is 2 or less.
    - Break the cheap-card rule for immediate wins, noble claims, or strong point cards.
    - Spend crowded token hands on cards instead of drifting into discard turns.
    - Never reserve unless the engine leaves no other legal action.
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

        purchases = [action for action in legal_actions if action["type"] == "purchase_card"]
        eligible_purchases = self._eligible_purchases(observation, purchases)
        if eligible_purchases:
            return self._best_purchase(observation, eligible_purchases)

        current_player = observation["public_state"]["current_player"]
        me = observation["public_state"]["players"][current_player]
        if purchases and sum(me["tokens"].values()) >= 6:
            return self._best_purchase(observation, purchases)

        takes = [action for action in legal_actions if action["type"] == "take_tokens"]
        if takes:
            return self._best_take(observation, takes)

        if purchases:
            return self._best_purchase(observation, purchases)

        non_reserves = [action for action in legal_actions if action["type"] != "reserve_card"]
        if non_reserves:
            return non_reserves[0]

        return legal_actions[0]

    def _eligible_purchases(
        self, observation: SplendorObservation, purchases: list[SplendorAction]
    ) -> list[SplendorAction]:
        current_player = observation["public_state"]["current_player"]
        me = observation["public_state"]["players"][current_player]
        if me["owned_count"] < 2:
            return purchases

        cards = self._visible_cards(observation)
        win_threshold = observation["context"]["win_threshold"]
        eligible = []
        for action in purchases:
            card = cards[action["card_id"]]
            remaining_cost = self._remaining_cost(card, me["bonuses"])
            wins_now = me["points"] + card["points"] >= win_threshold
            claims_noble = self._noble_points_claimed(observation, card["bonus"]) > 0
            point_race_card = card["points"] >= 2 and (me["owned_count"] >= 5 or me["points"] >= 5)
            cheap_card = remaining_cost <= 2
            if wins_now or claims_noble or point_race_card or cheap_card:
                eligible.append(action)
        return eligible

    def _best_purchase(self, observation: SplendorObservation, purchases: list[SplendorAction]) -> SplendorAction:
        cards = self._visible_cards(observation)
        current_player = observation["public_state"]["current_player"]
        me = observation["public_state"]["players"][current_player]
        win_threshold = observation["context"]["win_threshold"]

        bonus_demand = self._color_demand(observation)

        def score(action: SplendorAction) -> tuple[int, int, int, int, int, int, int]:
            card = cards[action["card_id"]]
            wins_now = int(me["points"] + card["points"] >= win_threshold)
            noble_points = self._noble_points_claimed(observation, card["bonus"])
            noble_progress = self._noble_progress(observation, card["bonus"])
            cost_after_bonuses = self._remaining_cost(card, me["bonuses"])
            point_density = (card["points"] + noble_points) * 100 // max(1, cost_after_bonuses)
            return (
                wins_now,
                card["points"] + noble_points,
                point_density,
                card["points"],
                noble_progress,
                bonus_demand.get(card["bonus"], 0),
                -cost_after_bonuses,
            )

        return max(purchases, key=score)

    def _best_take(self, observation: SplendorObservation, takes: list[SplendorAction]) -> SplendorAction:
        current_player = observation["public_state"]["current_player"]
        me = observation["public_state"]["players"][current_player]
        token_count = sum(me["tokens"].values())
        token_limit = observation["context"]["token_limit"]
        demand = self._color_demand(observation)

        def score(action: SplendorAction) -> tuple[int, int, int, int]:
            colors = action["colors"]
            overflow = max(0, token_count + len(colors) - token_limit)
            distinct_colors = int(len(set(colors)) == len(colors))
            demand_score = sum(demand.get(color, 0) for color in colors)
            return (-overflow, distinct_colors, demand_score, len(colors))

        return max(takes, key=score)

    def _choose_discard(
        self, observation: SplendorObservation, legal_actions: list[SplendorAction]
    ) -> SplendorAction:
        current_player = observation["public_state"]["current_player"]
        tokens = observation["public_state"]["players"][current_player]["tokens"]
        demand = self._color_demand(observation)

        def score(action: SplendorAction) -> tuple[int, int, int]:
            color = action["color"]
            gold_penalty = int(color == "gold")
            usefulness = demand.get(color, 0)
            return (-gold_penalty, tokens[color], -usefulness)

        return max(legal_actions, key=score)

    def _visible_cards(self, observation: SplendorObservation) -> dict[str, CardView]:
        cards: dict[str, CardView] = {}
        for tier in observation["public_state"]["market"].values():
            for card in tier["face_up"]:
                cards[card["id"]] = card
        for card in observation["private_state"]["your_reserved_cards"]:
            cards[card["id"]] = card
        return cards

    def _color_demand(self, observation: SplendorObservation) -> dict[str, int]:
        current_player = observation["public_state"]["current_player"]
        me = observation["public_state"]["players"][current_player]
        demand = {color: 0 for color in COLORS}

        target_cards: list[CardView] = []
        for tier in observation["public_state"]["market"].values():
            target_cards.extend(tier["face_up"])
        target_cards.extend(observation["private_state"]["your_reserved_cards"])
        target_cards.sort(key=lambda card: self._token_target_score(card, me), reverse=True)
        target_cards = target_cards[:5]

        for card in target_cards:
            tier_weight = card["tier"]
            point_weight = (card["points"] + 1) ** 2
            for color, amount in card["cost"].items():
                missing = max(0, amount - me["bonuses"].get(color, 0) - me["tokens"].get(color, 0))
                demand[color] += missing * tier_weight * point_weight

        return demand

    def _token_target_score(self, card: CardView, me: dict) -> tuple[int, int, int, int]:
        missing_cost = self._missing_cost(card, me["bonuses"], me["tokens"])
        point_density = card["points"] * 100 // max(1, missing_cost)
        return (card["points"], point_density, card["tier"], -missing_cost)

    def _noble_points_claimed(self, observation: SplendorObservation, bonus_color: str) -> int:
        current_player = observation["public_state"]["current_player"]
        bonuses = observation["public_state"]["players"][current_player]["bonuses"]
        points = 0
        for noble in observation["public_state"]["nobles"]:
            qualifies = True
            for color, required in noble["requirement"].items():
                after_purchase = bonuses.get(color, 0) + int(color == bonus_color)
                if after_purchase < required:
                    qualifies = False
                    break
            if qualifies:
                points = max(points, noble["points"])
        return points

    def _noble_progress(self, observation: SplendorObservation, bonus_color: str) -> int:
        current_player = observation["public_state"]["current_player"]
        bonuses = observation["public_state"]["players"][current_player]["bonuses"]
        best_progress = 0
        for noble in observation["public_state"]["nobles"]:
            if bonus_color not in noble["requirement"]:
                continue
            met = 0
            for color, required in noble["requirement"].items():
                after_purchase = bonuses.get(color, 0) + int(color == bonus_color)
                met += min(after_purchase, required)
            best_progress = max(best_progress, met)
        return best_progress

    @staticmethod
    def _remaining_cost(card: CardView, bonuses: dict[str, int]) -> int:
        return sum(max(0, amount - bonuses.get(color, 0)) for color, amount in card["cost"].items())

    @staticmethod
    def _missing_cost(card: CardView, bonuses: dict[str, int], tokens: dict[str, int]) -> int:
        return sum(
            max(0, amount - bonuses.get(color, 0) - tokens.get(color, 0))
            for color, amount in card["cost"].items()
        )
