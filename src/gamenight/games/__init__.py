from __future__ import annotations

from gamenight.core.registry import GameRegistry
from gamenight.games.connect_four.game import ConnectFourGame
from gamenight.games.tictactoe.game import TicTacToeGame


def build_registry() -> GameRegistry:
    registry = GameRegistry()
    registry.register(TicTacToeGame())
    registry.register(ConnectFourGame())
    return registry
