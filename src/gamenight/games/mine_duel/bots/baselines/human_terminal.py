from __future__ import annotations

from gamenight.core.types import Action, MatchContext, Observation


def _print_board(board: list[list[str]]) -> None:
    # Column/row counts come from the board itself (not a hardcoded constant) so this
    # stays correct regardless of which difficulty size `game.py` is configured for.
    cols = len(board[0]) if board else 0
    header = "    " + " ".join(str(col) for col in range(cols))
    print(f"  {header}")
    for row_index, row in enumerate(board):
        print(f"  {row_index:2d}  " + " ".join(row))


class HumanTerminalBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        """Show the human everything the AI sees, then return their chosen move.

        `observation` is typed as a plain dict -- every game has its own shape, so an
        editor can only tell you "dict". Here is exactly what Mine Duel puts inside it.
        (The authoritative version lives in BOT_SPEC.md, with a full worked example in
        EXAMPLES.md.)

        Mine Duel has NO hidden information -- both players see the exact same shared
        board, since neither of you knows where the mines are any better than the
        other. There's no `private_state` to speak of (it's always `{}`).

            observation = {
                "public_state": {
                    "current_player": "...",       # whose turn it is right now
                    "turn_index": 0,                # int >= 0, +1 every reveal
                    "done": False,                  # bool -- True once the match has ended
                    "winner": "..." | None,         # winner id, or None (ongoing, or a tied final score)
                    "scores": {"player_ember": 3, "player_frost": 1},
                    "safe_cells_remaining": 205,     # safe cells nobody has found yet
                    # rows x cols grid (see context.rows/cols), row 0 = top. "?" hidden,
                    # "0"-"8" a revealed safe cell's adjacent-mine count, "M" a mine.
                    "board": [["?", "?", ...], ...],
                    # Same shape -- which player revealed each cell (None if still hidden).
                    # Cosmetic/spectator info only -- it never tells you where a HIDDEN
                    # mine is, so using it is not an information leak.
                    "owner_grid": [[None, "player_ember", ...], ...],
                },
                "private_state": {},   # always empty -- see the note above
                "context": {
                    "opponent_id": "...",
                    "rows": 14,               # Google Minesweeper's "Medium" board -- see game.py
                    "cols": 18,
                    "mine_count": 40,
                    "total_safe_cells": 212,
                    "mine_penalty": 1,   # points you lose for revealing a mine
                },
                "legal_actions": [...],   # every still-hidden cell
            }

        Actions look like: {"type": "reveal", "row": 3, "col": 7}
        """
        public_state = observation["public_state"]
        legal_actions = observation["legal_actions"]
        context = observation["context"]

        print("Board (? hidden, 0-8 = adjacent mine count, M = revealed mine):")
        _print_board(public_state["board"])
        print()
        print("Scores: " + "  ".join(f"{pid}={score}" for pid, score in public_state["scores"].items()))
        print(f"Safe cells remaining: {public_state['safe_cells_remaining']}")
        print()

        prompt = (
            f"Reveal — enter 'row col' (row 0-{context['rows'] - 1}, col 0-{context['cols'] - 1}), "
            "e.g. '3 7': "
        )
        while True:
            raw = input(prompt).strip().split()
            try:
                row, col = int(raw[0]), int(raw[1])
            except (IndexError, ValueError):
                print("Couldn't parse that as two numbers — try again.")
                continue
            candidate = {"type": "reveal", "row": row, "col": col}
            if candidate in legal_actions:
                return candidate
            print("That cell isn't legal (out of range, or already revealed) — try again.")
