from __future__ import annotations

from gamenight.core.types import Action, MatchContext, Observation


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


class GreedyBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        board = observation["public_state"]["board"]
        legal_actions = observation["legal_actions"]
        my_marker = observation["private_state"]["marker"]
        opp_marker = "O" if my_marker == "X" else "X"

        winning_action = self._find_line_completion(board, legal_actions, my_marker)
        if winning_action is not None:
            return winning_action

        blocking_action = self._find_line_completion(board, legal_actions, opp_marker)
        if blocking_action is not None:
            return blocking_action

        for preferred_index in [4, 0, 2, 6, 8, 1, 3, 5, 7]:
            for action in legal_actions:
                if action["index"] == preferred_index:
                    return action

        return legal_actions[0]

    def _find_line_completion(self, board: list[str], legal_actions: list[Action], marker: str) -> Action | None:
        legal_indices = {action["index"]: action for action in legal_actions}
        for a, b, c in WIN_LINES:
            line = [board[a], board[b], board[c]]
            if line.count(marker) == 2 and line.count(" ") == 1:
                open_index = [a, b, c][line.index(" ")]
                if open_index in legal_indices:
                    return legal_indices[open_index]
        return None
