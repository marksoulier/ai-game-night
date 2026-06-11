from __future__ import annotations

from gamenight.core.types import Action, MatchContext, Observation

ORTHOGONAL_NEIGHBORS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


class PlayerBot:
    """Minimal strategy: spread placement + checkerboard hunt / line-following target."""

    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id
        self._pending_hits: list[tuple[int, int]] = []

    def reset(self, context: MatchContext) -> None:
        self._pending_hits = []

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        if observation["public_state"]["phase"] == "placement":
            return self._choose_placement(observation)
        return self._choose_target(observation)

    # -- placement: avoid clustering ships next to each other -----------------------

    def _choose_placement(self, observation: Observation) -> Action:
        legal_actions = observation["legal_actions"]
        ship_lengths = {ship["name"]: ship["length"] for ship in observation["context"]["ships"]}
        occupied = {
            tuple(cell) for ship in observation["private_state"]["your_fleet"] for cell in ship["cells"]
        }

        def adjacency_score(action: Action) -> int:
            length = ship_lengths[action["ship"]]
            if action["orientation"] == "horizontal":
                cells = [(action["row"], action["col"] + i) for i in range(length)]
            else:
                cells = [(action["row"] + i, action["col"]) for i in range(length)]
            return sum(
                1
                for row, col in cells
                for d_row, d_col in ORTHOGONAL_NEIGHBORS + [(-1, -1), (-1, 1), (1, -1), (1, 1)]
                if (row + d_row, col + d_col) in occupied
            )

        return min(legal_actions, key=adjacency_score)

    # -- battle: hunt on a checkerboard pattern, then home in on hits ----------------

    def _choose_target(self, observation: Observation) -> Action:
        legal_actions = observation["legal_actions"]
        legal_cells = {(action["row"], action["col"]): action for action in legal_actions}
        tracking = observation["private_state"]["tracking_grid"]

        self._refresh_pending_hits(tracking)

        for row, col in reversed(self._pending_hits):
            for d_row, d_col in ORTHOGONAL_NEIGHBORS:
                candidate = (row + d_row, col + d_col)
                if candidate in legal_cells:
                    return legal_cells[candidate]

        for (row, col), action in legal_cells.items():
            if (row + col) % 2 == 0:
                return action

        return next(iter(legal_cells.values()))

    def _refresh_pending_hits(self, tracking: list[list[str]]) -> None:
        self._pending_hits = [(row, col) for row, col in self._pending_hits if tracking[row][col] == "H"]
        for row, line in enumerate(tracking):
            for col, cell in enumerate(line):
                if cell == "H" and (row, col) not in self._pending_hits:
                    self._pending_hits.append((row, col))
