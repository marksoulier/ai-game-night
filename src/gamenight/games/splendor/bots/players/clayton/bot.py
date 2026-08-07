from __future__ import annotations

from gamenight.core.types import MatchContext
from gamenight.games.splendor.types import (
    CardView,
    SplendorAction,
    SplendorObservation,
)

COLORS = ["white", "blue", "green", "red", "black"]


class SimulatedState:
    def __init__(self, points, tokens, bonuses, reserved_ids, claimed_noble_ids):
        self.points = points
        self.tokens = dict(tokens)
        self.bonuses = dict(bonuses)
        self.reserved_ids = list(reserved_ids)
        self.claimed_noble_ids = list(claimed_noble_ids)

    def copy(self):
        return SimulatedState(
            self.points,
            self.tokens,
            self.bonuses,
            self.reserved_ids,
            self.claimed_noble_ids
        )


class PlayerBot:
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

        # Analyze game state and opponent
        me_id = observation["public_state"]["current_player"]
        me_state = observation["public_state"]["players"][me_id]
        current_points = me_state["points"]
        total_bonuses = sum(me_state["bonuses"].values())

        # Check for immediate or multi-step winning paths (up to 3 moves ahead)
        visible_cards = self._all_visible_cards(observation)
        all_nobles = observation["public_state"]["nobles"]
        
        initial_state = SimulatedState(
            points=me_state["points"],
            tokens=me_state["tokens"],
            bonuses=me_state["bonuses"],
            reserved_ids=[c["id"] for c in observation["private_state"]["your_reserved_cards"]],
            claimed_noble_ids=[n for n in me_state["nobles"]]
        )

        winning_path = self._find_winning_path(initial_state, legal_actions, visible_cards, all_nobles)
        if winning_path:
            target_act = winning_path[0]
            for act in legal_actions:
                if act["type"] == target_act["type"]:
                    if act["type"] == "purchase_card" and act["card_id"] == target_act["card_id"]:
                        return act
                    if act["type"] == "take_tokens" and set(act["colors"]) == set(target_act["colors"]):
                        return act
                    if act["type"] == "reserve_card" and act.get("card_id") == target_act.get("card_id"):
                        return act

        # Detect opponent strategy and adapt parameters dynamically
        opp_strategy = self._detect_opponent_strategy(observation)
        if opp_strategy == "greedy":
            early_pts = 15.0
            early_weight_mult = 0.5
            cost_penalty = 0.1
            late_pts_threshold = 6
            bonus_threshold = 7
            block_missing_threshold = 3
            block_score = 150.0
            use_efficiency = True
        elif opp_strategy == "noble_spammer":
            # Evolved vs Mark (Noble Rusher)
            early_pts = 25.86
            early_weight_mult = 1.62
            cost_penalty = 0.07
            late_pts_threshold = 6
            bonus_threshold = 12
            block_missing_threshold = 2
            block_score = 279.57
            use_efficiency = False
        elif opp_strategy == "balanced_mirror":
            # Evolved vs Hunter (Balanced Opponent)
            early_pts = 15.16
            early_weight_mult = 1.05
            cost_penalty = 0.44
            late_pts_threshold = 9
            bonus_threshold = 5
            block_missing_threshold = 2
            block_score = 68.61
            use_efficiency = True
        else:
            # Baseline / Unknown (Early Game)
            early_pts = 5.0
            early_weight_mult = 1.0
            cost_penalty = 0.2
            late_pts_threshold = 8
            bonus_threshold = 9
            block_missing_threshold = 2
            block_score = 150.0
            use_efficiency = True

        is_late_game = (current_points >= late_pts_threshold or total_bonuses >= bonus_threshold)

        purchases = [a for a in legal_actions if a["type"] == "purchase_card"]
        color_weights = self._get_color_weights(observation)
        visible_cards = self._all_visible_cards(observation)

        # Early game card efficiency: filter out purchases that do not align with our goals
        synergistic_purchases = []
        for act in purchases:
            card = visible_cards[act["card_id"]]
            weight = color_weights.get(card["bonus"], 0.0)
            # Synergistic if it has direct points or contributes to a noble/high-point cost
            if card["points"] > 0 or weight > 0.0:
                synergistic_purchases.append(act)

        # Prioritize purchases according to efficiency filter setting
        prioritized_purchases = purchases if (is_late_game or not use_efficiency) else synergistic_purchases

        # Action Phase:
        # 1. Prioritized (Synergistic) purchases first
        if prioritized_purchases:
            def purchase_score(act: SplendorAction) -> float:
                card = visible_cards[act["card_id"]]
                points = card["points"]
                bonus_color = card["bonus"]
                weight = color_weights.get(bonus_color, 0.0)

                block_score_val = 0.0
                if weight > 0.0 and self._is_opponent_saving_for(observation, card, block_missing_threshold):
                    block_score_val = block_score

                total_cost = sum(card["cost"].values())

                if is_late_game:
                    return block_score_val + 100.0 * points + weight - 0.1 * total_cost
                else:
                    return block_score_val + early_pts * points + early_weight_mult * weight - cost_penalty * total_cost

            return max(prioritized_purchases, key=purchase_score)

        # 2. Take tokens if any are legal (using our noble and high-point cost demands)
        takes = [a for a in legal_actions if a["type"] == "take_tokens"]
        if takes:
            color_demand = self._get_color_demand(observation, color_weights)

            def take_score(act: SplendorAction) -> tuple[bool, bool, float]:
                colors = act["colors"]
                is_three = len(colors) == 3
                is_distinct = len(set(colors)) == len(colors)
                demand_sum = sum(color_demand.get(c, 0.0) for c in colors)
                return (is_three, is_distinct, demand_sum)

            return max(takes, key=take_score)

        # 3. Fallback: Purchase a non-synergistic card only if we cannot take tokens
        if purchases:
            def fallback_purchase_score(act: SplendorAction) -> float:
                card = visible_cards[act["card_id"]]
                total_cost = sum(card["cost"].values())
                return -total_cost  # Prefer cheaper fallback cards to save resources

            return max(purchases, key=fallback_purchase_score)

        # 4. Reserve cards as a last resort
        reserves = [a for a in legal_actions if a["type"] == "reserve_card"]
        if reserves:
            def reserve_score(act: SplendorAction) -> tuple[int, int]:
                if act["location"] == "deck":
                    return (act["tier"], -1)
                card = visible_cards[act["card_id"]]
                return (card["points"], card["tier"])
            return max(reserves, key=reserve_score)

        # 5. Pass if absolutely nothing else is legal.
        return legal_actions[0]

    def _choose_discard(self, observation: SplendorObservation, legal_actions: list[SplendorAction]) -> SplendorAction:
        color_weights = self._get_color_weights(observation)
        color_demand = self._get_color_demand(observation, color_weights)

        def discard_score(act: SplendorAction) -> float:
            color = act["color"]
            if color == "gold":
                return -1000.0
            return -color_demand.get(color, 0.0)

        return max(legal_actions, key=discard_score)

    def _detect_opponent_strategy(self, observation: SplendorObservation) -> str:
        """Classifies the primary opponent's play style based on their points-per-card ratio."""
        current_player = observation["public_state"]["current_player"]
        opponents = [pid for pid in observation["public_state"]["players"] if pid != current_player]
        if not opponents:
            return "unknown"

        opp_id = opponents[0]
        opp_state = observation["public_state"]["players"][opp_id]
        opp_points = opp_state["points"]
        opp_cards = opp_state["owned_count"]

        if opp_cards < 3:
            return "unknown"

        # Calculate average points per card (excluding noble points)
        dev_points = opp_points - 3 * len(opp_state["nobles"])
        pts_per_card = dev_points / opp_cards

        if pts_per_card >= 0.4:
            return "greedy"  # Points rushing
        elif opp_cards >= 5 and pts_per_card <= 0.2:
            return "noble_spammer"  # Noble rushing (like Mark)
        else:
            return "balanced_mirror"  # Balanced / economy (like Hunter)

    def _get_color_weights(self, observation: SplendorObservation) -> dict[str, float]:
        """Calculates color weights based on Nobles (primary) and costs of high-point cards (secondary)."""
        visible_cards = self._all_visible_cards(observation)
        high_point_cards = [c for c in visible_cards.values() if c["points"] >= 2]

        weights = {c: 0.0 for c in COLORS}

        # 1. Base Nobles (3.0 * requirement)
        for noble in observation["public_state"]["nobles"]:
            for color, req in noble["requirement"].items():
                if color in weights:
                    weights[color] += 3.0 * req

        # 2. Base high-point card costs (1.0 * cost)
        for card in high_point_cards:
            for color, cost in card["cost"].items():
                if color in weights:
                    weights[color] += float(cost)

        return weights

    def _missing_for_player(self, player_state: dict, card: CardView) -> int:
        """Returns the number of tokens a player is missing to buy a card, accounting for bonuses and gold."""
        bonuses = player_state["bonuses"]
        tokens = player_state["tokens"]
        missing = 0
        for color, cost in card["cost"].items():
            have = bonuses.get(color, 0) + tokens.get(color, 0)
            if have < cost:
                missing += cost - have
        gold = tokens.get("gold", 0)
        return max(0, missing - gold)

    def _is_opponent_saving_for(self, observation: SplendorObservation, card: CardView, missing_threshold: int) -> bool:
        """Checks if any opponent is close to purchasing the card (missing <= missing_threshold tokens)."""
        current_player = observation["public_state"]["current_player"]
        opponents = [pid for pid in observation["public_state"]["players"] if pid != current_player]
        for opp_id in opponents:
            opp_state = observation["public_state"]["players"][opp_id]
            if self._missing_for_player(opp_state, card) <= missing_threshold:
                return True
        return False

    def _all_visible_cards(self, observation: SplendorObservation) -> dict[str, CardView]:
        """Returns a combined dictionary of all face-up market cards and own reserved cards."""
        cards = {}
        for tier_info in observation["public_state"]["market"].values():
            for card in tier_info["face_up"]:
                cards[card["id"]] = card
        for card in observation["private_state"]["your_reserved_cards"]:
            cards[card["id"]] = card
        return cards

    def _get_color_demand(self, observation: SplendorObservation, color_weights: dict[str, float]) -> dict[str, float]:
        """Dynamically computes the demand for each color based on what is needed to buy desirable cards
        and defensively blocking tokens needed for opponents' reserved/market cards."""
        me_id = observation["public_state"]["current_player"]
        me_state = observation["public_state"]["players"][me_id]

        # Baseline demand is the static weights
        demand = {c: color_weights.get(c, 0.0) for c in COLORS}

        # 1. Dynamic demand based on cards in market/reserve
        visible_cards = self._all_visible_cards(observation)
        for card in visible_cards.values():
            card_pts = card["points"]
            bonus_color = card["bonus"]
            interest = 10.0 * card_pts + color_weights.get(bonus_color, 0.0)

            missing_total = self._missing_for_player(me_state, card)

            for color, cost in card["cost"].items():
                if color not in COLORS:
                    continue
                # If we still need this color to purchase this card
                have = me_state["bonuses"].get(color, 0) + me_state["tokens"].get(color, 0)
                if have < cost:
                    # Divisor prioritizing cards we are closer to buying
                    demand[color] += interest / (missing_total + 1)

        # 2. Defensive demand: block opponents from getting tokens they need for their reserved cards
        opponents = [pid for pid in observation["public_state"]["players"] if pid != me_id]
        for opp_id in opponents:
            opp_state = observation["public_state"]["players"][opp_id]
            for card in opp_state["visible_reserved_cards"]:
                missing_total = self._missing_for_player(opp_state, card)
                if missing_total <= 2:
                    for color, cost in card["cost"].items():
                        if color not in COLORS:
                            continue
                        have = opp_state["bonuses"].get(color, 0) + opp_state["tokens"].get(color, 0)
                        if have < cost:
                            # Add defensive weight to block them
                            interest = 5.0 * card["points"] + 1.0
                            demand[color] += interest / (missing_total + 1)

        return demand

    def _can_afford(self, state: SimulatedState, card) -> tuple[bool, dict[str, int]]:
        tokens = state.tokens.copy()
        bonuses = state.bonuses
        
        pay_tokens = {}
        missing_gold = 0
        
        for color, cost in card["cost"].items():
            have_bonus = bonuses.get(color, 0)
            if have_bonus >= cost:
                continue
            needed = cost - have_bonus
            have_token = tokens.get(color, 0)
            if have_token >= needed:
                pay_tokens[color] = needed
            else:
                pay_tokens[color] = have_token
                missing_gold += needed - have_token
                
        if missing_gold <= tokens.get("gold", 0):
            pay_tokens["gold"] = missing_gold
            return True, pay_tokens
        return False, {}

    def _apply_simulated_action(self, state: SimulatedState, act, visible_cards, all_nobles):
        next_state = state.copy()
        
        if act["type"] == "purchase_card":
            card = visible_cards[act["card_id"]]
            affords, pay = self._can_afford(next_state, card)
            if affords:
                for color, val in pay.items():
                    next_state.tokens[color] -= val
                next_state.bonuses[card["bonus"]] = next_state.bonuses.get(card["bonus"], 0) + 1
                next_state.points += card["points"]
                for noble in all_nobles:
                    if noble["id"] not in next_state.claimed_noble_ids:
                        if all(next_state.bonuses.get(color, 0) >= req for color, req in noble["requirement"].items()):
                            next_state.points += 3
                            next_state.claimed_noble_ids.append(noble["id"])
                if card["id"] in next_state.reserved_ids:
                    next_state.reserved_ids.remove(card["id"])
                    
        elif act["type"] == "take_tokens":
            for color in act["colors"]:
                next_state.tokens[color] = next_state.tokens.get(color, 0) + 1
            total_tokens = sum(next_state.tokens.values())
            if total_tokens > 10:
                excess = total_tokens - 10
                for _ in range(excess):
                    for c in COLORS:
                        if next_state.tokens.get(c, 0) > 0:
                            next_state.tokens[c] -= 1
                            break
                            
        elif act["type"] == "reserve_card":
            if act.get("card_id"):
                next_state.reserved_ids.append(act["card_id"])
            next_state.tokens["gold"] = next_state.tokens.get("gold", 0) + 1
            
        return next_state

    def _get_simulated_legal_actions(self, state: SimulatedState, visible_cards) -> list:
        actions = []
        
        for card_id, card in visible_cards.items():
            affords, _ = self._can_afford(state, card)
            if affords:
                actions.append({"type": "purchase_card", "card_id": card_id})
                
        available_colors = [c for c in COLORS if state.tokens.get(c, 0) < 4]
        if len(available_colors) >= 3:
            actions.append({"type": "take_tokens", "colors": available_colors[:3]})
            
        if len(state.reserved_ids) < 3:
            for card_id, card in visible_cards.items():
                if card_id not in state.reserved_ids and card["tier"] <= 2:
                    actions.append({"type": "reserve_card", "card_id": card_id})
                    break
                    
        return actions

    def _find_winning_path(self, initial_state: SimulatedState, legal_actions, visible_cards, all_nobles) -> list | None:
        for act in legal_actions:
            if act["type"] == "purchase_card":
                next_state = self._apply_simulated_action(initial_state, act, visible_cards, all_nobles)
                if next_state.points >= 15:
                    return [act]

        for act1 in legal_actions:
            s1 = self._apply_simulated_action(initial_state, act1, visible_cards, all_nobles)
            s1_actions = self._get_simulated_legal_actions(s1, visible_cards)
            for act2 in s1_actions:
                if act2["type"] == "purchase_card":
                    s2 = self._apply_simulated_action(s1, act2, visible_cards, all_nobles)
                    if s2.points >= 15:
                        return [act1, act2]

        for act1 in legal_actions:
            s1 = self._apply_simulated_action(initial_state, act1, visible_cards, all_nobles)
            s1_actions = self._get_simulated_legal_actions(s1, visible_cards)
            for act2 in s1_actions:
                s2 = self._apply_simulated_action(s1, act2, visible_cards, all_nobles)
                s2_actions = self._get_simulated_legal_actions(s2, visible_cards)
                for act3 in s2_actions:
                    if act3["type"] == "purchase_card":
                        s3 = self._apply_simulated_action(s2, act3, visible_cards, all_nobles)
                        if s3.points >= 15:
                            return [act1, act2, act3]

        return None
