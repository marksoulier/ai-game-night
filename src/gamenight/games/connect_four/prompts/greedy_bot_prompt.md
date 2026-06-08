# Prompt: Generate Connect Four Greedy Bot

You are writing a Python class for this repository.

Task:

- Create class `PlayerBot` in `bot.py`.
- The class must expose:
  - `__init__(self, bot_id: str)`
  - `reset(self, context)`
  - `choose_action(self, observation, context)`

Rules:

1. Read only from the provided `observation` and `context`.
2. Never use hidden information.
3. Return one action from `observation["legal_actions"]`.
4. If your preferred action is not legal, fall back to a legal action.

Greedy strategy requirements:

1. If dropping in some open column completes 4 of your discs in a row (horizontally,
   vertically, or on either diagonal), play that column.
2. Else if the opponent could complete 4 in a row by dropping in some open column on
   their next turn, play that column to deny it to them.
3. Else prefer columns center-out: column `3`, then `2`, then `4`, then `1`, then `5`,
   then `0`, then `6`.

Observation schema summary:

- `observation["public_state"]["board"]`: flat list of 42 cells (`"R"`, `"Y"`, or `" "`),
  indexed `row * 7 + col` with row `0` at the top and row `5` at the bottom
- `observation["private_state"]["marker"]`: your disc color (`R` or `Y`)
- `observation["legal_actions"]`: list of actions shaped like `{"type": "drop", "column": c}`
  — only columns that aren't full appear here

Implementation notes:

- A disc dropped into column `c` lands on the lowest empty row in that column (gravity) —
  to simulate "what if I drop here," find the lowest empty row yourself rather than
  assuming row `5`.
- Check all four directions from the landing cell: horizontal, vertical, and both
  diagonals (`\` and `/`). It's easy to implement one diagonal and forget its mirror.

Output:

- Return valid Python code only.
