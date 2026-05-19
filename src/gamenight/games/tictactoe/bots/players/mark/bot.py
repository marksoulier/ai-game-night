class PlayerBot:
    def __init__(self, bot_id: str):
        self.bot_id = bot_id

    def reset(self, context):
        pass

    def choose_action(self, observation, context):
        board = observation["public_state"]["board"]
        legal_actions = observation["legal_actions"]
        my_marker = observation["private_state"]["marker"]
        opp_marker = "O" if my_marker == "X" else "X"

        # 1. If a move wins this turn, play it.
        for action in legal_actions:
            idx = action["index"]
            if self._is_winning_move(board, idx, my_marker):
                return action

        # 2. Else if opponent can win next turn, block it.
        for action in legal_actions:
            idx = action["index"]
            if self._is_winning_move(board, idx, opp_marker):
                return action

        # 3. Else prefer center, then corners, then edges.
        preferred = [4, 0, 2, 6, 8, 1, 3, 5, 7]
        for idx in preferred:
            for action in legal_actions:
                if action["index"] == idx:
                    return action

        # Fallback: return first legal action
        return legal_actions[0]

    def _is_winning_move(self, board, idx, marker):
        test_board = board[:]
        test_board[idx] = marker
        win_lines = [
            (0, 1, 2), (3, 4, 5), (6, 7, 8),
            (0, 3, 6), (1, 4, 7), (2, 5, 8),
            (0, 4, 8), (2, 4, 6),
        ]
        for a, b, c in win_lines:
            if test_board[a] == test_board[b] == test_board[c] == marker:
                return True
        return False
