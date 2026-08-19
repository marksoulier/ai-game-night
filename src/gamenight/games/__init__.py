from __future__ import annotations

from gamenight.core.registry import GameRegistry
from gamenight.games.battleship.game import BattleshipGame
from gamenight.games.connect_four.game import ConnectFourGame
from gamenight.games.mine_duel.game import MineDuelGame
from gamenight.games.splendor.game import SplendorGame
from gamenight.games.ticket_to_ride.game import TicketToRideGame
from gamenight.games.tictactoe.game import TicTacToeGame


def build_registry() -> GameRegistry:
    registry = GameRegistry()
    registry.register("tictactoe", TicTacToeGame)
    registry.register("connect_four", ConnectFourGame)
    registry.register("battleship", BattleshipGame)
    registry.register("splendor", SplendorGame)
    registry.register("mine_duel", MineDuelGame)
    registry.register("ticket_to_ride", TicketToRideGame)
    return registry
