from __future__ import annotations

import random

from gamenight.core.types import Action, MatchContext, Observation


class PlayerBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        return random.choice(observation["legal_actions"])
