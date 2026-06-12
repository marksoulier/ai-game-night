from __future__ import annotations

import random
from dataclasses import dataclass
from gamenight.core.types import Action, MatchContext, Observation

BOARD_SIZE = 10
ORTHOGONAL_NEIGHBORS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
ALL_NEIGHBORS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

class PlayerBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        pass

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        if observation["public_state"]["phase"] == "placement":
            return self._choose_placement(observation, context)
        return self._choose_target(observation, context)

    def _choose_placement(self, observation: Observation, context: MatchContext) -> Action:
        legal_actions = observation["legal_actions"]
        tracking = observation["private_state"]["your_board"]
        ship_order = [ship["name"] for ship in observation["context"]["ships"]]
        ship_name = observation["context"]["next_ship_to_place"]
        ship_index = ship_order.index(ship_name) if ship_name in ship_order else 0
        preferred_edge = ship_index % 4
        
        # Identify occupied cells to apply a "no touch" heuristic
        occupied = set()
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if tracking[r][c] != "~":
                    occupied.add((r, c))

        # We'd like to minimize adjacent cells
        def score_placement(action: Action) -> float:
            length = next(s["length"] for s in observation["context"]["ships"] if s["name"] == action["ship"])
            cells = self._cells_for(action["row"], action["col"], length, action["orientation"])
            
            touch_penalty = 0
            edge_bonus = 0.0
            corner_penalty = 0.0
            for r, c in cells:
                for dr, dc in ALL_NEIGHBORS:
                    if (r + dr, c + dc) in occupied:
                        touch_penalty += 1
                on_top = r == 0
                on_bottom = r == BOARD_SIZE - 1
                on_left = c == 0
                on_right = c == BOARD_SIZE - 1
                on_edge = on_top or on_bottom or on_left or on_right
                on_corner = (on_top or on_bottom) and (on_left or on_right)

                if on_corner:
                    corner_penalty += 1.5
                elif on_edge:
                    edge_bonus += 0.9

                if (
                    (preferred_edge == 0 and on_top)
                    or (preferred_edge == 1 and on_right)
                    or (preferred_edge == 2 and on_bottom)
                    or (preferred_edge == 3 and on_left)
                ):
                    edge_bonus += 0.75

            # Seed for randomization
            rng = random.Random(f"{context.seed}:{self.bot_id}:{action['ship']}:{action['row']}:{action['col']}:{action['orientation']}")
            noise = rng.random() * 0.2

            return touch_penalty + corner_penalty - edge_bonus + noise

        return min(legal_actions, key=score_placement)

    def _cells_for(self, row: int, col: int, length: int, orientation: str) -> list[tuple[int, int]]:
        if orientation == "horizontal":
            return [(row, col + offset) for offset in range(length)]
        return [(row + offset, col) for offset in range(length)]

    def _remaining_ship_lengths(self, observation: Observation) -> list[int]:
        sunk_ships = {shot["ship"] for shot in observation["private_state"]["your_shots"] if shot["ship"]}
        return [ship["length"] for ship in observation["context"]["ships"] if ship["name"] not in sunk_ships]

    def _choose_target(self, observation: Observation, context: MatchContext) -> Action:
        legal_actions = observation["legal_actions"]
        tracking = observation["private_state"]["tracking_grid"]
        
        valid_cells = {(a["row"], a["col"]): a for a in legal_actions}
        
        remaining_lengths = self._remaining_ship_lengths(observation)
        
        # Grid probability counts
        probs = {cell: 0.0 for cell in valid_cells}
        
        pending_hits = []
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if tracking[r][c] == "H":
                    pending_hits.append((r, c))
                    
        is_hunt_mode = len(pending_hits) == 0
                    
        for length in remaining_lengths:
            for orientation in ("horizontal", "vertical"):
                max_row = BOARD_SIZE if orientation == "horizontal" else BOARD_SIZE - length + 1
                max_col = BOARD_SIZE - length + 1 if orientation == "horizontal" else BOARD_SIZE
                
                for r in range(max_row):
                    for c in range(max_col):
                        cells = self._cells_for(r, c, length, orientation)
                        
                        # Check if placement is possible
                        possible = True
                        hits_covered = 0
                        for cr, cc in cells:
                            if tracking[cr][cc] in ("M", "X"):
                                possible = False
                                break
                            if tracking[cr][cc] == "H":
                                hits_covered += 1
                        
                        if not possible:
                            continue
                            
                        if not is_hunt_mode and hits_covered == 0:
                            continue
                            
                        weight = 1.0
                        if not is_hunt_mode:
                            weight = 10.0 ** hits_covered
                            
                        for cr, cc in cells:
                            if (cr, cc) in valid_cells:
                                probs[(cr, cc)] += weight

        if is_hunt_mode:
            # Apply checkerboard parity
            for (r, c) in probs:
                if (r + c) % 2 != 0:
                    probs[(r, c)] *= 0.01  # Heavily bias against incorrect parity

        # Add a tiny amount of noise
        rng = random.Random(f"{context.seed}:{self.bot_id}:{observation['public_state']['turn_index']}")
        
        best_prob = -1
        best_actions = []
        for cell, p in probs.items():
            if p > best_prob + 1e-6:
                best_prob = p
                best_actions = [valid_cells[cell]]
            elif abs(p - best_prob) <= 1e-6:
                best_actions.append(valid_cells[cell])
                
        if not best_actions:
            best_actions = list(valid_cells.values())
            
        return rng.choice(best_actions)
