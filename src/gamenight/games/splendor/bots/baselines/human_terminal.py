from __future__ import annotations

from gamenight.core.types import MatchContext
from gamenight.games.splendor.types import CardView, NobleView, SplendorAction, SplendorObservation

COLORS = ["white", "blue", "green", "red", "black"]


class HumanTerminalBot:
    """Prints the board, then lets a human pick a move by number.

    Splendor's actions are more varied in shape than a single (row, col) -- take
    tokens, reserve, purchase, discard, choose a noble -- so rather than parsing typed
    coordinates (as Battleship's HumanTerminalBot does for a single fixed shape), this
    prints every legal action as a numbered, human-readable line and asks for an index.
    """

    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: SplendorObservation, context: MatchContext) -> SplendorAction:
        self._print_board(observation)
        legal_actions = observation["legal_actions"]

        print(f"\n{len(legal_actions)} legal actions:")
        for index, action in enumerate(legal_actions):
            print(f"  [{index}] {self._describe(action, observation)}")

        while True:
            raw = input(f"Choose an action (0-{len(legal_actions) - 1}): ").strip()
            try:
                choice = int(raw)
            except ValueError:
                print("Enter a number from the list above.")
                continue
            if 0 <= choice < len(legal_actions):
                return legal_actions[choice]
            print("Out of range -- try again.")

    def _print_board(self, observation: SplendorObservation) -> None:
        public_state = observation["public_state"]
        private_state = observation["private_state"]
        current_player = public_state["current_player"]
        me = public_state["players"][current_player]

        print(f"\n=== Turn {public_state['turn_index']} -- {current_player} to act ({public_state['phase']}) ===")
        print("Bank: " + "  ".join(f"{c}={n}" for c, n in public_state["bank"].items()))

        if public_state["nobles"]:
            print("Nobles: " + ", ".join(self._noble_text(noble) for noble in public_state["nobles"]))

        for tier in (3, 2, 1):
            tier_info = public_state["market"][tier]
            print(f"Tier {tier} ({tier_info['remaining_in_deck']} left in deck):")
            for card in tier_info["face_up"]:
                print("  " + self._card_text(card))

        print(f"\nYour points: {me['points']}  |  bonuses: {me['bonuses']}  |  tokens: {me['tokens']}")
        if private_state["your_reserved_cards"]:
            print("Your reserved cards:")
            for card in private_state["your_reserved_cards"]:
                print(f"  ({card['source']}) " + self._card_text(card))

        for opponent_id in observation["context"]["opponent_ids"]:
            opponent = public_state["players"][opponent_id]
            blind_count = opponent["reserved_count"] - len(opponent["visible_reserved_cards"])
            print(
                f"{opponent_id}: {opponent['points']} pts  |  bonuses: {opponent['bonuses']}  |  "
                f"tokens: {opponent['tokens']}  |  reserved: {opponent['reserved_count']}"
                f" ({blind_count} blind, unknown)"
            )
            for card in opponent["visible_reserved_cards"]:
                print("    (seen from market) " + self._card_text(card))

    @staticmethod
    def _card_text(card: CardView) -> str:
        cost = "  ".join(f"{c}{card['cost'][c]}" for c in COLORS if card["cost"].get(c))
        points = f"+{card['points']}pt " if card["points"] else ""
        return f"[{card['id']}] {points}bonus={card['bonus']} cost=({cost})"

    @staticmethod
    def _noble_text(noble: NobleView) -> str:
        requirement = "  ".join(f"{c}{amount}" for c, amount in noble["requirement"].items())
        return f"[{noble['id']}] +{noble['points']}pt requires ({requirement})"

    def _describe(self, action: SplendorAction, observation: SplendorObservation) -> str:
        action_type = action["type"]
        if action_type == "take_tokens":
            colors = action["colors"]
            if len(colors) == 2 and colors[0] == colors[1]:
                return f"take 2x {colors[0]}"
            return f"take 1 each of: {', '.join(colors)}"
        if action_type == "reserve_card":
            if action["location"] == "deck":
                return f"reserve blind from tier {action['tier']} deck (+1 gold if available)"
            return f"reserve {action['card_id']} from tier {action['tier']} market (+1 gold if available)"
        if action_type == "purchase_card":
            where = "your reserved cards" if action["location"] == "reserved" else "the market"
            return f"purchase {action['card_id']} from {where}"
        if action_type == "discard_token":
            return f"discard 1 {action['color']} token"
        if action_type == "choose_noble":
            return f"claim noble {action['noble_id']}"
        if action_type == "pass":
            return "pass (no legal action available)"
        return str(action)
