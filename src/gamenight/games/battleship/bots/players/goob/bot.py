from __future__ import annotations

from collections import deque
import random

from gamenight.core.types import Action, MatchContext, Observation


BOARD_SIZE = 10
SHIP_LENGTHS = {"carrier": 5, "battleship": 4, "cruiser": 3, "submarine": 3, "destroyer": 2}
ORTHOGONAL_NEIGHBORS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _build_placements() -> dict[int, list[tuple[tuple[int, int], ...]]]:
    placements: dict[int, list[tuple[tuple[int, int], ...]]] = {length: [] for length in set(SHIP_LENGTHS.values())}
    for length in placements:
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if col + length <= BOARD_SIZE:
                    placements[length].append(tuple((row, col + offset) for offset in range(length)))
                if row + length <= BOARD_SIZE:
                    placements[length].append(tuple((row + offset, col) for offset in range(length)))
    return placements


PLACEMENTS_BY_LENGTH = _build_placements()


class PlayerBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id
        self._rng = random.Random()

    def reset(self, context: MatchContext) -> None:
        seed = context.seed
        if seed is None:
            self._rng = random.Random()
        else:
            bot_offset = sum(ord(char) for char in self.bot_id)
            self._rng = random.Random((seed << 1) ^ bot_offset)

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        if observation["public_state"]["phase"] == "placement":
            return self._choose_placement(observation)
        return self._choose_battle_action(observation)

    def _choose_placement(self, observation: Observation) -> Action:
        legal_actions = observation["legal_actions"]
        occupied = {
            tuple(cell)
            for ship in observation["private_state"]["your_fleet"]
            for cell in ship["cells"]
        }
        ship_lengths = {ship["name"]: ship["length"] for ship in observation["context"]["ships"]}
        scored_actions = [(self._placement_score(action, occupied, ship_lengths), action) for action in legal_actions]
        scored_actions.sort(key=lambda item: item[0], reverse=True)

        top_count = min(8, len(scored_actions))
        top_actions = scored_actions[:top_count]
        if len(top_actions) == 1:
            return top_actions[0][1]

        lowest_score = top_actions[-1][0]
        weights = [max(0.01, score - lowest_score + 0.05) for score, _ in top_actions]
        total = sum(weights)
        pick = self._rng.random() * total
        running = 0.0
        for weight, (_, action) in zip(weights, top_actions):
            running += weight
            if pick <= running:
                return action
        return top_actions[0][1]

    def _placement_score(
        self,
        action: Action,
        occupied: set[tuple[int, int]],
        ship_lengths: dict[str, int],
    ) -> float:
        cells = self._cells_for(action["row"], action["col"], ship_lengths[action["ship"]], action["orientation"])

        touching = 0
        diagonal_touching = 0
        minimum_distance = BOARD_SIZE * 2
        center_distance = 0.0
        quadrant_rows = 0
        quadrant_cols = 0

        for row, col in cells:
            center_distance += abs(row - 4.5) + abs(col - 4.5)
            quadrant_rows += 1 if row < 5 else -1
            quadrant_cols += 1 if col < 5 else -1
            for d_row, d_col in ORTHOGONAL_NEIGHBORS:
                if (row + d_row, col + d_col) in occupied:
                    touching += 1
            for d_row in (-1, 1):
                for d_col in (-1, 1):
                    if (row + d_row, col + d_col) in occupied:
                        diagonal_touching += 1
            for occupied_row, occupied_col in occupied:
                distance = abs(row - occupied_row) + abs(col - occupied_col)
                if distance < minimum_distance:
                    minimum_distance = distance

        edge_distance = min(
            min(row, BOARD_SIZE - 1 - row, col, BOARD_SIZE - 1 - col)
            for row, col in cells
        )

        separation_score = minimum_distance * 3.0
        spread_score = edge_distance * 2.25
        anti_cluster_penalty = touching * 5.0 + diagonal_touching * 2.0
        center_penalty = center_distance * 0.15
        quadrant_bonus = abs(quadrant_rows) * 0.4 + abs(quadrant_cols) * 0.4
        return separation_score + spread_score + quadrant_bonus - anti_cluster_penalty - center_penalty

    def _choose_battle_action(self, observation: Observation) -> Action:
        legal_actions = observation["legal_actions"]
        tracking = observation["private_state"]["tracking_grid"]
        legal_cells = {(action["row"], action["col"]): action for action in legal_actions}

        blocked = {
            (row, col)
            for row in range(BOARD_SIZE)
            for col in range(BOARD_SIZE)
            if tracking[row][col] in {"M", "X"}
        }
        hits = self._hit_cells(tracking)
        sunk_ship_names = self._sunk_ship_names(observation)
        remaining_lengths = [
            ship["length"]
            for ship in observation["context"]["ships"]
            if ship["name"] not in sunk_ship_names
        ]

        if hits:
            cluster = self._most_promising_cluster(hits, blocked, remaining_lengths)
            if cluster:
                target = self._destroy_from_cluster(cluster, blocked, hits, remaining_lengths, legal_cells)
                if target is not None:
                    return target

        return self._hunt_with_heatmap(legal_cells, blocked, remaining_lengths)

    def _hit_cells(self, tracking: list[list[str]]) -> list[tuple[int, int]]:
        return [(row, col) for row in range(BOARD_SIZE) for col in range(BOARD_SIZE) if tracking[row][col] == "H"]

    def _sunk_ship_names(self, observation: Observation) -> set[str]:
        sunk_names = set()
        for shot in observation["private_state"]["your_shots"]:
            ship_name = shot["ship"]
            if ship_name is not None:
                sunk_names.add(ship_name)
        return sunk_names

    def _clusters(self, hits: list[tuple[int, int]]) -> list[list[tuple[int, int]]]:
        hit_set = set(hits)
        clusters: list[list[tuple[int, int]]] = []
        seen: set[tuple[int, int]] = set()

        for start in hits:
            if start in seen:
                continue
            cluster: list[tuple[int, int]] = []
            queue: deque[tuple[int, int]] = deque([start])
            seen.add(start)
            while queue:
                row, col = queue.popleft()
                cluster.append((row, col))
                for d_row, d_col in ORTHOGONAL_NEIGHBORS:
                    candidate = (row + d_row, col + d_col)
                    if candidate in hit_set and candidate not in seen:
                        seen.add(candidate)
                        queue.append(candidate)
            clusters.append(cluster)
        return clusters

    def _most_promising_cluster(
        self,
        hits: list[tuple[int, int]],
        blocked: set[tuple[int, int]],
        remaining_lengths: list[int],
    ) -> list[tuple[int, int]]:
        clusters = self._clusters(hits)
        best_cluster: list[tuple[int, int]] = []
        best_count: int | None = None
        for cluster in clusters:
            count = self._count_cluster_placements(cluster, blocked, hits, remaining_lengths)
            if count == 0:
                continue
            if best_count is None or count < best_count:
                best_count = count
                best_cluster = cluster
        return best_cluster

    def _count_cluster_placements(
        self,
        cluster: list[tuple[int, int]],
        blocked: set[tuple[int, int]],
        all_hits: list[tuple[int, int]],
        remaining_lengths: list[int],
    ) -> int:
        total = 0
        cluster_set = set(cluster)
        other_hits = set(all_hits) - cluster_set
        for length in remaining_lengths:
            for placement in PLACEMENTS_BY_LENGTH[length]:
                if any(cell in blocked for cell in placement):
                    continue
                placement_set = set(placement)
                if not cluster_set.issubset(placement_set):
                    continue
                if placement_set & other_hits:
                    continue
                total += 1
        return total

    def _destroy_from_cluster(
        self,
        cluster: list[tuple[int, int]],
        blocked: set[tuple[int, int]],
        all_hits: list[tuple[int, int]],
        remaining_lengths: list[int],
        legal_cells: dict[tuple[int, int], Action],
    ) -> Action | None:
        cluster_set = set(cluster)
        other_hits = set(all_hits) - cluster_set
        scores: dict[tuple[int, int], int] = {}

        for length in remaining_lengths:
            for placement in PLACEMENTS_BY_LENGTH[length]:
                if any(cell in blocked for cell in placement):
                    continue
                placement_set = set(placement)
                if not cluster_set.issubset(placement_set):
                    continue
                if placement_set & other_hits:
                    continue

                weight = 10 + len(cluster) * 10
                for row, col in placement:
                    if (row, col) not in legal_cells:
                        continue
                    scores[(row, col)] = scores.get((row, col), 0) + weight

        if scores:
            row, col = max(
                scores.items(),
                key=lambda item: (
                    item[1],
                    -abs(item[0][0] - 4.5) - abs(item[0][1] - 4.5),
                    -item[0][0],
                    -item[0][1],
                ),
            )[0]
            return legal_cells[(row, col)]

        for row, col in cluster:
            for d_row, d_col in ORTHOGONAL_NEIGHBORS:
                candidate = (row + d_row, col + d_col)
                if candidate in legal_cells:
                    return legal_cells[candidate]
        return None

    def _hunt_with_heatmap(
        self,
        legal_cells: dict[tuple[int, int], Action],
        blocked: set[tuple[int, int]],
        remaining_lengths: list[int],
    ) -> Action:
        scores: dict[tuple[int, int], int] = {}
        parity_scores = {0: 0, 1: 0}
        for length in remaining_lengths:
            for placement in PLACEMENTS_BY_LENGTH[length]:
                if any(cell in blocked for cell in placement):
                    continue
                for cell in placement:
                    if cell in legal_cells:
                        scores[cell] = scores.get(cell, 0) + 1
                        parity_scores[(cell[0] + cell[1]) % 2] += 1

        if scores:
            preferred_parity = 0 if parity_scores[0] >= parity_scores[1] else 1
            row, col = max(
                scores.items(),
                key=lambda item: (
                    item[1],
                    (item[0][0] + item[0][1]) % 2 == preferred_parity,
                    -abs(item[0][0] - 4.5) - abs(item[0][1] - 4.5),
                    -item[0][0],
                    -item[0][1],
                ),
            )[0]
            return legal_cells[(row, col)]

        return min(
            legal_cells.values(),
            key=lambda action: (
                abs(action["row"] - 4.5) + abs(action["col"] - 4.5),
                action["row"],
                action["col"],
            ),
        )

    @staticmethod
    def _cells_for(row: int, col: int, length: int, orientation: str) -> list[tuple[int, int]]:
        if orientation == "horizontal":
            return [(row, col + offset) for offset in range(length)]
        return [(row + offset, col) for offset in range(length)]