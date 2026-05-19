from __future__ import annotations

from gamenight.core.types import Action, MatchContext, Observation


class HumanTerminalBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        legal_actions = observation["legal_actions"]
        print("Legal actions:")
        for idx, action in enumerate(legal_actions):
            print(f"  {idx}: {action}")
        selected = int(input("Select action index: ").strip())
        return legal_actions[selected]
