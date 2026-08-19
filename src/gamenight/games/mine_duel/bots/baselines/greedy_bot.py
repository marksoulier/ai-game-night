from __future__ import annotations

from gamenight.core.types import Action, MatchContext, Observation

NEIGHBOR_OFFSETS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1), (0, 1),
    (1, -1), (1, 0), (1, 1),
]


class GreedyBot:
    """Single-constraint Minesweeper deduction, falling back to a local risk estimate.

    Full Minesweeper "given this board, is cell X a mine" is NP-complete in general
    (Kaye, 2000 -- see ../../README.md's "Is Mine Duel Solved?" section), so an
    optimal bot isn't a realistic 30-minute target. This bot uses the same two-tier
    approach as a competent human player, layered exactly like the other games'
    GreedyBots (a "clearly better than random" heuristic, not a solver):

    1. **Certain-safe deduction**: for every revealed numbered cell, if its own number
       already equals the mines already confirmed among its hidden neighbors (revealed
       `"M"` cells count as confirmed -- see below), every OTHER hidden neighbor must be
       safe. This is a single-constraint check (no multi-clue combination), but it's
       100% correct whenever it fires, and it's often enough to clear large chunks of
       board for free.
    2. **Risk estimate**: if no cell is provably safe, score every hidden cell by the
       worst (highest) local mine probability implied by its revealed numbered
       neighbors, and reveal the lowest-risk cell. Cells with no revealed neighbor at
       all (nothing constrains them yet) fall back to the board's overall remaining
       mine density.

    One quirk specific to this game: because the board is fully shared and public,
    revealing a mine doesn't hide it -- it flips to `"M"` for both players. That means
    a numbered clue's "confirmed mine neighbors" isn't just this bot's own guesswork,
    it includes every mine either player has ever triggered nearby.
    """

    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        legal_actions = observation["legal_actions"]
        legal_cells = {(action["row"], action["col"]): action for action in legal_actions}
        board = observation["public_state"]["board"]
        rows = observation["context"]["rows"]
        cols = observation["context"]["cols"]
        mine_count = observation["context"]["mine_count"]

        safe_cells, risk = self._analyze(board, rows, cols, legal_cells)

        if safe_cells:
            best = min(safe_cells)
            return legal_cells[best]

        hidden_count = len(legal_cells)
        mines_revealed = sum(1 for r in range(rows) for c in range(cols) if board[r][c] == "M")
        base_rate = (mine_count - mines_revealed) / hidden_count if hidden_count else 0.0

        def risk_of(cell: tuple[int, int]) -> tuple[float, tuple[int, int]]:
            return (risk.get(cell, base_rate), cell)

        best_cell = min(legal_cells.keys(), key=risk_of)
        return legal_cells[best_cell]

    def _analyze(
        self,
        board: list[list[str]],
        rows: int,
        cols: int,
        legal_cells: dict[tuple[int, int], Action],
    ) -> tuple[set[tuple[int, int]], dict[tuple[int, int], float]]:
        safe_cells: set[tuple[int, int]] = set()
        risk: dict[tuple[int, int], float] = {}

        for row in range(rows):
            for col in range(cols):
                value = board[row][col]
                if value in ("?", "M"):
                    continue
                clue = int(value)

                hidden_neighbors = []
                confirmed_mines = 0
                for d_row, d_col in NEIGHBOR_OFFSETS:
                    nr, nc = row + d_row, col + d_col
                    if not (0 <= nr < rows and 0 <= nc < cols):
                        continue
                    neighbor_value = board[nr][nc]
                    if neighbor_value == "M":
                        confirmed_mines += 1
                    elif neighbor_value == "?":
                        hidden_neighbors.append((nr, nc))

                if not hidden_neighbors:
                    continue

                remaining = clue - confirmed_mines
                if remaining <= 0:
                    safe_cells.update(hidden_neighbors)
                    continue

                cell_risk = min(1.0, remaining / len(hidden_neighbors))
                for cell in hidden_neighbors:
                    if cell in safe_cells:
                        continue
                    risk[cell] = max(risk.get(cell, 0.0), cell_risk)

        safe_cells &= set(legal_cells.keys())
        return safe_cells, risk
