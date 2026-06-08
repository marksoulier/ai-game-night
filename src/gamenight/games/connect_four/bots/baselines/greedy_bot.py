from __future__ import annotations

from gamenight.core.types import Action, MatchContext, Observation


COLUMNS = 7
ROWS = 6
CONNECT_LENGTH = 4
DIRECTIONS = [(0, 1), (1, 0), (1, 1), (1, -1)]
PREFERRED_COLUMNS = [3, 2, 4, 1, 5, 0, 6]


class GreedyBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        board = observation["public_state"]["board"]
        legal_actions = observation["legal_actions"]
        my_marker = observation["private_state"]["marker"]
        opp_marker = "Y" if my_marker == "R" else "R"

        winning_action = self._find_winning_drop(board, legal_actions, my_marker)
        if winning_action is not None:
            return winning_action

        blocking_action = self._find_winning_drop(board, legal_actions, opp_marker)
        if blocking_action is not None:
            return blocking_action

        for preferred_column in PREFERRED_COLUMNS:
            for action in legal_actions:
                if action["column"] == preferred_column:
                    return action

        return legal_actions[0]

    def _find_winning_drop(self, board: list[str], legal_actions: list[Action], marker: str) -> Action | None:
        for action in legal_actions:
            column = action["column"]
            row = self._landing_row(board, column)
            if row is not None and self._creates_connect_four(board, row, column, marker):
                return action
        return None

    def _landing_row(self, board: list[str], column: int) -> int | None:
        for row in range(ROWS - 1, -1, -1):
            if board[row * COLUMNS + column] == " ":
                return row
        return None

    def _creates_connect_four(self, board: list[str], row: int, col: int, marker: str) -> bool:
        for d_row, d_col in DIRECTIONS:
            total = (
                1
                + self._count_direction(board, row, col, d_row, d_col, marker)
                + self._count_direction(board, row, col, -d_row, -d_col, marker)
            )
            if total >= CONNECT_LENGTH:
                return True
        return False

    def _count_direction(self, board: list[str], row: int, col: int, d_row: int, d_col: int, marker: str) -> int:
        count = 0
        r, c = row + d_row, col + d_col
        while 0 <= r < ROWS and 0 <= c < COLUMNS and board[r * COLUMNS + c] == marker:
            count += 1
            r += d_row
            c += d_col
        return count
