from __future__ import annotations

from gamenight.core.types import Action, MatchContext, Observation

BOARD_SIZE = 10


def _print_grid(grid: list[list[str]]) -> None:
    header = "    " + "  ".join(str(col) for col in range(BOARD_SIZE))
    print(f"  {header}")
    for row_index, row in enumerate(grid):
        print(f"  {row_index:2d}  " + "  ".join(row))


class HumanTerminalBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        """Show the human everything the AI sees, then return their chosen move.

        `observation` is typed as a plain dict — every game has its own shape, so an
        editor can only tell you "dict". Here is *exactly* what Battleship puts inside
        it, field by field. (The authoritative version lives in BOT_SPEC.md, with a full
        worked example in EXAMPLES.md — this is the same shape, annotated inline.)

        Battleship has **hidden information** and **two phases**, so the shape below
        looks bigger than Tic-Tac-Toe's or Connect Four's — but every field is either
        "what's true for everyone" (`public_state`) or "what only YOU would know"
        (`private_state`). You are never shown the opponent's ship positions — only
        what your own shots have revealed about them over time.

            observation = {
                "public_state": {
                    "phase": "placement",       # "placement" | "battle"
                    "current_player": "...",    # whose turn it is right now
                    "turn_index": 0,            # int >= 0, +1 every move (placement AND battle)
                    "done": False,              # bool — True once the match has ended
                    "winner": "..." | None,     # winner id, or None while the game continues
                },
                "private_state": {
                    # Your own fleet — fully known to you, never redacted.
                    "your_fleet": [
                        {
                            "name": "carrier",          # one of: carrier/battleship/cruiser/submarine/destroyer
                            "length": 5,                # int, cells the ship occupies
                            "cells": [[r, c], ...],     # every [row, col] this ship occupies (0-9, 0-9)
                            "hits": [[r, c], ...],      # which of those cells the opponent has hit so far
                            "sunk": False,              # bool — True once every cell has been hit
                        },
                        ...
                    ],
                    # A 10x10 grid (list of 10 lists of 10 single-char strings) of YOUR
                    # OWN waters — your ships plus every shot the opponent has fired at you:
                    #   "~" empty water (untouched)   "S" your ship, undamaged
                    #   "H" your ship, hit            "X" your ship, hit AND sunk
                    #   "M" opponent fired here and missed (open water)
                    "your_board": [["~", "S", ...], ...],   # 10 rows x 10 cols, row 0 = top
                    # The exact list of shots YOU have fired at the opponent, in order:
                    "your_shots": [
                        {"row": 3, "col": 7, "result": "hit", "ship": None},
                        # "result" is "miss" | "hit" | "sunk".
                        # "ship" is the opponent's ship NAME — but ONLY once you've sunk
                        # it (that's the moment the real game reveals "you sank my
                        # Battleship!"); a plain "hit" never tells you which ship it was.
                        # The instant a ship sinks, every earlier shot of yours that
                        # contributed to it is retroactively relabeled "sunk" with that
                        # ship's name — exactly like suddenly realizing "oh, THOSE four
                        # hits were all the same ship."
                        ...
                    ],
                    # The same shot history as a 10x10 grid for quick "what's at (r, c)"
                    # lookups — same symbols as your_board's damage marks, plus "?" for
                    # "you haven't fired here yet":
                    #   "?" unknown   "M" miss   "H" hit (ship unknown)   "X" hit & sunk
                    "tracking_grid": [["?", "?", ...], ...],  # 10 rows x 10 cols, row 0 = top
                },
                "context": {
                    "opponent_id": "...",       # the other player's id
                    "board_size": 10,           # board is board_size x board_size (constant)
                    "ships": [                  # the fixed fleet every player places, in order
                        {"name": "carrier", "length": 5},
                        {"name": "battleship", "length": 4},
                        {"name": "cruiser", "length": 3},
                        {"name": "submarine", "length": 3},
                        {"name": "destroyer", "length": 2},
                    ],
                    "next_ship_to_place": "carrier" | None,  # set during YOUR placement turns, else None
                },
                "legal_actions": [...],        # see below — shape differs by phase
            }

        **Placement-phase actions** look like:
            {"type": "place_ship", "ship": "carrier", "row": 4, "col": 2, "orientation": "horizontal"}
        `legal_actions` enumerates every in-bounds, non-overlapping placement for
        whichever ship is next in your fleet order (`context.next_ship_to_place`) — you
        place ships one at a time, largest (carrier, 5) to smallest (destroyer, 2).
        `(row, col)` is the ship's FIRST cell; "horizontal" extends it rightward (same
        row, increasing col), "vertical" extends it downward (same col, increasing row).

        **Battle-phase actions** look like:
            {"type": "fire", "row": 3, "col": 7}
        `legal_actions` enumerates every cell on the opponent's board you haven't
        already fired at (an integer `row`/`col`, each `0`-`9`).

        Either way, what you must return is exactly one of the dicts already sitting in
        `observation["legal_actions"]` — that's the only way to guarantee a legal reply.
        Below, rather than making you pick by index from a list of up to 100 entries, we
        ask for plain coordinates and look up the matching legal action for you.
        """
        public_state = observation["public_state"]
        private_state = observation["private_state"]
        legal_actions = observation["legal_actions"]

        if public_state["phase"] == "placement":
            return self._choose_placement(observation, legal_actions)

        print("Your board (your ships + every shot the opponent has fired at you):")
        _print_grid(private_state["your_board"])
        print("Legend: ~ empty water   S ship   H hit   X sunk   M opponent missed here")
        print()
        print("Your tracking grid (results of the shots YOU have fired at the opponent):")
        _print_grid(private_state["tracking_grid"])
        print("Legend: ? unknown   M miss   H hit (ship unknown)   X hit & sunk")
        print()

        while True:
            raw = input("Fire at — enter 'row col' (each 0-9), e.g. '3 7': ").strip().split()
            try:
                row, col = int(raw[0]), int(raw[1])
            except (IndexError, ValueError):
                print("Couldn't parse that as two numbers — try again.")
                continue
            candidate = {"type": "fire", "row": row, "col": col}
            if candidate in legal_actions:
                return candidate
            print("That cell isn't legal (out of range, or you've already fired there) — try again.")

    def _choose_placement(self, observation: Observation, legal_actions: list[Action]) -> Action:
        ship = observation["context"]["next_ship_to_place"]
        length = next(s["length"] for s in observation["context"]["ships"] if s["name"] == ship)
        print(f"Placement phase — place your {ship} (length {length} cells).")
        print("Your board so far (your own ships only — the opponent's fleet stays hidden):")
        _print_grid(observation["private_state"]["your_board"])
        print("Legend: ~ empty water   S your ship")
        print()

        while True:
            raw = (
                input(
                    f"Place the {ship} — enter 'row col orientation' "
                    f"(orientation = h or v, e.g. '4 2 h' for horizontal starting at row 4, col 2): "
                )
                .strip()
                .split()
            )
            if len(raw) != 3:
                print("Expected three values: row, col, orientation — try again.")
                continue
            try:
                row, col = int(raw[0]), int(raw[1])
            except ValueError:
                print("Row and column must be numbers — try again.")
                continue
            orientation = "horizontal" if raw[2].lower().startswith("h") else "vertical"
            candidate = {
                "type": "place_ship",
                "ship": ship,
                "row": row,
                "col": col,
                "orientation": orientation,
            }
            if candidate in legal_actions:
                return candidate
            print("That placement isn't legal (off the board, or overlaps a ship you already placed) — try again.")

