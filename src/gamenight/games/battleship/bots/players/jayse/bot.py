from __future__ import annotations

from dataclasses import dataclass
import math
import random

from gamenight.core.types import Action, MatchContext, Observation

BOARD_SIZE = 10
ORTHOGONAL_NEIGHBORS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


# ---------------------------------------------------------------------------------
# Optional typed view of `observation`
#
# `observation` arrives as a plain dict (every game has a different shape, so the
# engine can't type it for you). If you'd rather have your editor/IDE autocomplete
# fields and catch typos, build one of these from the raw dict:
#
#     obs = BattleshipObservation.from_dict(observation)
#     obs.private_state.tracking_grid[3][7]   # instead of observation["private_state"]["tracking_grid"][3][7]
#
# This is purely a convenience wrapper around the dict described in ../../../BOT_SPEC.md
# (worked example in ../../../EXAMPLES.md) -- using it is entirely optional, and
# `choose_action` below works fine with the raw dict. Delete this block if you don't
# want it.
# ---------------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class ShipView:
    """One of YOUR ships. `cells` and `hits` are [row, col] pairs."""

    name: str  # carrier/battleship/cruiser/submarine/destroyer
    length: int
    cells: list[list[int]]
    hits: list[list[int]]
    sunk: bool


@dataclass(slots=True, frozen=True)
class Shot:
    """One shot YOU fired at the opponent."""

    row: int
    col: int
    result: str  # "miss" | "hit" | "sunk"
    ship: str | None  # opponent ship name, only once you've sunk it


@dataclass(slots=True, frozen=True)
class ShipSpec:
    """A fixed entry in the fleet every player places (carrier first, destroyer last)."""

    name: str
    length: int


@dataclass(slots=True, frozen=True)
class PublicState:
    """What's true for everyone, regardless of who's asking."""

    phase: str  # "placement" | "battle"
    current_player: str
    turn_index: int
    done: bool
    winner: str | None
    points: dict[str, int]  # per-player ship cells not yet hit (17 max each)


@dataclass(slots=True, frozen=True)
class PrivateState:
    """What only YOU would know."""

    your_fleet: list[ShipView]
    # Your own 10x10 waters: "~" empty, "S" your ship, "H" your ship hit,
    # "X" your ship hit & sunk, "M" opponent fired here and missed.
    your_board: list[list[str]]
    your_shots: list[Shot]
    # Your shot history as a 10x10 grid: "?" unknown, "M" miss, "H" hit (ship
    # unknown), "X" hit & sunk.
    tracking_grid: list[list[str]]


@dataclass(slots=True, frozen=True)
class Context:
    """Fixed facts about the match."""

    opponent_id: str
    board_size: int
    ships: list[ShipSpec]
    next_ship_to_place: str | None  # set during YOUR placement turns


@dataclass(slots=True, frozen=True)
class BattleshipObservation:
    public_state: PublicState
    private_state: PrivateState
    context: Context
    legal_actions: list[Action]

    @classmethod
    def from_dict(cls, observation: Observation) -> "BattleshipObservation":
        public = observation["public_state"]
        private = observation["private_state"]
        context = observation["context"]
        return cls(
            public_state=PublicState(
                phase=public["phase"],
                current_player=public["current_player"],
                turn_index=public["turn_index"],
                done=public["done"],
                winner=public["winner"],
                points=dict(public["points"]),
            ),
            private_state=PrivateState(
                your_fleet=[
                    ShipView(
                        name=ship["name"],
                        length=ship["length"],
                        cells=ship["cells"],
                        hits=ship["hits"],
                        sunk=ship["sunk"],
                    )
                    for ship in private["your_fleet"]
                ],
                your_board=private["your_board"],
                your_shots=[
                    Shot(row=shot["row"], col=shot["col"], result=shot["result"], ship=shot["ship"])
                    for shot in private["your_shots"]
                ],
                tracking_grid=private["tracking_grid"],
            ),
            context=Context(
                opponent_id=context["opponent_id"],
                board_size=context["board_size"],
                ships=[ShipSpec(name=ship["name"], length=ship["length"]) for ship in context["ships"]],
                next_ship_to_place=context["next_ship_to_place"],
            ),
            legal_actions=observation["legal_actions"],
        )


class PlayerBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id
        self._pending_hits: list[tuple[int, int]] = []
        self._last_hit_turn: int = 0

    def reset(self, context: MatchContext) -> None:
        self._pending_hits = []
        self._last_hit_turn = 0

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        if observation["public_state"]["phase"] == "placement":
            return self._choose_placement(observation, context)
        return self._choose_target(observation, context)

    def _choose_placement(self, observation: Observation, context: MatchContext) -> Action:
        legal_actions = observation["legal_actions"]
        board_size = observation["context"]["board_size"]
        ship_lengths = {ship["name"]: ship["length"] for ship in observation["context"]["ships"]}
        ship_order = [ship["name"] for ship in observation["context"]["ships"]]
        ship_name = observation["context"]["next_ship_to_place"]
        ship_index = ship_order.index(ship_name) if ship_name in ship_order else 0
        preferred_edge = ship_index % 4
        center = (board_size - 1) / 2

        def score(action: Action) -> tuple[int, int, float, int, int]:
            cells = self._cells_for(
                action["row"],
                action["col"],
                ship_lengths[action["ship"]],
                action["orientation"],
            )
            preferred_edge_cells = sum(
                1
                for row, col in cells
                if (
                    (preferred_edge == 0 and row == 0)
                    or (preferred_edge == 1 and col == board_size - 1)
                    or (preferred_edge == 2 and row == board_size - 1)
                    or (preferred_edge == 3 and col == 0)
                )
            )
            any_edge_cells = sum(
                1
                for row, col in cells
                if row in {0, board_size - 1} or col in {0, board_size - 1}
            )
            distance_from_center = sum(abs(row - center) + abs(col - center) for row, col in cells)
            noise_seed = f"{context.seed}:{self.bot_id}:{ship_name}:{action['row']}:{action['col']}:{action['orientation']}"
            noise = random.Random(noise_seed).random()
            return (preferred_edge_cells, any_edge_cells, distance_from_center, noise, -action["row"], -action["col"])

        return max(legal_actions, key=score)

    @staticmethod
    def _cells_for(row: int, col: int, length: int, orientation: str) -> list[tuple[int, int]]:
        if orientation == "horizontal":
            return [(row, col + offset) for offset in range(length)]
        return [(row + offset, col) for offset in range(length)]

    def _choose_target(self, observation: Observation, context: MatchContext) -> Action:
        legal_actions = observation["legal_actions"]
        legal_cells = {(action["row"], action["col"]): action for action in legal_actions}
        tracking = observation["private_state"]["tracking_grid"]

        self._refresh_pending_hits(tracking)
        self._refresh_last_hit_turn(observation)
        stale_search = self._is_stale_search(observation)

        line_target = self._extend_known_line(legal_cells)
        if line_target is not None:
            return line_target

        adjacent_target = self._target_next_to_hit(legal_cells)
        if adjacent_target is not None:
            return adjacent_target

        if not self._pending_hits:
            if stale_search:
                return self._inverted_heatmap_target(legal_actions, tracking, observation, context)
            return self._annealed_probe_target(legal_actions, tracking, observation, context)

        return self._best_probability_target(legal_actions, tracking, observation)

    def _refresh_last_hit_turn(self, observation: Observation) -> None:
        your_shots = observation["private_state"]["your_shots"]
        if not your_shots:
            return

        last_shot = your_shots[-1]
        if last_shot["result"] in {"hit", "sunk"}:
            self._last_hit_turn = observation["public_state"]["turn_index"]

    def _is_stale_search(self, observation: Observation) -> bool:
        turn_index = observation["public_state"]["turn_index"]
        return (turn_index - self._last_hit_turn) >= 78

    def _inverted_heatmap_target(
        self,
        legal_actions: list[Action],
        tracking: list[list[str]],
        observation: Observation,
        context: MatchContext,
    ) -> Action:
        scores = self._target_scores(legal_actions, tracking, observation)
        inverted_scores = {cell: -score for cell, score in scores.items()}

        board_size = observation["context"]["board_size"]
        for action in legal_actions:
            row = action["row"]
            col = action["col"]
            edge_bonus = 0.0
            corner_bonus = 0.0
            if row in {0, board_size - 1}:
                edge_bonus += 2.0
            if col in {0, board_size - 1}:
                edge_bonus += 2.0
            if row in {0, board_size - 1} and col in {0, board_size - 1}:
                corner_bonus = 1.5
            inverted_scores[(row, col)] += edge_bonus + corner_bonus

        rng = self._match_rng(observation, context)
        ranked_actions = sorted(legal_actions, key=lambda action: inverted_scores[(action["row"], action["col"])], reverse=True)
        temperature = max(0.15, self._target_temperature(observation, tracking) * 0.35)
        cutoff = max(1, len(ranked_actions) // 10)

        if rng.random() < 0.1:
            return rng.choice(ranked_actions[:cutoff])

        top_action = ranked_actions[0]
        top_score = inverted_scores[(top_action["row"], top_action["col"])]
        weights = [math.exp((inverted_scores[(action["row"], action["col"])] - top_score) / temperature) for action in ranked_actions[:cutoff]]
        return rng.choices(ranked_actions[:cutoff], weights=weights, k=1)[0]

    def _annealed_probe_target(
        self,
        legal_actions: list[Action],
        tracking: list[list[str]],
        observation: Observation,
        context: MatchContext,
    ) -> Action:
        scores = self._target_scores(legal_actions, tracking, observation)
        rng = self._match_rng(observation, context)
        temperature = self._target_temperature(observation, tracking)

        exploration_chance = min(0.08, max(0.015, temperature * 0.03))
        if rng.random() < exploration_chance:
            ranked_actions = sorted(legal_actions, key=lambda action: scores[(action["row"], action["col"])], reverse=True)
            cutoff = max(1, len(ranked_actions) // 12)
            return rng.choice(ranked_actions[:cutoff])

        best_score = max(scores.values())
        if best_score <= 0.0:
            return rng.choice(legal_actions)

        shifted = [max(score, 0.0) for score in scores.values()]
        if all(score == 0.0 for score in shifted):
            return rng.choice(legal_actions)

        softmax_temperature = max(0.12, temperature * 0.35)
        max_shifted = max(shifted)
        weights = [math.exp((score - max_shifted) / softmax_temperature) for score in shifted]
        return rng.choices(legal_actions, weights=weights, k=1)[0]

    def _best_probability_target(
        self,
        legal_actions: list[Action],
        tracking: list[list[str]],
        observation: Observation,
    ) -> Action:
        scores = self._target_scores(legal_actions, tracking, observation)
        return max(legal_actions, key=lambda action: (scores[(action["row"], action["col"])] , -action["row"], -action["col"]))

    def _target_scores(
        self,
        legal_actions: list[Action],
        tracking: list[list[str]],
        observation: Observation,
    ) -> dict[tuple[int, int], float]:
        legal_cells = {(action["row"], action["col"]): action for action in legal_actions}
        scores: dict[tuple[int, int], float] = {cell: 0.0 for cell in legal_cells}
        remaining_lengths = self._remaining_ship_lengths(observation)
        has_open_hits = any(cell == "H" for row in tracking for cell in row)

        for length in remaining_lengths:
            for orientation in ("horizontal", "vertical"):
                max_row = BOARD_SIZE if orientation == "horizontal" else BOARD_SIZE - length + 1
                max_col = BOARD_SIZE - length + 1 if orientation == "horizontal" else BOARD_SIZE
                for row in range(max_row):
                    for col in range(max_col):
                        cells = self._cells_for(row, col, length, orientation)
                        if any(tracking[cell_row][cell_col] in {"M", "X"} for cell_row, cell_col in cells):
                            continue

                        hit_overlap = sum(1 for cell_row, cell_col in cells if tracking[cell_row][cell_col] == "H")
                        if has_open_hits and hit_overlap == 0:
                            continue

                        placement_weight = 1.0 + hit_overlap * 4.0
                        if length == max(remaining_lengths):
                            placement_weight *= 1.5
                        for cell_row, cell_col in cells:
                            if (cell_row, cell_col) in scores:
                                scores[(cell_row, cell_col)] += placement_weight

        if all(score == 0.0 for score in scores.values()):
            for (row, col), action in legal_cells.items():
                scores[(row, col)] = float(
                    sum(1 for d_row, d_col in ORTHOGONAL_NEIGHBORS if tracking[row + d_row][col + d_col] == "H")
                )
                if (row + col) % 2 == 0:
                    scores[(row, col)] += 0.25

        return scores

    def _refresh_pending_hits(self, tracking: list[list[str]]) -> None:
        self._pending_hits = [(row, col) for row, col in self._pending_hits if tracking[row][col] == "H"]
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if tracking[row][col] == "H" and (row, col) not in self._pending_hits:
                    self._pending_hits.append((row, col))

    def _remaining_ship_lengths(self, observation: Observation) -> list[int]:
        sunk_ships = {shot["ship"] for shot in observation["private_state"]["your_shots"] if shot["ship"]}
        return [ship["length"] for ship in observation["context"]["ships"] if ship["name"] not in sunk_ships]

    def _target_next_to_hit(self, legal_cells: dict[tuple[int, int], Action]) -> Action | None:
        for row, col in reversed(self._pending_hits):
            for d_row, d_col in ORTHOGONAL_NEIGHBORS:
                candidate = (row + d_row, col + d_col)
                if candidate in legal_cells:
                    return legal_cells[candidate]
        return None

    def _extend_known_line(self, legal_cells: dict[tuple[int, int], Action]) -> Action | None:
        if len(self._pending_hits) < 2:
            return None

        rows = {row for row, _ in self._pending_hits}
        cols = {col for _, col in self._pending_hits}

        if len(rows) == 1:
            row = next(iter(rows))
            ordered_cols = sorted(col for _, col in self._pending_hits)
            if ordered_cols[-1] - ordered_cols[0] == len(ordered_cols) - 1:
                for candidate in [(row, ordered_cols[0] - 1), (row, ordered_cols[-1] + 1)]:
                    if candidate in legal_cells:
                        return legal_cells[candidate]

        if len(cols) == 1:
            col = next(iter(cols))
            ordered_rows = sorted(row for row, _ in self._pending_hits)
            if ordered_rows[-1] - ordered_rows[0] == len(ordered_rows) - 1:
                for candidate in [(ordered_rows[0] - 1, col), (ordered_rows[-1] + 1, col)]:
                    if candidate in legal_cells:
                        return legal_cells[candidate]

        return None

    def _score_targets(
        self,
        observation: Observation,
        legal_cells: dict[tuple[int, int], Action],
        tracking: list[list[str]],
    ) -> dict[Action, float]:
        board_size = observation["context"]["board_size"]
        remaining_lengths = self._remaining_ship_lengths(observation)
        score_by_action: dict[Action, float] = {action: 0.0 for action in legal_cells.values()}

        for length in remaining_lengths:
            for orientation in ("horizontal", "vertical"):
                for row in range(board_size):
                    for col in range(board_size):
                        cells = self._cells_for(row, col, length, orientation)
                        if not self._placement_is_consistent(cells, tracking):
                            continue

                        hit_cells = [(cell_row, cell_col) for cell_row, cell_col in cells if tracking[cell_row][cell_col] == "H"]
                        cluster_bonus = 1.0 + len(hit_cells)
                        for cell_row, cell_col in cells:
                            action = legal_cells.get((cell_row, cell_col))
                            if action is None:
                                continue
                            score_by_action[action] += cluster_bonus

        for action in score_by_action:
            row = action["row"]
            col = action["col"]
            if (row, col) in self._pending_hits:
                score_by_action[action] += 6.0
            elif any((abs(row - hit_row) + abs(col - hit_col)) == 1 for hit_row, hit_col in self._pending_hits):
                score_by_action[action] += 3.0
            elif (row + col) % 2 == 0:
                score_by_action[action] += 0.25

        return score_by_action

    def _remaining_ship_lengths(self, observation: Observation) -> list[int]:
        ships = observation["context"]["ships"]
        sunk_names = {shot["ship"] for shot in observation["private_state"]["your_shots"] if shot["result"] == "sunk" and shot["ship"]}
        return [ship["length"] for ship in ships if ship["name"] not in sunk_names]

    def _target_temperature(self, observation: Observation, tracking: list[list[str]]) -> float:
        turn_index = observation["public_state"]["turn_index"]
        open_hits = sum(1 for row in tracking for cell in row if cell == "H")
        remaining_lengths = self._remaining_ship_lengths(observation)
        base = 1.1 if open_hits == 0 else 0.6
        decay = 0.045 * turn_index + 0.1 * max(0, len(remaining_lengths) - 1)
        return max(0.2, base - decay)

    def _match_rng(self, observation: Observation, context: MatchContext) -> random.Random:
        turn_index = observation["public_state"]["turn_index"]
        seed_value = f"{context.seed}:{self.bot_id}:{turn_index}:{observation['public_state']['current_player']}"
        return random.Random(seed_value)

    def _placement_is_consistent(self, cells: list[tuple[int, int]], tracking: list[list[str]]) -> bool:
        hit_count = 0
        for row, col in cells:
            cell_state = tracking[row][col]
            if cell_state == "M" or cell_state == "X":
                return False
            if cell_state == "H":
                hit_count += 1

        return hit_count > 0 or not self._pending_hits
