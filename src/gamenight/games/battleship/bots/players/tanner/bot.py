from __future__ import annotations

from dataclasses import dataclass
import random
from collections import defaultdict

from gamenight.core.types import Action, MatchContext, Observation


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

    def reset(self, context: MatchContext) -> None:
        return None

    def _is_valid_placement_with_guard(self, action: Action, legal_actions: list[Action], 
                                       existing_placements: list[list[int]], context_ships: list, guard_region: int = 2) -> bool:
        """Check if placement respects guard region (2-block buffer) around existing ships."""
        row, col = action["row"], action["col"]
        orientation = action["orientation"]
        ship_name = action.get("ship")
        
        # Get ship length from context
        ship_length = 0
        for ship in context_ships:
            if ship["name"] == ship_name:
                ship_length = ship["length"]
                break
        
        if ship_length == 0:
            return False
        
        # Get ship cells for this placement
        if orientation == "horizontal":
            placement_cells = [[row, col + i] for i in range(ship_length)]
        else:
            placement_cells = [[row + i, col] for i in range(ship_length)]
        
        # Check if any placement cell is within guard_region of existing ships
        for placed_cell in existing_placements:
            for new_cell in placement_cells:
                dist = abs(placed_cell[0] - new_cell[0]) + abs(placed_cell[1] - new_cell[1])
                if dist < guard_region:
                    return False
        return True

    def _get_ship_length(self, action: Action, context: MatchContext) -> int:
        """Infer ship length from the action (need to look at legal actions or context)."""
        # Extract from context ships list based on ship name in action
        if "ship" in action:
            for ship in context.get("ships", []):
                if ship["name"] == action["ship"]:
                    return ship["length"]
        return 0

    def _calculate_ship_density_map(self, observation: Observation) -> list[list[float]]:
        """Bayesian probabilistic map: estimate where opponent's remaining ships are likely positioned."""
        tracking_grid = observation["private_state"]["tracking_grid"]
        board_size = observation["context"]["board_size"]
        ships = observation["context"]["ships"]
        
        # Get remaining ship sizes (not sunk)
        remaining_ships = ships.copy()
        for shot in observation["private_state"]["your_shots"]:
            if shot["ship"]:  # Sunk ship
                remaining_ships = [s for s in remaining_ships if s["name"] != shot["ship"]]
        
        if not remaining_ships:
            # All ships sunk, shouldn't happen but handle gracefully
            return [[0.0 for _ in range(board_size)] for _ in range(board_size)]
        
        # Initialize probability map
        prob_map = [[0.0 for _ in range(board_size)] for _ in range(board_size)]
        
        # For each cell, calculate likelihood a ship occupies it
        for row in range(board_size):
            for col in range(board_size):
                cell_state = tracking_grid[row][col]
                
                # Skip cells we know about - definitely penalize them
                if cell_state in ["M", "X"]:
                    prob_map[row][col] = 0.0
                    continue
                
                # Hits are weighted higher (ships definitely there)
                if cell_state == "H":
                    prob_map[row][col] = 10.0
                    continue
                
                # For unknown cells, count valid placements
                count = 0
                for ship in remaining_ships:
                    length = ship["length"]
                    
                    # Check horizontal placements that include this cell
                    for start_col in range(max(0, col - length + 1), min(board_size - length + 1, col + 1)):
                        # Check if all cells in this placement are valid
                        valid = True
                        for check_col in range(start_col, start_col + length):
                            grid_cell = tracking_grid[row][check_col]
                            # Can place if unknown or hit
                            if grid_cell not in ["?", "H"]:
                                valid = False
                                break
                        if valid:
                            count += 1
                    
                    # Check vertical placements that include this cell
                    for start_row in range(max(0, row - length + 1), min(board_size - length + 1, row + 1)):
                        # Check if all cells in this placement are valid
                        valid = True
                        for check_row in range(start_row, start_row + length):
                            grid_cell = tracking_grid[check_row][col]
                            # Can place if unknown or hit
                            if grid_cell not in ["?", "H"]:
                                valid = False
                                break
                        if valid:
                            count += 1
                
                prob_map[row][col] = float(count)
        
        # Normalize (but keep hits high)
        max_prob = max(max(row) for row in prob_map) or 1.0
        for row in range(board_size):
            for col in range(board_size):
                if tracking_grid[row][col] != "H":
                    prob_map[row][col] /= max_prob
        
        return prob_map

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        """Tanner's TURBO battleship bot:
        - Placement: random with 70% guard region enforcement
        - Battle: hunt established vectors, then Bayesian probabilistic targeting
        """
        legal_actions = observation["legal_actions"]
        phase = observation["public_state"]["phase"]
        
        # ===== PLACEMENT PHASE =====
        if phase == "placement":
            use_strict_guard = random.random() < 0.7
            
            # Collect existing placements from your_fleet
            existing_placements = []
            your_fleet = observation["private_state"]["your_fleet"]
            for ship in your_fleet:
                existing_placements.extend(ship["cells"])
            
            context_ships = observation["context"]["ships"]
            
            # Always enforce some guard region - 70% strict (2-cell), 30% relaxed (1-cell)
            guard_distance = 2 if use_strict_guard else 1
            valid_actions = [
                action for action in legal_actions
                if self._is_valid_placement_with_guard(action, legal_actions, existing_placements, context_ships, guard_region=guard_distance)
            ]
            
            if valid_actions:
                return random.choice(valid_actions)
            
            # Fallback: if no valid guard placement found, try looser guard
            if use_strict_guard:
                valid_actions = [
                    action for action in legal_actions
                    if self._is_valid_placement_with_guard(action, legal_actions, existing_placements, context_ships, guard_region=1)
                ]
                if valid_actions:
                    return random.choice(valid_actions)
            
            # Last resort: pick random (shouldn't happen often)
            return random.choice(legal_actions)
        
        # ===== BATTLE PHASE =====
        else:
            tracking_grid = observation["private_state"]["tracking_grid"]
            your_shots = observation["private_state"]["your_shots"]
            
            # Step 1: Hunt established hit vectors
            hit_cells = []
            for row in range(10):
                for col in range(10):
                    if tracking_grid[row][col] == "H":
                        hit_cells.append([row, col])
            
            if hit_cells:
                # Try to establish vector and continue hunting
                best_hunt_action = self._hunt_hits(hit_cells, tracking_grid, legal_actions)
                if best_hunt_action:
                    return best_hunt_action
            
            # Step 2: Distributed search pattern - space out shots
            # Use a distributed grid-based approach for maximum board coverage
            distributed_actions = self._get_distributed_search_actions(tracking_grid, legal_actions)
            if distributed_actions:
                return distributed_actions[0]
            
            # Fallback
            return legal_actions[0]
    
    def _get_distributed_search_actions(self, tracking_grid: list[list[str]], legal_actions: list[Action]) -> list[Action]:
        """Get distributed search pattern - prioritize cells that spread coverage across board."""
        # Create distribution by quadrants and spacing
        candidates_by_coverage = defaultdict(list)
        
        for action in legal_actions:
            row, col = action["row"], action["col"]
            
            # Calculate coverage score: prefer cells far from already-fired areas
            min_distance_to_known = 100
            for check_row in range(10):
                for check_col in range(10):
                    if tracking_grid[check_row][check_col] in ["M", "H", "X"]:
                        dist = abs(row - check_row) + abs(col - check_col)
                        min_distance_to_known = min(min_distance_to_known, dist)
            
            # Prefer cells that are far from known shots (spreading out)
            coverage_score = min_distance_to_known
            candidates_by_coverage[coverage_score].append(action)
        
        # Return actions with highest coverage score (furthest from known shots)
        if candidates_by_coverage:
            best_score = max(candidates_by_coverage.keys())
            return candidates_by_coverage[best_score]
        
        return legal_actions

    def _hunt_hits(self, hit_cells: list[list[int]], tracking_grid: list[list[str]], 
                   legal_actions: list[Action]) -> Action | None:
        """Hunt adjacent cells around hits, establishing vector of attack with priority."""
        if not hit_cells:
            return None
        
        priority_candidates = []
        secondary_candidates = []
        
        for hit_row, hit_col in hit_cells:
            # Check if there's another hit in the same row (horizontal ship)
            horizontal_hits = [h for h in hit_cells if h[0] == hit_row and h[1] != hit_col]
            if horizontal_hits:
                # Narrow along the row - find endpoints
                all_cols = [hit_col] + [h[1] for h in horizontal_hits]
                min_col = min(all_cols)
                max_col = max(all_cols)
                # Fire beyond the cluster (high priority)
                for nc in [min_col - 1, max_col + 1]:
                    if 0 <= nc < 10:
                        action = {"type": "fire", "row": hit_row, "col": nc}
                        if action in legal_actions and tracking_grid[hit_row][nc] == "?":
                            priority_candidates.append(action)
            
            # Check if there's another hit in the same column (vertical ship)
            vertical_hits = [h for h in hit_cells if h[1] == hit_col and h[0] != hit_row]
            if vertical_hits:
                # Narrow along the column - find endpoints
                all_rows = [hit_row] + [h[0] for h in vertical_hits]
                min_row = min(all_rows)
                max_row = max(all_rows)
                # Fire beyond the cluster (high priority)
                for nr in [min_row - 1, max_row + 1]:
                    if 0 <= nr < 10:
                        action = {"type": "fire", "row": nr, "col": hit_col}
                        if action in legal_actions and tracking_grid[nr][hit_col] == "?":
                            priority_candidates.append(action)
        
        # Prioritize established lines first
        if priority_candidates:
            return random.choice(priority_candidates)
        
        # No established line yet - collect orthogonal neighbors more conservatively
        seen = set()
        for hit_row, hit_col in hit_cells:
            directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            for dr, dc in directions:
                nr, nc = hit_row + dr, hit_col + dc
                if 0 <= nr < 10 and 0 <= nc < 10 and (nr, nc) not in seen:
                    if tracking_grid[nr][nc] == "?":
                        action = {"type": "fire", "row": nr, "col": nc}
                        if action in legal_actions:
                            secondary_candidates.append(action)
                            seen.add((nr, nc))
        
        if secondary_candidates:
            return random.choice(secondary_candidates)
        
        return None
