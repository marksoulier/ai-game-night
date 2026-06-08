from __future__ import annotations

from gamenight.core.types import Action, MatchContext, Observation

BOARD_SIZE = 10
ALL_NEIGHBORS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
ORTHOGONAL_NEIGHBORS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


class GreedyBot:
    """A two-heuristic Battleship bot: spread placement + classic "hunt-and-target".

    Neither heuristic is optimal play (no such thing is known to exist for Battleship —
    see ../../README.md's "Is Battleship Solved?" section) — they're the same kind of
    well-studied, "clearly better than random" layered heuristics the other games'
    GreedyBots use, scaled to fit Battleship's actual structure:

    - **Placement**: prefer wherever keeps your fleet least clustered (fewest cells
      touching an already-placed ship), so a string of hits on one ship doesn't hand
      the opponent a map to your whole fleet.
    - **Targeting**: "hunt" on a checkerboard parity pattern when nothing's been hit
      yet (every ship is >= 2 cells long, so parity is guaranteed to eventually touch
      every possible placement while halving the cells you need to try), then switch
      to "target" mode — radiating out from a hit, and narrowing to a line once two
      hits in a row reveal the ship's orientation — until that ship is sunk.
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

    # -- placement: spread the fleet out rather than clustering it -------------------

    def _choose_placement(self, observation: Observation) -> Action:
        legal_actions = observation["legal_actions"]
        ship_lengths = {ship["name"]: ship["length"] for ship in observation["context"]["ships"]}
        occupied = {
            tuple(cell) for ship in observation["private_state"]["your_fleet"] for cell in ship["cells"]
        }

        def adjacency_score(action: Action) -> int:
            cells = self._cells_for(action["row"], action["col"], ship_lengths[action["ship"]], action["orientation"])
            return sum(
                1
                for row, col in cells
                for d_row, d_col in ALL_NEIGHBORS
                if (row + d_row, col + d_col) in occupied
            )

        return min(legal_actions, key=adjacency_score)

    @staticmethod
    def _cells_for(row: int, col: int, length: int, orientation: str) -> list[tuple[int, int]]:
        if orientation == "horizontal":
            return [(row, col + offset) for offset in range(length)]
        return [(row + offset, col) for offset in range(length)]

    # -- targeting: hunt (parity) then target (follow up a hit, narrowing to a line) -

    def _choose_target(self, observation: Observation) -> Action:
        legal_actions = observation["legal_actions"]
        legal_cells = {(action["row"], action["col"]): action for action in legal_actions}
        tracking = observation["private_state"]["tracking_grid"]

        self._refresh_pending_hits(tracking)

        if self._pending_hits:
            target = self._target_adjacent_to_hit(legal_cells)
            if target is not None:
                return target

        return self._hunt_on_parity(legal_cells)

    def _refresh_pending_hits(self, tracking: list[list[str]]) -> None:
        # "H" = hit, ship not yet sunk. Once a ship sinks, its cells flip to "X" in the
        # tracking grid (see BOT_SPEC.md) -- drop those, they're fully resolved.
        self._pending_hits = [(row, col) for row, col in self._pending_hits if tracking[row][col] == "H"]
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if tracking[row][col] == "H" and (row, col) not in self._pending_hits:
                    self._pending_hits.append((row, col))

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
        """Two-or-more hits forming a contiguous run reveal a ship's orientation."""
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

    def _hunt_on_parity(self, legal_cells: dict[tuple[int, int], Action]) -> Action:
        parity_targets = [action for (row, col), action in legal_cells.items() if (row + col) % 2 == 0]
        if parity_targets:
            return parity_targets[0]
        return next(iter(legal_cells.values()))
