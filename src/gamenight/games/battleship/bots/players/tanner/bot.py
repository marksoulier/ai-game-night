from __future__ import annotations

from dataclasses import dataclass

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

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        """Tanner's minimal battleship strategy:
        - Placement: spread ships across the board (every 2-3 cells)
        - Battle: hunt adjacent cells after a hit, otherwise use checkerboard
        """
        legal_actions = observation["legal_actions"]
        
        # Placement phase: pick placements that spread the fleet out
        if observation["public_state"]["phase"] == "placement":
            # Prefer placements that are spaced away from board edges
            # and distributed across different areas
            for action in legal_actions:
                row, col = action["row"], action["col"]
                # Prefer mid-board placements (rows/cols 2-7)
                if 2 <= row <= 7 and 2 <= col <= 7:
                    return action
            # If no mid-board option, take any legal placement
            return legal_actions[0]
        
        # Battle phase: hunt and target
        else:
            tracking_grid = observation["private_state"]["tracking_grid"]
            
            # Look for unhit "H" (hit but not sunk) and target its neighbors
            for row in range(10):
                for col in range(10):
                    if tracking_grid[row][col] == "H":
                        # Try to fire at orthogonal neighbors
                        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nr, nc = row + dr, col + dc
                            if 0 <= nr < 10 and 0 <= nc < 10:
                                # Check if this cell is a legal action (not already fired at)
                                neighbor_action = {"type": "fire", "row": nr, "col": nc}
                                if neighbor_action in legal_actions:
                                    return neighbor_action
            
            # No adjacent hits to pursue: use checkerboard pattern
            # Fire at cells where (row + col) is even, for good coverage
            for action in legal_actions:
                if (action["row"] + action["col"]) % 2 == 0:
                    return action
            
            # Fallback: take first legal action
            return legal_actions[0]
