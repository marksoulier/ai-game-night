# Prompt: Generate Mine Duel Greedy Bot

You are writing a Python class for this repository.

Task:

- Create class `PlayerBot` in `bot.py`.
- The class must expose:
  - `__init__(self, bot_id: str)`
  - `reset(self, context)`
  - `choose_action(self, observation, context)`

Rules:

1. Read only from the provided `observation` and `context`.
2. There is no hidden information to exploit here — `observation["private_state"]` is
   always `{}` because neither player knows the mine layout any better than the other
   (see `../../BOT_SPEC.md`'s Information Policy). If a strategy idea seems to need a
   field that isn't in `public_state`/`context`, it doesn't exist.
3. Return one action from `observation["legal_actions"]`.
4. If your preferred action is not legal, fall back to a legal action.

## The core idea: deduce, then estimate risk

Every action is `{"type": "reveal", "row": r, "col": c}`. Two things determine how
good a reveal is: whether it's a mine (costs you `context["mine_penalty"]` points and
ends your turn), and whether it's a `0` that cascades into a big multi-cell bonus.
You can't predict cascades in advance, but you *can* avoid mines using the revealed
numbers already on the board.

### Step 1: find provably safe cells

For every revealed numbered cell on `observation["public_state"]["board"]` (a value
`"1"`-`"8"`, not `"?"` or `"M"`):

1. Look at its 8 neighbors (bounds-check against `context["rows"]`/`context["cols"]`).
2. Count how many neighbors are already revealed mines (`"M"` on the board) — call
   this `confirmed_mines`. Mines are public once triggered, by either player, so this
   includes mines your opponent found too.
3. Count the neighbors that are still hidden (`"?"`) — call this `hidden_neighbors`.
4. If `int(clue) - confirmed_mines == 0`, every one of those hidden neighbors is
   **guaranteed safe** — none of the clue's mines are still unaccounted for among
   them.

Collect every guaranteed-safe cell this way across the whole board. If you found any,
reveal one of them (any tie-break is fine — e.g. lowest `(row, col)`).

### Step 2: no safe cell found — pick the lowest-risk one

If step 1 found nothing, estimate a mine-probability for every hidden cell:

- For a hidden cell adjacent to one or more revealed numbered clues, its risk is the
  **worst** (highest) of `(int(clue) - confirmed_mines) / hidden_neighbors` over each
  clue that touches it — i.e. how many of that clue's remaining mines could still be
  this cell, out of how many hidden cells are competing for them.
- For a hidden cell with no revealed neighbor at all (nothing constrains it yet), fall
  back to the board's overall remaining mine density: `(mine_count - mines_already_
  revealed) / hidden_cells_remaining`.

Reveal the hidden cell with the lowest estimated risk.

## Why this is "greedy," not optimal

Step 1's single-constraint check is 100% correct whenever it fires, but it doesn't
combine multiple overlapping clues the way a full constraint solver would (some boards
have cells that are provably safe only by reasoning about *several* clues at once —
this bot won't find those). Step 2's risk estimate is a genuine heuristic, not a
probability solver. That's intentional and matches this repo's other GreedyBots:
"clearly better than random," not optimal — see `../../README.md`'s "Is Mine Duel
Solved?" section for why a from-scratch optimal solver isn't a realistic target
anyway.

Observation schema summary:

- `observation["public_state"]["board"]`: `rows` x `cols` grid (18x14 by default),
  `"?"` hidden / `"0"`-`"8"` revealed safe / `"M"` revealed mine
- `observation["context"]["rows"]`, `["cols"]`, `["mine_count"]`,
  `["mine_penalty"]`: fixed match constants
