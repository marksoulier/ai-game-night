# Battleship Examples

Two complete worked examples — one from the placement phase, one from the battle phase
— since Battleship's `observation` shape shifts between the two (and hidden information
means what you'd see depends on *which player* you are).

## Example 1: Placement-Phase Observation

`player_blue` has placed their carrier and battleship; the cruiser is next.

```json
{
  "public_state": {
    "phase": "placement",
    "current_player": "player_blue",
    "turn_index": 2,
    "done": false,
    "winner": null
  },
  "private_state": {
    "your_fleet": [
      {"name": "carrier",    "length": 5, "cells": [[0,0],[0,1],[0,2],[0,3],[0,4]], "hits": [], "sunk": false},
      {"name": "battleship", "length": 4, "cells": [[1,0],[1,1],[1,2],[1,3]],       "hits": [], "sunk": false}
    ],
    "your_board": [
      ["S","S","S","S","S","~","~","~","~","~"],
      ["S","S","S","S","~","~","~","~","~","~"],
      ["~","~","~","~","~","~","~","~","~","~"],
      ["~","~","~","~","~","~","~","~","~","~"],
      ["~","~","~","~","~","~","~","~","~","~"],
      ["~","~","~","~","~","~","~","~","~","~"],
      ["~","~","~","~","~","~","~","~","~","~"],
      ["~","~","~","~","~","~","~","~","~","~"],
      ["~","~","~","~","~","~","~","~","~","~"],
      ["~","~","~","~","~","~","~","~","~","~"]
    ],
    "your_shots": [],
    "tracking_grid": [
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"]
    ]
  },
  "context": {
    "opponent_id": "player_orange",
    "board_size": 10,
    "ships": [
      {"name": "carrier", "length": 5},
      {"name": "battleship", "length": 4},
      {"name": "cruiser", "length": 3},
      {"name": "submarine", "length": 3},
      {"name": "destroyer", "length": 2}
    ],
    "next_ship_to_place": "cruiser"
  },
  "legal_actions": [
    {"type": "place_ship", "ship": "cruiser", "row": 0, "col": 5, "orientation": "horizontal"},
    {"type": "place_ship", "ship": "cruiser", "row": 0, "col": 6, "orientation": "horizontal"},
    {"type": "place_ship", "ship": "cruiser", "row": 2, "col": 0, "orientation": "horizontal"},
    "... every other in-bounds, non-overlapping placement for a length-3 ship ..."
  ]
}
```

Notice `your_fleet` and `your_board` already show the carrier and battleship placed —
`tracking_grid` is still all `"?"` because the battle phase (and therefore firing)
hasn't started yet, and `next_ship_to_place` tells you exactly which ship `legal_actions`
is enumerating placements for.

### Example Placement Action

```json
{"type": "place_ship", "ship": "cruiser", "row": 2, "col": 0, "orientation": "horizontal"}
```

Lays the cruiser (length 3) starting at `(2, 0)` extending right to `(2, 1)`, `(2, 2)` —
clear of the carrier (row 0) and battleship (row 1) above it.

## Example 2: Battle-Phase Observation (mid-game, from `player_blue`'s seat)

`player_blue` has been hunting `player_orange`'s carrier: two hits in a row at `(3, 4)`
and `(3, 5)` reveal it's lying horizontally, and the next shot — at `(3, 6)` — is about
to sink it.

```json
{
  "public_state": {
    "phase": "battle",
    "current_player": "player_blue",
    "turn_index": 19,
    "done": false,
    "winner": null
  },
  "private_state": {
    "your_fleet": [
      "... your own 5 ships, fully visible to you, each with its own hits/sunk status ..."
    ],
    "your_board": [
      "... your own 10x10 grid: your ships, plus M for every shot orange has fired at you ..."
    ],
    "your_shots": [
      {"row": 3, "col": 4, "result": "hit",  "ship": null},
      {"row": 3, "col": 5, "result": "hit",  "ship": null},
      {"row": 7, "col": 1, "result": "miss", "ship": null},
      "... 16 more shots ..."
    ],
    "tracking_grid": [
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","H","H","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","M","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?"]
    ]
  },
  "context": {
    "opponent_id": "player_orange",
    "board_size": 10,
    "ships": [
      {"name": "carrier", "length": 5},
      {"name": "battleship", "length": 4},
      {"name": "cruiser", "length": 3},
      {"name": "submarine", "length": 3},
      {"name": "destroyer", "length": 2}
    ],
    "next_ship_to_place": null
  },
  "legal_actions": [
    {"type": "fire", "row": 0, "col": 0},
    {"type": "fire", "row": 0, "col": 1},
    {"type": "fire", "row": 3, "col": 6},
    "... every other cell player_blue hasn't already fired at ..."
  ]
}
```

Notice two things hidden information makes possible here: `your_shots[0]` and `[1]` both
show `"result": "hit"` with `"ship": null` — `player_blue` knows they've struck *something*
twice in a row at `(3,4)` and `(3,5)`, but not *which* ship, exactly like a real player
squinting at their tracking sheet. And nothing in this observation — not `your_fleet`,
not `tracking_grid`, not any nested field — reveals where `player_orange`'s carrier
*actually* sits beyond those two confirmed hit cells. `(3, 6)` is a guess based on the
revealed line, not a known fact.

### Example Battle Action — and the "sunk" reveal that follows it

```json
{"type": "fire", "row": 3, "col": 6}
```

Suppose this shot lands on the carrier's last unhit cell. The very next time
`player_blue` observes, `your_shots` looks like this:

```json
"your_shots": [
  {"row": 3, "col": 4, "result": "sunk", "ship": "carrier"},
  {"row": 3, "col": 5, "result": "sunk", "ship": "carrier"},
  {"row": 7, "col": 1, "result": "miss", "ship": null},
  "... 16 more shots ...",
  {"row": 3, "col": 6, "result": "sunk", "ship": "carrier"}
]
```

All three shots that contributed to the carrier are now labeled `"sunk"` with the ship's
name — including the two *earlier* ones that were `"hit"` with `"ship": null` a moment
ago. That's the retroactive reveal: the instant a ship goes down, every shot that found
it gets relabeled all at once, the same "oh, THOSE were all the carrier!" realization a
human player gets when the announcement lands.
