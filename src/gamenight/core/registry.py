from __future__ import annotations

from typing import Callable

from gamenight.core.protocols import GameProtocol


class GameRegistry:
    """Maps a `game_id` to a *factory* (usually just the game class itself) rather
    than a fixed instance.

    Most games are fixed-player-count and take no constructor arguments, so
    `registry.get(game_id)` with no kwargs behaves exactly like the old
    instance-per-game-id registry. Games that support a configurable player count
    (see `SplendorGame`'s `MIN_PLAYERS`/`MAX_PLAYERS`) accept kwargs like
    `num_players`, so `registry.get(game_id, num_players=3)` builds a freshly-sized
    instance for that match rather than sharing one fixed instance across every match.
    """

    def __init__(self) -> None:
        self._factories: dict[str, Callable[..., GameProtocol]] = {}

    def register(self, game_id: str, factory: Callable[..., GameProtocol]) -> None:
        self._factories[game_id] = factory

    def get(self, game_id: str, **kwargs) -> GameProtocol:
        if game_id not in self._factories:
            raise KeyError(f"Unknown game_id: {game_id}")
        return self._factories[game_id](**kwargs)

    def list_game_ids(self) -> list[str]:
        return sorted(self._factories.keys())
