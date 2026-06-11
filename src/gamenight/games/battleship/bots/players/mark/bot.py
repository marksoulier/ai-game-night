from __future__ import annotations

import random

from gamenight.core.types import Action, MatchContext, Observation

BOARD_SIZE = 10
ALL_NEIGHBORS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
ORTHOGONAL_NEIGHBORS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


class PlayerBot:
    """Randomized spread placement + probability-density hunt / line-following target.

    - Placement: among the placements that minimize fleet clustering, pick randomly so
      our layout isn't deterministic/guessable across games.
    - Battle: when we have unresolved hits, follow them (line-narrowing once two hits
      reveal orientation). Otherwise, compute a probability-density map over every
      possible placement of each remaining (not-yet-sunk) ship and fire at the
      highest-density cell, restricted to one checkerboard parity (every ship length
      >= 2 guarantees a placement touches both parities, so this is safe and halves
      the search).
    """

    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id
        self._pending_hits: list[tuple[int, int]] = []

    def reset(self, context: MatchContext) -> None:
        self._pending_hits = []

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        if observation["public_state"]["phase"] == "placement":
            return self._choose_placement(observation)
        return self._choose_target(observation)

    # -- placement: randomize among the least-clustered options ---------------------

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
                for d_row, d_col in ALL_NEIGHBORS
                if (row + d_row, col + d_col) in occupied
            )

        best_score = min(adjacency_score(action) for action in legal_actions)
        best_actions = [action for action in legal_actions if adjacency_score(action) == best_score]
        return random.choice(best_actions)

    # -- battle: target pending hits, otherwise hunt by probability density ----------

    def _choose_target(self, observation: Observation) -> Action:
        legal_actions = observation["legal_actions"]
        legal_cells = {(action["row"], action["col"]): action for action in legal_actions}
        tracking = observation["private_state"]["tracking_grid"]

        self._refresh_pending_hits(tracking)

        if self._pending_hits:
            target = self._target_adjacent_to_hit(legal_cells)
            if target is not None:
                return target

        return self._hunt_by_density(observation, legal_cells)

    def _refresh_pending_hits(self, tracking: list[list[str]]) -> None:
        self._pending_hits = [(row, col) for row, col in self._pending_hits if tracking[row][col] == "H"]
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if tracking[row][col] == "H" and (row, col) not in self._pending_hits:
                    self._pending_hits.append((row, col))

    # -- targeting: follow up a hit, narrowing to a line once orientation is known ---

    def _target_adjacent_to_hit(self, legal_cells: dict[tuple[int, int], Action]) -> Action | None:
        line = self._infer_line(self._pending_hits)
        if line is not None:
            extension = self._extend_line(line, legal_cells)
            if extension is not None:
                return extension

        for row, col in reversed(self._pending_hits):
            for d_row, d_col in ORTHOGONAL_NEIGHBORS:
                candidate = (row + d_row, col + d_col)
                if candidate in legal_cells:
                    return legal_cells[candidate]
        return None

    @staticmethod
    def _infer_line(hits: list[tuple[int, int]]):
        if len(hits) < 2:
            return None
        rows = {row for row, _ in hits}
        cols = {col for _, col in hits}
        if len(rows) == 1:
            ordered = sorted(col for _, col in hits)
            if ordered[-1] - ordered[0] == len(ordered) - 1:
                return ("horizontal", next(iter(rows)), ordered)
        elif len(cols) == 1:
            ordered = sorted(row for row, _ in hits)
            if ordered[-1] - ordered[0] == len(ordered) - 1:
                return ("vertical", next(iter(cols)), ordered)
        return None

    @staticmethod
    def _extend_line(line, legal_cells: dict[tuple[int, int], Action]) -> Action | None:
        orientation, fixed, ordered = line
        low, high = ordered[0], ordered[-1]
        if orientation == "horizontal":
            ends = [(fixed, low - 1), (fixed, high + 1)]
        else:
            ends = [(low - 1, fixed), (high + 1, fixed)]
        for candidate in ends:
            if candidate in legal_cells:
                return legal_cells[candidate]
        return None

    # -- hunting: probability-density map over remaining ships' possible placements --

    def _hunt_by_density(
        self, observation: Observation, legal_cells: dict[tuple[int, int], Action]
    ) -> Action:
        tracking = observation["private_state"]["tracking_grid"]
        sunk_names = {
            shot["ship"]
            for shot in observation["private_state"]["your_shots"]
            if shot["result"] == "sunk" and shot["ship"]
        }
        remaining_lengths = [
            ship["length"] for ship in observation["context"]["ships"] if ship["name"] not in sunk_names
        ]

        density: dict[tuple[int, int], int] = {}
        for length in remaining_lengths:
            # horizontal placements
            for row in range(BOARD_SIZE):
                for col in range(BOARD_SIZE - length + 1):
                    cells = [(row, col + offset) for offset in range(length)]
                    if all(tracking[r][c] not in ("M", "X") for r, c in cells):
                        for cell in cells:
                            density[cell] = density.get(cell, 0) + 1
            # vertical placements
            for row in range(BOARD_SIZE - length + 1):
                for col in range(BOARD_SIZE):
                    cells = [(row + offset, col) for offset in range(length)]
                    if all(tracking[r][c] not in ("M", "X") for r, c in cells):
                        for cell in cells:
                            density[cell] = density.get(cell, 0) + 1

        # Restrict to one checkerboard parity: every ship (length >= 2) placed in a
        # straight line covers cells of both parities, so this halves the candidates
        # without missing any possible placement.
        parity_cells = {cell: action for cell, action in legal_cells.items() if (cell[0] + cell[1]) % 2 == 0}
        candidates = parity_cells if parity_cells else legal_cells

        best_cell = max(candidates, key=lambda cell: density.get(cell, 0))
        return candidates[best_cell]
