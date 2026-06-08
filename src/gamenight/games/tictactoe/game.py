from __future__ import annotations

from dataclasses import dataclass

from gamenight.core.protocols import BotProtocol
from gamenight.core.types import Action, Observation, StepResult
from gamenight.games.tictactoe.bots.baselines.greedy_bot import GreedyBot
from gamenight.games.tictactoe.bots.baselines.human_terminal import HumanTerminalBot
from gamenight.games.tictactoe.bots.baselines.random_bot import RandomBot


WIN_LINES = [
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
]


@dataclass(slots=True)
class TicTacToeState:
    board: list[str]
    current_player: str
    turn_index: int
    done: bool
    winner: str | None


class TicTacToeGame:
    game_id = "tictactoe"
    player_ids = ["player_x", "player_o"]

    def build_baseline_bot(self, name: str, bot_id: str) -> BotProtocol:
        baseline = name.lower().strip()
        if baseline == "random":
            return RandomBot(bot_id=bot_id)
        if baseline == "human":
            return HumanTerminalBot(bot_id=bot_id)
        if baseline == "greedy":
            return GreedyBot(bot_id=bot_id)
        raise ValueError(f"Unknown bot name: {name}")

    def create_initial_state(self, seed: int | None = None) -> dict:
        return {
            "board": [" "] * 9,
            "current_player": "player_x",
            "turn_index": 0,
            "done": False,
            "winner": None,
        }

    def current_player(self, state: dict) -> str:
        return state["current_player"]

    def legal_actions(self, state: dict, player_id: str) -> list[Action]:
        if state["done"] or player_id != state["current_player"]:
            return []
        return [{"type": "place", "index": idx} for idx, value in enumerate(state["board"]) if value == " "]

    def observe(self, state: dict, player_id: str) -> Observation:
        marker = "X" if player_id == "player_x" else "O"
        opponent = "player_o" if player_id == "player_x" else "player_x"
        return {
            "public_state": {
                "board": state["board"],
                "current_player": state["current_player"],
                "turn_index": state["turn_index"],
                "done": state["done"],
                "winner": state["winner"],
            },
            "private_state": {
                "marker": marker,
            },
            "context": {
                "opponent_id": opponent,
                "board_size": 3,
                "win_length": 3,
            },
        }

    def step(self, state: dict, action: Action) -> StepResult:
        if state["done"]:
            return StepResult(next_state=state, rewards=self._rewards(state["winner"]), done=True)

        next_state = {
            "board": state["board"][:],
            "current_player": state["current_player"],
            "turn_index": state["turn_index"],
            "done": state["done"],
            "winner": state["winner"],
        }

        index = int(action["index"])
        marker = "X" if next_state["current_player"] == "player_x" else "O"
        next_state["board"][index] = marker
        next_state["turn_index"] += 1

        winner = self._winner(next_state["board"])
        board_full = all(cell != " " for cell in next_state["board"])

        if winner is not None:
            next_state["done"] = True
            next_state["winner"] = "player_x" if winner == "X" else "player_o"
        elif board_full:
            next_state["done"] = True
            next_state["winner"] = None
        else:
            next_state["current_player"] = "player_o" if next_state["current_player"] == "player_x" else "player_x"

        rewards = self._rewards(next_state["winner"])
        events = [{"type": "move", "index": index, "marker": marker}]
        return StepResult(next_state=next_state, rewards=rewards, done=next_state["done"], events=events)

    def render_text(self, state: dict) -> str:
        board = state["board"]
        rows = [
            f" {board[0]} | {board[1]} | {board[2]} ",
            "-----------",
            f" {board[3]} | {board[4]} | {board[5]} ",
            "-----------",
            f" {board[6]} | {board[7]} | {board[8]} ",
        ]
        return "\n".join(rows)

    def _winner(self, board: list[str]) -> str | None:
        for a, b, c in WIN_LINES:
            if board[a] != " " and board[a] == board[b] == board[c]:
                return board[a]
        return None

    def _rewards(self, winner: str | None) -> dict[str, float]:
        if winner == "player_x":
            return {"player_x": 1.0, "player_o": 0.0}
        if winner == "player_o":
            return {"player_x": 0.0, "player_o": 1.0}
        return {"player_x": 0.5, "player_o": 0.5}
