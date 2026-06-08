from __future__ import annotations

from gamenight.core.protocols import BotProtocol
from gamenight.core.types import Action, Observation, StepResult
from gamenight.games.connect_four.bots.baselines.greedy_bot import GreedyBot
from gamenight.games.connect_four.bots.baselines.human_terminal import HumanTerminalBot
from gamenight.games.connect_four.bots.baselines.random_bot import RandomBot


COLUMNS = 7
ROWS = 6
CONNECT_LENGTH = 4


def _index(row: int, col: int) -> int:
    return row * COLUMNS + col


def _generate_win_lines() -> list[tuple[int, int, int, int]]:
    lines: list[tuple[int, int, int, int]] = []

    for row in range(ROWS):
        for col in range(COLUMNS - CONNECT_LENGTH + 1):
            lines.append(tuple(_index(row, col + offset) for offset in range(CONNECT_LENGTH)))

    for col in range(COLUMNS):
        for row in range(ROWS - CONNECT_LENGTH + 1):
            lines.append(tuple(_index(row + offset, col) for offset in range(CONNECT_LENGTH)))

    for row in range(ROWS - CONNECT_LENGTH + 1):
        for col in range(COLUMNS - CONNECT_LENGTH + 1):
            lines.append(tuple(_index(row + offset, col + offset) for offset in range(CONNECT_LENGTH)))

    for row in range(ROWS - CONNECT_LENGTH + 1):
        for col in range(CONNECT_LENGTH - 1, COLUMNS):
            lines.append(tuple(_index(row + offset, col - offset) for offset in range(CONNECT_LENGTH)))

    return lines


WIN_LINES = _generate_win_lines()


class ConnectFourGame:
    game_id = "connect_four"
    player_ids = ["player_red", "player_yellow"]

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
            "board": [" "] * (COLUMNS * ROWS),
            "current_player": "player_red",
            "turn_index": 0,
            "done": False,
            "winner": None,
        }

    def current_player(self, state: dict) -> str:
        return state["current_player"]

    def legal_actions(self, state: dict, player_id: str) -> list[Action]:
        if state["done"] or player_id != state["current_player"]:
            return []
        board = state["board"]
        return [
            {"type": "drop", "column": col}
            for col in range(COLUMNS)
            if board[_index(0, col)] == " "
        ]

    def observe(self, state: dict, player_id: str) -> Observation:
        marker = "R" if player_id == "player_red" else "Y"
        opponent = "player_yellow" if player_id == "player_red" else "player_red"
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
                "columns": COLUMNS,
                "rows": ROWS,
                "win_length": CONNECT_LENGTH,
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

        column = int(action["column"])
        marker = "R" if next_state["current_player"] == "player_red" else "Y"
        landing_row = self._landing_row(next_state["board"], column)
        landing_index = _index(landing_row, column)
        next_state["board"][landing_index] = marker
        next_state["turn_index"] += 1

        winner = self._winner(next_state["board"])
        board_full = all(cell != " " for cell in next_state["board"])

        if winner is not None:
            next_state["done"] = True
            next_state["winner"] = "player_red" if winner == "R" else "player_yellow"
        elif board_full:
            next_state["done"] = True
            next_state["winner"] = None
        else:
            next_state["current_player"] = (
                "player_yellow" if next_state["current_player"] == "player_red" else "player_red"
            )

        rewards = self._rewards(next_state["winner"])
        events = [{"type": "drop", "column": column, "row": landing_row, "marker": marker}]
        return StepResult(next_state=next_state, rewards=rewards, done=next_state["done"], events=events)

    def render_text(self, state: dict) -> str:
        board = state["board"]
        header = " " + " ".join(str(col) for col in range(COLUMNS))
        rows = [header]
        for row in range(ROWS):
            cells = [board[_index(row, col)] for col in range(COLUMNS)]
            rows.append("|" + "|".join(cells) + "|")
        rows.append("+" + "+".join("-" for _ in range(COLUMNS)) + "+")
        return "\n".join(rows)

    def _landing_row(self, board: list[str], column: int) -> int:
        for row in range(ROWS - 1, -1, -1):
            if board[_index(row, column)] == " ":
                return row
        raise ValueError(f"Column {column} is full")

    def _winner(self, board: list[str]) -> str | None:
        for line in WIN_LINES:
            first = board[line[0]]
            if first != " " and all(board[cell] == first for cell in line[1:]):
                return first
        return None

    def _rewards(self, winner: str | None) -> dict[str, float]:
        if winner == "player_red":
            return {"player_red": 1.0, "player_yellow": 0.0}
        if winner == "player_yellow":
            return {"player_red": 0.0, "player_yellow": 1.0}
        return {"player_red": 0.5, "player_yellow": 0.5}
