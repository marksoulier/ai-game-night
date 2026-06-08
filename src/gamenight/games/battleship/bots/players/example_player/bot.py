from __future__ import annotations

from gamenight.core.types import Action, MatchContext, Observation


class PlayerBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        """Decide what to play this turn — replace this with your own strategy.

        `observation` is typed as a plain dict because every game has a different shape
        (that's all your editor can tell you). Battleship has **two phases** and
        **hidden information**, so its shape is bigger than Connect Four's — but the
        same three-part split applies: `public_state` (what's true for everyone),
        `private_state` (what only YOU would know), and `context` (fixed facts about
        the match). The full field-by-field reference lives in ../../../BOT_SPEC.md,
        with a complete worked example in ../../../EXAMPLES.md — this docstring is the
        "show me in the code, right where I'm reading and writing it" version:

            observation = {
                "public_state": {
                    "phase": "placement",       # "placement" | "battle"
                    "current_player": "...",    # whose turn it is right now
                    "turn_index": 0,            # int >= 0, +1 every move (either phase)
                    "done": False,              # bool — True once the match has ended
                    "winner": "..." | None,     # winner id, or None while still going
                },
                "private_state": {
                    # Your own fleet — fully known to you, never redacted.
                    "your_fleet": [
                        {
                            "name": "carrier",          # carrier/battleship/cruiser/submarine/destroyer
                            "length": 5,                # int, cells the ship occupies
                            "cells": [[r, c], ...],     # every [row, col] this ship occupies (0-9, 0-9)
                            "hits": [[r, c], ...],      # which of those cells the opponent has hit
                            "sunk": False,              # bool — True once every cell has been hit
                        },
                        ...
                    ],
                    # Your own 10x10 waters: your ships + every shot fired AT you.
                    #   "~" empty water   "S" your ship   "H" your ship, hit
                    #   "X" your ship, hit AND sunk   "M" opponent fired here, missed
                    "your_board": [["~", "S", ...], ...],   # 10 rows x 10 cols, row 0 = top
                    # The shots YOU have fired at the opponent, in order:
                    "your_shots": [
                        {"row": 3, "col": 7, "result": "hit", "ship": None},
                        # "result" is "miss" | "hit" | "sunk". "ship" is the opponent's
                        # ship NAME, but ONLY once you've sunk it — a plain "hit" never
                        # tells you which ship it was. The instant a ship sinks, every
                        # earlier shot of yours that contributed to it is retroactively
                        # relabeled "sunk" with that ship's name.
                        ...
                    ],
                    # The same shot history as a 10x10 grid for quick lookups:
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
                    "next_ship_to_place": "carrier" | None,  # set during YOUR placement turns
                },
                "legal_actions": [...],   # shape differs by phase, see below
            }

        **Placement-phase actions** look like:
            {"type": "place_ship", "ship": "carrier", "row": 4, "col": 2, "orientation": "horizontal"}
        `legal_actions` enumerates every in-bounds, non-overlapping placement for
        whichever ship is next in your fleet order (`context.next_ship_to_place`) —
        largest (carrier, 5) to smallest (destroyer, 2), one at a time. `(row, col)` is
        the ship's first cell; "horizontal" extends rightward, "vertical" downward.

        **Battle-phase actions** look like:
            {"type": "fire", "row": 3, "col": 7}
        `legal_actions` enumerates every cell on the opponent's board you haven't
        already fired at.

        What you must return: exactly one of the dicts already sitting in
        `observation["legal_actions"]`. Anything else (wrong shape, an out-of-bounds or
        overlapping placement, a cell you've already fired at) is rejected by the engine.

        A reasonable first upgrade from "always play legal_actions[0]" (which places
        every ship in the same top-left corner and fires in a fixed left-to-right sweep
        — easy to predict and exactly the kind of clustering that hands an opponent your
        whole fleet once they land one hit): once you're in "battle" and `tracking_grid`
        shows an "H" you haven't sunk yet, fire at one of its orthogonal neighbors rather
        than continuing your sweep — see bots/baselines/greedy_bot.py for a fuller
        hunt-and-target implementation (checkerboard hunting + line-narrowing) plus a
        "spread your fleet out" placement heuristic.
        """
        return observation["legal_actions"][0]
