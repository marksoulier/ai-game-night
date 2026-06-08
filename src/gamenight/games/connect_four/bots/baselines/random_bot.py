from __future__ import annotations

import random

from gamenight.core.types import Action, MatchContext, Observation


class RandomBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        legal_actions = observation["legal_actions"]
        return random.choice(legal_actions)
