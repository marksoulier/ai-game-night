from __future__ import annotations

from dataclasses import dataclass

from gamenight.core.protocols import GameProtocol


@dataclass(slots=True)
class GameRegistration:
    game_id: str
    game: GameProtocol


class GameRegistry:
    def __init__(self) -> None:
        self._games: dict[str, GameProtocol] = {}

    def register(self, game: GameProtocol) -> None:
        self._games[game.game_id] = game

    def get(self, game_id: str) -> GameProtocol:
        if game_id not in self._games:
            raise KeyError(f"Unknown game_id: {game_id}")
        return self._games[game_id]

    def list_game_ids(self) -> list[str]:
        return sorted(self._games.keys())
