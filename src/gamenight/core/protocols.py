from __future__ import annotations

from typing import Any, Protocol

from gamenight.core.types import Action, MatchContext, Observation, StepResult


class BotProtocol(Protocol):
    bot_id: str

    def reset(self, context: MatchContext) -> None:
        ...

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        ...


class GameProtocol(Protocol):
    game_id: str

    def create_initial_state(self, seed: int | None = None) -> Any:
        ...

    def current_player(self, state: Any) -> str:
        ...

    def legal_actions(self, state: Any, player_id: str) -> list[Action]:
        ...

    def observe(self, state: Any, player_id: str) -> Observation:
        ...

    def step(self, state: Any, action: Action) -> StepResult:
        ...

    def render_text(self, state: Any) -> str:
        ...
