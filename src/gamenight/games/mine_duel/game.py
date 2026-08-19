from __future__ import annotations

import random
from copy import deepcopy

from gamenight.core.protocols import BotProtocol
from gamenight.core.types import Action, Observation, StepResult
from gamenight.games.mine_duel.bots.baselines.greedy_bot import GreedyBot
from gamenight.games.mine_duel.bots.baselines.human_terminal import HumanTerminalBot
from gamenight.games.mine_duel.bots.baselines.random_bot import RandomBot


# Matches Google's Minesweeper (google.com/fbx?fbx=minesweeper) "Medium" difficulty:
# an 18x14 board (252 cells) with 40 mines, ~15.9% mine density -- between its own
# Easy (10x8, 10 mines) and Hard (24x20, 99 mines, same density as classic Expert).
ROWS = 14
COLS = 18
MINE_COUNT = 40
TOTAL_CELLS = ROWS * COLS
TOTAL_SAFE_CELLS = TOTAL_CELLS - MINE_COUNT
MINE_PENALTY = 1

_NEIGHBOR_OFFSETS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1), (0, 1),
    (1, -1), (1, 0), (1, 1),
]


def _neighbors(row: int, col: int) -> list[tuple[int, int]]:
    result = []
    for d_row, d_col in _NEIGHBOR_OFFSETS:
        r, c = row + d_row, col + d_col
        if 0 <= r < ROWS and 0 <= c < COLS:
            result.append((r, c))
    return result


class MineDuelGame:
    game_id = "mine_duel"
    player_ids = ["player_ember", "player_frost"]

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
        rng = random.Random(seed)
        # The center cell is reserved as a neutral "bootstrap" opening (see below) and
        # can never itself be a mine -- same idea as classic Minesweeper's safe-first-
        # click guarantee, just anchored to a fixed cell instead of the player's pick.
        center = (ROWS // 2, COLS // 2)
        mineable = [i for i in range(TOTAL_CELLS) if (i // COLS, i % COLS) != center]
        mine_positions = set(rng.sample(mineable, MINE_COUNT))

        cells = []
        for row in range(ROWS):
            row_cells = []
            for col in range(COLS):
                is_mine = (row * COLS + col) in mine_positions
                row_cells.append(
                    {
                        "mine": is_mine,
                        "adjacent": 0,
                        "revealed": False,
                        "revealed_by": None,
                    }
                )
            cells.append(row_cells)

        for row in range(ROWS):
            for col in range(COLS):
                if cells[row][col]["mine"]:
                    continue
                cells[row][col]["adjacent"] = sum(
                    1 for nr, nc in _neighbors(row, col) if cells[nr][nc]["mine"]
                )

        # Neutral bootstrap opening: reveal (and flood-cascade from) the center cell
        # before anyone's first turn, with `revealed_by=None` and no score awarded.
        #
        # Without this, whichever player moves first gets a *guaranteed* crack at
        # revealing into a completely untouched board -- empirically the single
        # highest-value reveal of the entire game by a wide margin (mine-hit risk
        # aside, a blank board is exactly when the biggest flood-fill cascades are
        # still fully intact). That handed player one a structural scoring edge on
        # essentially every game, independent of either bot's skill. Opening on a
        # shared, unscored cell removes that -- both players' *first actual turn*
        # starts from the same partially-opened board instead of one of them getting
        # the one guaranteed jackpot click. See EDGE_CASES.md for the measurement.
        opening_revealed = self._flood_reveal(cells, center[0], center[1], actor=None)

        first_id = self.player_ids[0]
        return {
            "current_player": first_id,
            "turn_index": 0,
            "done": False,
            "winner": None,
            "cells": cells,
            "scores": {pid: 0 for pid in self.player_ids},
            "safe_remaining": TOTAL_SAFE_CELLS - len(opening_revealed),
        }

    def current_player(self, state: dict) -> str:
        return state["current_player"]

    def legal_actions(self, state: dict, player_id: str) -> list[Action]:
        if state["done"] or player_id != state["current_player"]:
            return []
        return [
            {"type": "reveal", "row": row, "col": col}
            for row in range(ROWS)
            for col in range(COLS)
            if not state["cells"][row][col]["revealed"]
        ]

    def observe(self, state: dict, player_id: str) -> Observation:
        opponent_id = self._opponent(player_id)
        return {
            "public_state": {
                "current_player": state["current_player"],
                "turn_index": state["turn_index"],
                "done": state["done"],
                "winner": state["winner"],
                "scores": dict(state["scores"]),
                "safe_cells_remaining": state["safe_remaining"],
                "board": self._render_board(state["cells"]),
                "owner_grid": self._render_owner_grid(state["cells"]),
            },
            # Mine Duel has no hidden information relative to your opponent -- the
            # mine layout is unknown to BOTH players equally (it's random world state,
            # not a secret either side holds), so there is nothing player-specific to
            # redact. This is empty on purpose; see BOT_SPEC.md's Information Policy.
            "private_state": {},
            "context": {
                "opponent_id": opponent_id,
                "rows": ROWS,
                "cols": COLS,
                "mine_count": MINE_COUNT,
                "total_safe_cells": TOTAL_SAFE_CELLS,
                "mine_penalty": MINE_PENALTY,
            },
        }

    def step(self, state: dict, action: Action) -> StepResult:
        if state["done"]:
            return StepResult(next_state=state, rewards=self._rewards(state["winner"]), done=True)

        next_state = deepcopy(state)
        actor = next_state["current_player"]
        row, col = int(action["row"]), int(action["col"])
        cell = next_state["cells"][row][col]

        if cell["revealed"]:
            raise ValueError(
                f"{actor} tried to reveal ({row}, {col}) which is already revealed -- "
                "callers must only pass legal_actions"
            )

        if cell["mine"]:
            cell["revealed"] = True
            cell["revealed_by"] = actor
            next_state["scores"][actor] -= MINE_PENALTY
            events = [
                {
                    "type": "reveal",
                    "player": actor,
                    "row": row,
                    "col": col,
                    "result": "mine",
                }
            ]
        else:
            revealed_cells = self._flood_reveal(next_state["cells"], row, col, actor)
            next_state["scores"][actor] += len(revealed_cells)
            next_state["safe_remaining"] -= len(revealed_cells)
            events = [
                {
                    "type": "reveal",
                    "player": actor,
                    "row": row,
                    "col": col,
                    "result": "safe",
                    "cells_revealed": [[r, c] for r, c in revealed_cells],
                }
            ]

        next_state["turn_index"] += 1

        if next_state["safe_remaining"] <= 0:
            next_state["done"] = True
            next_state["winner"] = self._decide_winner(next_state["scores"])
        else:
            next_state["current_player"] = self._opponent(actor)

        rewards = self._rewards(next_state["winner"] if next_state["done"] else None)
        return StepResult(next_state=next_state, rewards=rewards, done=next_state["done"], events=events)

    def render_text(self, state: dict) -> str:
        board = self._render_board(state["cells"])
        header = "    " + " ".join(str(c) for c in range(COLS))
        lines = [
            f"Turn {state['turn_index']}  |  current_player: {state['current_player']}",
        ]
        if state["done"]:
            lines.append(f"Game over: winner is {state['winner']}")
        lines.append(f"Scores: " + "  ".join(f"{pid}={score}" for pid, score in state["scores"].items()))
        lines.append(f"Safe cells remaining: {state['safe_remaining']}")
        lines.append(header)
        for row in range(ROWS):
            lines.append(f"{row:2d}  " + " ".join(board[row]))
        lines.append("Legend: ? hidden   0-8 revealed safe cell (adjacent mine count)   M revealed mine")
        return "\n".join(lines)

    # -- flood fill -------------------------------------------------------------------

    def _flood_reveal(
        self, cells: list[list[dict]], start_row: int, start_col: int, actor: str | None
    ) -> list[tuple[int, int]]:
        """Reveal `(start_row, start_col)` (never a mine -- callers check that first)
        and, if it's a 0, cascade outward exactly like classic Minesweeper: keep
        revealing neighbors of 0-cells, but never auto-reveal a mine and never recurse
        past a non-zero numbered cell (it gets revealed, just not expanded from).

        `actor=None` marks a neutral reveal (the initial center bootstrap) that isn't
        credited to either player's score -- see `create_initial_state`."""
        stack = [(start_row, start_col)]
        seen: set[tuple[int, int]] = set()
        revealed: list[tuple[int, int]] = []

        while stack:
            row, col = stack.pop()
            if (row, col) in seen:
                continue
            seen.add((row, col))
            cell = cells[row][col]
            if cell["revealed"] or cell["mine"]:
                continue

            cell["revealed"] = True
            cell["revealed_by"] = actor
            revealed.append((row, col))

            if cell["adjacent"] == 0:
                for nr, nc in _neighbors(row, col):
                    if (nr, nc) not in seen:
                        stack.append((nr, nc))

        return revealed

    # -- rendering ----------------------------------------------------------------------

    def _render_board(self, cells: list[list[dict]]) -> list[list[str]]:
        grid = []
        for row in cells:
            display_row = []
            for cell in row:
                if not cell["revealed"]:
                    display_row.append("?")
                elif cell["mine"]:
                    display_row.append("M")
                else:
                    display_row.append(str(cell["adjacent"]))
            grid.append(display_row)
        return grid

    def _render_owner_grid(self, cells: list[list[dict]]) -> list[list[str | None]]:
        return [[cell["revealed_by"] for cell in row] for row in cells]

    # -- shared helpers -----------------------------------------------------------------

    def _opponent(self, player_id: str) -> str:
        first_id, second_id = self.player_ids
        return second_id if player_id == first_id else first_id

    def _decide_winner(self, scores: dict[str, int]) -> str | None:
        first_id, second_id = self.player_ids
        if scores[first_id] > scores[second_id]:
            return first_id
        if scores[second_id] > scores[first_id]:
            return second_id
        return None

    def _rewards(self, winner: str | None) -> dict[str, float]:
        first_id, second_id = self.player_ids
        if winner == first_id:
            return {first_id: 1.0, second_id: 0.0}
        if winner == second_id:
            return {first_id: 0.0, second_id: 1.0}
        return {first_id: 0.5, second_id: 0.5}
