# Prompt: Generate Battleship Greedy Bot

You are writing a Python class for this repository.

Task:

- Create class `PlayerBot` in `bot.py`.
- The class must expose:
  - `__init__(self, bot_id: str)`
  - `reset(self, context)`
  - `choose_action(self, observation, context)`

Rules:

1. Read only from the provided `observation` and `context`.
2. Never use hidden information — there is no field anywhere in `observation` that
   reveals the opponent's ship positions before your own confirmed shots have found
   them. If your strategy seems to need one, that's a sign to rethink the strategy, not
   to go looking for a leak.
3. Return one action from `observation["legal_actions"]`.
4. If your preferred action is not legal, fall back to a legal action.

Battleship has two phases — your bot needs a heuristic for each.

## Placement strategy: spread your fleet out

1. For each candidate placement in `legal_actions`, count how many of its cells would be
   orthogonally *or* diagonally adjacent to a cell your fleet already occupies (an
   "adjacency score").
2. Prefer the placement with the **lowest** adjacency score — i.e., the one that keeps
   your fleet least clustered.
3. Rationale: a tightly clustered fleet means a single string of lucky hits can reveal
   where your *whole* fleet lives; spreading out forces the opponent to search more of
   the board to find each ship independently.

## Targeting strategy: "hunt-and-target"

Maintain a small piece of memory across turns — your set of "pending hits": cells where
you've scored a hit (`tracking_grid[r][c] == "H"`) on a ship that hasn't sunk yet
(once it sinks, those cells flip to `"X"` and drop out of the pending set).

1. **Target mode** (you have pending hits): you know you've found part of a ship —
   press the advantage rather than spreading your search:
   - If two or more pending hits form a contiguous line (all same row with consecutive
     columns, or all same column with consecutive rows), the ship's orientation is
     revealed — fire at one of the two cells that would extend that line, preferring
     whichever end is still a legal target.
   - Otherwise, fire at a cell orthogonally adjacent (up/down/left/right, never
     diagonal — ships are always straight lines) to your most recent pending hit.
2. **Hunt mode** (no pending hits): fire on a checkerboard / parity pattern — only
   cells where `(row + col) % 2 == 0`. Every ship is at least 2 cells long, so a parity
   pattern is *guaranteed* to eventually touch every possible ship placement while
   only requiring you to search roughly half the board. Fall back to any legal cell if
   the parity set is exhausted (it will be, late in the game).

Observation schema summary:

- `observation["public_state"]["phase"]`: `"placement"` or `"battle"` — which heuristic
  to run
- `observation["private_state"]["your_fleet"]`: your own ships, for the placement
  adjacency check (`cells` field)
- `observation["private_state"]["tracking_grid"]`: 10x10 grid of `"?"` / `"M"` / `"H"` /
  `"X"` — your shot history against the opponent, for the hunt-and-target state machine
- `observation["context"]["ships"]`: `{"name": ..., "length": ...}` per ship, to know how
  many cells each candidate placement spans
- `observation["legal_actions"]`: list of `{"type": "place_ship", ...}` during placement,
  or `{"type": "fire", "row": r, "col": c}` during battle — only ever legal actions

Implementation notes:

- Reset your pending-hits memory in `reset(context)` — a fresh match means a fresh board.
- A ship is always a straight horizontal or vertical line — never diagonal, never
  bent — so "extend the revealed line" only ever needs to check the two endpoints.
- Don't assume your memory of "pending hits" matches `tracking_grid` exactly forever —
  recompute it from `tracking_grid` each turn (drop cells that have flipped to `"X"`,
  add any new `"H"` cells) rather than trusting incremental updates, since a sunk ship
  can clear several pending hits at once.

Output:

- Return valid Python code only.
