from __future__ import annotations

from functools import lru_cache

from gamenight.core.types import Action, MatchContext, Observation


BOARD_SIZE = 10
CENTER = (BOARD_SIZE - 1) / 2
ALL_NEIGHBORS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
ORTHOGONAL_NEIGHBORS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


class PlayerBot:
    def __init__(self, bot_id: str = "josh") -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        legal_actions = observation["legal_actions"]
        if not legal_actions:
            raise ValueError("No legal actions available")

        if observation["public_state"]["phase"] == "placement":
            return self._choose_placement(observation)
        return self._choose_battle(observation)

    def _choose_placement(self, observation: Observation) -> Action:
        legal_actions = observation["legal_actions"]
        ship_lengths = {ship["name"]: ship["length"] for ship in observation["context"]["ships"]}
        occupied = {
            tuple(cell)
            for ship in observation["private_state"]["your_fleet"]
            for cell in ship["cells"]
        }

        if not occupied:
            return max(legal_actions, key=lambda action: self._placement_spread_score(action, ship_lengths))

        return min(legal_actions, key=lambda action: self._placement_score(action, occupied, ship_lengths))

    def _choose_battle(self, observation: Observation) -> Action:
        legal_actions = observation["legal_actions"]
        tracking = observation["private_state"]["tracking_grid"]
        remaining_lengths = self._remaining_ship_lengths(observation)
        blocked_cells = self._blocked_cells(tracking)
        hit_cells = self._hit_cells(tracking)

        if hit_cells:
            heatmap = self._build_heatmap(remaining_lengths, blocked_cells, hit_cells)
            if heatmap:
                return self._choose_from_heatmap(legal_actions, heatmap, tracking)
            return self._fallback_near_hits(legal_actions, hit_cells)

        heatmap = self._build_heatmap(remaining_lengths, blocked_cells, None)
        if heatmap:
            return self._choose_from_heatmap(legal_actions, heatmap, tracking)

        return self._choose_parity_fallback(legal_actions)

    def _placement_score(
        self,
        action: Action,
        occupied: set[tuple[int, int]],
        ship_lengths: dict[str, int],
    ) -> tuple[int, int, float, int, int, int]:
        cells = self._cells_for(action["row"], action["col"], ship_lengths[action["ship"]], action["orientation"])
        adjacency = sum(
            1
            for row, col in cells
            for delta_row, delta_col in ALL_NEIGHBORS
            if (row + delta_row, col + delta_col) in occupied
        )
        min_distance = self._minimum_distance_to_fleet(cells, occupied)
        edge_bias = sum(abs(row - CENTER) + abs(col - CENTER) for row, col in cells)
        orientation_bias = 0 if action["orientation"] == "horizontal" else 1
        return (adjacency, -min_distance, -edge_bias, action["row"], action["col"], orientation_bias)

    def _placement_spread_score(self, action: Action, ship_lengths: dict[str, int]) -> tuple[float, float, int, int, int]:
        cells = self._cells_for(action["row"], action["col"], ship_lengths[action["ship"]], action["orientation"])
        edge_bias = sum(abs(row - CENTER) + abs(col - CENTER) for row, col in cells)
        orientation_bias = 0 if action["orientation"] == "horizontal" else 1
        return (edge_bias, -abs(action["row"] - CENTER), action["row"], action["col"], orientation_bias)

    def _choose_from_heatmap(
        self,
        legal_actions: list[Action],
        heatmap: dict[tuple[int, int], int],
        tracking: list[list[str]],
    ) -> Action:
        best_action = legal_actions[0]
        best_score: tuple[int, int, int, int, int, int] | None = None
        for action in legal_actions:
            cell = (action["row"], action["col"])
            score = (
                heatmap.get(cell, 0),
                self._adjacent_hit_count(cell, tracking),
                1 if (cell[0] + cell[1]) % 2 == 0 else 0,
                -self._distance_to_center(cell),
                -cell[0],
                -cell[1],
            )
            if best_score is None or score > best_score:
                best_score = score
                best_action = action
        return best_action

    def _fallback_near_hits(self, legal_actions: list[Action], hit_cells: set[tuple[int, int]]) -> Action:
        legal_by_cell = {(action["row"], action["col"]): action for action in legal_actions}
        line = self._infer_line(sorted(hit_cells))
        if line is not None:
            extension = self._extend_line(line, legal_by_cell)
            if extension is not None:
                return extension

        for row, col in sorted(hit_cells, key=lambda cell: (-cell[0], -cell[1])):
            for delta_row, delta_col in ORTHOGONAL_NEIGHBORS:
                candidate = (row + delta_row, col + delta_col)
                if candidate in legal_by_cell:
                    return legal_by_cell[candidate]

        return self._choose_parity_fallback(legal_actions)

    def _choose_parity_fallback(self, legal_actions: list[Action]) -> Action:
        parity_targets = [action for action in legal_actions if (action["row"] + action["col"]) % 2 == 0]
        if parity_targets:
            return min(parity_targets, key=lambda action: (action["row"], action["col"]))
        return min(legal_actions, key=lambda action: (action["row"], action["col"]))

    @staticmethod
    def _infer_line(hits: list[tuple[int, int]]):
        if len(hits) < 2:
            return None

        rows = {row for row, _ in hits}
        cols = {col for _, col in hits}
        if len(rows) == 1:
            ordered_columns = sorted(col for _, col in hits)
            if ordered_columns[-1] - ordered_columns[0] == len(ordered_columns) - 1:
                return ("horizontal", next(iter(rows)), ordered_columns)
        if len(cols) == 1:
            ordered_rows = sorted(row for row, _ in hits)
            if ordered_rows[-1] - ordered_rows[0] == len(ordered_rows) - 1:
                return ("vertical", next(iter(cols)), ordered_rows)
        return None

    @staticmethod
    def _extend_line(line, legal_cells: dict[tuple[int, int], Action]) -> Action | None:
        orientation, fixed, ordered = line
        low, high = ordered[0], ordered[-1]
        candidates = [(fixed, low - 1), (fixed, high + 1)] if orientation == "horizontal" else [(low - 1, fixed), (high + 1, fixed)]
        for candidate in candidates:
            if candidate in legal_cells:
                return legal_cells[candidate]
        return None

    def _build_heatmap(
        self,
        remaining_lengths: tuple[int, ...],
        blocked_cells: set[tuple[int, int]],
        hit_cells: set[tuple[int, int]] | None,
    ) -> dict[tuple[int, int], int]:
        heatmap: dict[tuple[int, int], int] = {}
        for length in remaining_lengths:
            for placement in self._placements_for_length(length):
                if any(cell in blocked_cells for cell in placement):
                    continue

                if hit_cells is not None:
                    covered_hits = sum(1 for cell in placement if cell in hit_cells)
                    if covered_hits == 0:
                        continue
                    weight = covered_hits
                else:
                    weight = 1

                for cell in placement:
                    heatmap[cell] = heatmap.get(cell, 0) + weight

        return heatmap

    def _remaining_ship_lengths(self, observation: Observation) -> tuple[int, ...]:
        your_shots = observation["private_state"].get("your_shots", [])
        sunk_ship_names = {
            shot["ship"]
            for shot in your_shots
            if shot.get("result") == "sunk" and shot.get("ship") is not None
        }
        remaining = [ship["length"] for ship in observation["context"]["ships"] if ship["name"] not in sunk_ship_names]
        return tuple(sorted(remaining, reverse=True))

    @staticmethod
    def _blocked_cells(tracking: list[list[str]]) -> set[tuple[int, int]]:
        blocked = set()
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if tracking[row][col] in {"M", "X"}:
                    blocked.add((row, col))
        return blocked

    @staticmethod
    def _hit_cells(tracking: list[list[str]]) -> set[tuple[int, int]]:
        hits = set()
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if tracking[row][col] == "H":
                    hits.add((row, col))
        return hits

    @staticmethod
    def _adjacent_hit_count(cell: tuple[int, int], tracking: list[list[str]]) -> int:
        row, col = cell
        return sum(
            1
            for delta_row, delta_col in ORTHOGONAL_NEIGHBORS
            if 0 <= row + delta_row < BOARD_SIZE
            and 0 <= col + delta_col < BOARD_SIZE
            and tracking[row + delta_row][col + delta_col] == "H"
        )

    @staticmethod
    def _distance_to_center(cell: tuple[int, int]) -> float:
        row, col = cell
        return abs(row - CENTER) + abs(col - CENTER)

    @staticmethod
    def _minimum_distance_to_fleet(cells: list[tuple[int, int]], occupied: set[tuple[int, int]]) -> int:
        if not occupied:
            return BOARD_SIZE * 2

        return min(
            abs(row - occupied_row) + abs(col - occupied_col)
            for row, col in cells
            for occupied_row, occupied_col in occupied
        )

    @staticmethod
    def _cells_for(row: int, col: int, length: int, orientation: str) -> list[tuple[int, int]]:
        if orientation == "horizontal":
            return [(row, col + offset) for offset in range(length)]
        return [(row + offset, col) for offset in range(length)]

    @staticmethod
    @lru_cache(maxsize=None)
    def _placements_for_length(length: int) -> tuple[tuple[tuple[int, int], ...], ...]:
        placements: list[tuple[tuple[int, int], ...]] = []
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if col + length <= BOARD_SIZE:
                    placements.append(tuple((row, col + offset) for offset in range(length)))
                if row + length <= BOARD_SIZE:
                    placements.append(tuple((row + offset, col) for offset in range(length)))
        return tuple(placements)
