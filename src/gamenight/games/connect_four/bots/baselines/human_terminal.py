from __future__ import annotations

from gamenight.core.types import Action, MatchContext, Observation

COLUMNS = 7
ROWS = 6


class HumanTerminalBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        """Show the human everything the AI sees, then return their chosen column.

        `observation` is typed as a plain dict — every game has its own shape, so an
        editor can only ever tell you "dict". Here is *exactly* what Connect Four puts
        inside it, field by field, with the type and valid range/values of each one.
        (The authoritative version of this lives in games/connect_four/BOT_SPEC.md, with
        a full worked example in EXAMPLES.md — this is the same shape, annotated inline.)

            observation = {
                "public_state": {
                    "board": [...],          # list[str], length 42 — each cell "R" / "Y" / " "
                                             #   flat grid, index = row * 7 + col
                                             #   row 0 = TOP of board, row 5 = BOTTOM
                    "current_player": "...", # "player_red" | "player_yellow" — whose turn
                    "turn_index": 0,         # int >= 0, +1 every move
                    "done": False,           # bool — True once the match has ended
                    "winner": None,          # "player_red" | "player_yellow" | None
                                             #   (None means "still going" OR "drawn" —
                                             #   check "done" to tell those apart)
                },
                "private_state": {
                    "marker": "R",           # "R" | "Y" — YOUR disc color (matches your player id)
                },
                "context": {
                    "opponent_id": "...",    # the other player's id, e.g. "player_yellow"
                    "columns": 7,            # board width  (constant for this game)
                    "rows": 6,               # board height (constant for this game)
                    "win_length": 4,         # discs in a row needed to win (constant)
                },
                "legal_actions": [           # list[dict] — only columns that AREN'T full appear
                    {"type": "drop", "column": 0},  # "column" is an int, 0 <= column <= 6
                    ...
                ],
            }

        What this bot must return: exactly one of the dicts already sitting in
        `observation["legal_actions"]` (that's why we print them with an index below and
        let the human pick by number — it guarantees a legal reply every time). The
        engine decides which row a disc lands in for you (gravity); you only ever choose
        a column.
        """
        board = observation["public_state"]["board"]
        print("Board (the exact flat list the AI receives, index = row * 7 + col, row 0 = top):")
        print(f"  {board}")
        print("Game State:")
        for row in range(ROWS):
            start = row * COLUMNS
            end = start + COLUMNS
            print(f"  row {row} (indexes {start:2d}-{end - 1:2d}): {board[start:end]}")
        legal_actions = observation["legal_actions"]
        print("Legal actions:")
        for idx, action in enumerate(legal_actions):
            print(f"  {idx}: {action}")
        selected = int(input("Select action index: ").strip())
        return legal_actions[selected]
