from __future__ import annotations

from gamenight.core.types import Action, MatchContext, Observation


class PlayerBot:
    def __init__(self, bot_id: str = "Josh") -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        legal_actions = observation["legal_actions"]
        if not legal_actions:
            raise ValueError("No legal actions available")
        return legal_actions[0]
