from __future__ import annotations

from copy import deepcopy

from gamenight.core.protocols import BotProtocol
from gamenight.core.types import Action, Observation, StepResult
from gamenight.games.battleship.bots.baselines.greedy_bot import GreedyBot
from gamenight.games.battleship.bots.baselines.human_terminal import HumanTerminalBot
from gamenight.games.battleship.bots.baselines.random_bot import RandomBot


BOARD_SIZE = 10
SHIPS = [
    ("carrier", 5),
    ("battleship", 4),
    ("cruiser", 3),
    ("submarine", 3),
    ("destroyer", 2),
]
SHIP_LENGTHS = dict(SHIPS)


def _ship_cells(row: int, col: int, length: int, orientation: str) -> list[list[int]]:
    if orientation == "horizontal":
        return [[row, col + offset] for offset in range(length)]
    return [[row + offset, col] for offset in range(length)]


def _in_bounds(cells: list[list[int]]) -> bool:
    return all(0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE for r, c in cells)


class BattleshipGame:
    game_id = "battleship"
    player_ids = ["player_blue", "player_orange"]

    def build_baseline_bot(self, name: str, bot_id: str) -> BotProtocol:
        baseline = name.lower().strip()
        if baseline == "random":
            return RandomBot(bot_id=bot_id)
        if baseline == "human":
            return HumanTerminalBot(bot_id=bot_id)
        if baseline == "greedy":
            return GreedyBot(bot_id=bot_id)
        raise ValueError(f"Unknown bot name: {name}")

    def create_initial_state(self, seed: int | None = None) -> dict:
        first_id, second_id = self.player_ids
        return {
            "phase": "placement",
            "current_player": first_id,
            "turn_index": 0,
            "done": False,
            "winner": None,
            "fleets": {first_id: [], second_id: []},
            "shots": {first_id: [], second_id: []},
        }

    def current_player(self, state: dict) -> str:
        return state["current_player"]

    def legal_actions(self, state: dict, player_id: str) -> list[Action]:
        if state["done"] or player_id != state["current_player"]:
            return []
        if state["phase"] == "placement":
            return self._legal_placements(state, player_id)
        return self._legal_shots(state, player_id)

    def observe(self, state: dict, player_id: str) -> Observation:
        opponent_id = self._opponent(player_id)
        your_fleet = state["fleets"][player_id]
        your_shots = state["shots"][player_id]
        incoming_shots = state["shots"][opponent_id]

        next_ship = None
        if state["phase"] == "placement" and len(your_fleet) < len(SHIPS):
            next_ship = SHIPS[len(your_fleet)][0]

        return {
            "public_state": {
                "phase": state["phase"],
                "current_player": state["current_player"],
                "turn_index": state["turn_index"],
                "done": state["done"],
                "winner": state["winner"],
            },
            "private_state": {
                "your_fleet": [self._ship_view(ship) for ship in your_fleet],
                "your_board": self._render_own_board(your_fleet, incoming_shots),
                "your_shots": [dict(shot) for shot in your_shots],
                "tracking_grid": self._render_tracking_grid(your_shots),
            },
            "context": {
                "opponent_id": opponent_id,
                "board_size": BOARD_SIZE,
                "ships": [{"name": name, "length": length} for name, length in SHIPS],
                "next_ship_to_place": next_ship,
            },
        }

    def step(self, state: dict, action: Action) -> StepResult:
        if state["done"]:
            return StepResult(next_state=state, rewards=self._rewards(state["winner"]), done=True)

        next_state = deepcopy(state)
        actor = next_state["current_player"]

        if action["type"] == "place_ship":
            events = self._apply_placement(next_state, actor, action)
        else:
            events = self._apply_shot(next_state, actor, action)

        next_state["turn_index"] += 1
        rewards = self._rewards(next_state["winner"])
        return StepResult(next_state=next_state, rewards=rewards, done=next_state["done"], events=events)

    def render_text(self, state: dict) -> str:
        first_id, second_id = self.player_ids
        lines = [
            f"Phase: {state['phase']}  |  Turn {state['turn_index']}  |  current_player: {state['current_player']}"
        ]
        if state["done"]:
            lines.append(f"Game over: winner is {state['winner']}")

        left = self._render_player_board(state, first_id)
        right = self._render_player_board(state, second_id)
        lines.append(f"{first_id:<24}{second_id}")
        for left_line, right_line in zip(left, right):
            lines.append(f"{left_line}    {right_line}")

        for player_id in self.player_ids:
            sunk = [ship["name"] for ship in state["fleets"][player_id] if ship["sunk"]]
            if sunk:
                lines.append(f"{player_id} ships sunk: {', '.join(sunk)}")

        lines.append("Legend: ~ water   # ship   X hit   O miss")
        return "\n".join(lines)

    # -- placement -----------------------------------------------------------------

    def _legal_placements(self, state: dict, player_id: str) -> list[Action]:
        fleet = state["fleets"][player_id]
        ship_name, length = SHIPS[len(fleet)]
        occupied = {tuple(cell) for ship in fleet for cell in ship["cells"]}

        actions: list[Action] = []
        for orientation in ("horizontal", "vertical"):
            for row in range(BOARD_SIZE):
                for col in range(BOARD_SIZE):
                    cells = _ship_cells(row, col, length, orientation)
                    if not _in_bounds(cells):
                        continue
                    if any(tuple(cell) in occupied for cell in cells):
                        continue
                    actions.append(
                        {
                            "type": "place_ship",
                            "ship": ship_name,
                            "row": row,
                            "col": col,
                            "orientation": orientation,
                        }
                    )
        return actions

    def _apply_placement(self, state: dict, player_id: str, action: Action) -> list[dict]:
        ship_name = action["ship"]
        length = SHIP_LENGTHS[ship_name]
        cells = _ship_cells(int(action["row"]), int(action["col"]), length, action["orientation"])
        state["fleets"][player_id].append({"name": ship_name, "cells": cells, "hits": [], "sunk": False})

        first_id, second_id = self.player_ids
        if len(state["fleets"][player_id]) == len(SHIPS):
            if player_id == first_id:
                state["current_player"] = second_id
            else:
                state["phase"] = "battle"
                state["current_player"] = first_id

        return [{"type": "place_ship", "player": player_id, "ship": ship_name, "cells": cells}]

    # -- battle ---------------------------------------------------------------------

    def _legal_shots(self, state: dict, player_id: str) -> list[Action]:
        fired = {(shot["row"], shot["col"]) for shot in state["shots"][player_id]}
        return [
            {"type": "fire", "row": row, "col": col}
            for row in range(BOARD_SIZE)
            for col in range(BOARD_SIZE)
            if (row, col) not in fired
        ]

    def _apply_shot(self, state: dict, player_id: str, action: Action) -> list[dict]:
        opponent_id = self._opponent(player_id)
        row, col = int(action["row"]), int(action["col"])

        if any(shot["row"] == row and shot["col"] == col for shot in state["shots"][player_id]):
            raise ValueError(
                f"{player_id} already fired at ({row}, {col}) -- callers must only pass legal_actions"
            )

        target_ship = None
        for ship in state["fleets"][opponent_id]:
            if [row, col] in ship["cells"]:
                target_ship = ship
                break

        if target_ship is None:
            shot_result = "miss"
        else:
            target_ship["hits"].append([row, col])
            target_ship["sunk"] = len(target_ship["hits"]) == len(target_ship["cells"])
            shot_result = "sunk" if target_ship["sunk"] else "hit"

        state["shots"][player_id].append({"row": row, "col": col, "result": shot_result, "ship": None})

        sunk_ship_name = None
        if target_ship is not None and target_ship["sunk"]:
            sunk_ship_name = target_ship["name"]
            cell_set = {tuple(cell) for cell in target_ship["cells"]}
            for shot in state["shots"][player_id]:
                if (shot["row"], shot["col"]) in cell_set:
                    shot["result"] = "sunk"
                    shot["ship"] = sunk_ship_name

        if all(ship["sunk"] for ship in state["fleets"][opponent_id]):
            state["done"] = True
            state["winner"] = player_id
        else:
            state["current_player"] = opponent_id

        return [
            {
                "type": "fire",
                "player": player_id,
                "row": row,
                "col": col,
                "result": shot_result,
                "ship": sunk_ship_name,
            }
        ]

    # -- shared helpers ---------------------------------------------------------------

    def _opponent(self, player_id: str) -> str:
        first_id, second_id = self.player_ids
        return second_id if player_id == first_id else first_id

    def _ship_view(self, ship: dict) -> dict:
        return {
            "name": ship["name"],
            "length": len(ship["cells"]),
            "cells": [cell[:] for cell in ship["cells"]],
            "hits": [cell[:] for cell in ship["hits"]],
            "sunk": ship["sunk"],
        }

    def _render_own_board(self, fleet: list[dict], incoming_shots: list[dict]) -> list[list[str]]:
        grid = [["~"] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        for ship in fleet:
            hit_cells = {tuple(cell) for cell in ship["hits"]}
            for cell in ship["cells"]:
                row, col = cell
                if tuple(cell) not in hit_cells:
                    grid[row][col] = "S"
                elif ship["sunk"]:
                    grid[row][col] = "X"
                else:
                    grid[row][col] = "H"
        for shot in incoming_shots:
            row, col = shot["row"], shot["col"]
            if grid[row][col] == "~":
                grid[row][col] = "M"
        return grid

    def _render_tracking_grid(self, your_shots: list[dict]) -> list[list[str]]:
        symbols = {"miss": "M", "hit": "H", "sunk": "X"}
        grid = [["?"] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        for shot in your_shots:
            grid[shot["row"]][shot["col"]] = symbols[shot["result"]]
        return grid

    def _render_player_board(self, state: dict, player_id: str) -> list[str]:
        grid = [["~"] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        for ship in state["fleets"][player_id]:
            for cell in ship["cells"]:
                row, col = cell
                grid[row][col] = "#"
        for shot in state["shots"][self._opponent(player_id)]:
            row, col = shot["row"], shot["col"]
            grid[row][col] = "X" if shot["result"] in ("hit", "sunk") else "O"

        header = "    " + " ".join(str(col) for col in range(BOARD_SIZE))
        rows = [header]
        for row in range(BOARD_SIZE):
            rows.append(f"{row:2d}  " + " ".join(grid[row]))
        return rows

    def _rewards(self, winner: str | None) -> dict[str, float]:
        first_id, second_id = self.player_ids
        if winner == first_id:
            return {first_id: 1.0, second_id: 0.0}
        if winner == second_id:
            return {first_id: 0.0, second_id: 1.0}
        return {first_id: 0.0, second_id: 0.0}
