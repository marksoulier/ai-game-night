# Connect Four Bot Spec

This document defines the exact bot interface for Connect Four.

## Bot Class Contract

Implement class `PlayerBot` with methods:

- `reset(context)`
- `choose_action(observation, context)`

## Observation Object

`observation` fields:

- `public_state.board`: list of 42 strings (`"R"`, `"Y"`, or `" "`), indexed `row * 7 + col` with row `0` at the top and row `5` at the bottom
- `public_state.current_player`: `"player_red"` or `"player_yellow"`
- `public_state.turn_index`: integer turn count
- `public_state.done`: bool
- `public_state.winner`: `"player_red"`, `"player_yellow"`, or `null`
- `private_state.marker`: `"R"` or `"Y"`
- `context.opponent_id`: opponent player id
- `context.columns`: `7`
- `context.rows`: `6`
- `context.win_length`: `4`
- `legal_actions`: list of currently droppable columns (full columns are never included)

## Action Schema

Each legal action has shape:

```json
{"type": "drop", "column": 3}
```

`column` is between `0` and `6`. Gravity decides the landing row for you — you cannot
target a specific cell.

## Context Object

`context` includes:

- `game_id`
- `seed`
- `player_ids`
- `max_turns`

## Bot Author Rules

Do:

- Read only fields in this spec.
- Return one of the provided legal actions.
- Keep implementation inside your own player folder.

Do not:

- Read hidden/off-spec information.
- Edit baseline bots or other players' folders.
- Change shared core infrastructure for player-bot tasks.

## FAQ

### Can I create more than one bot?

Yes. One folder equals one bot identity.

For example:

- `players/alex/bot.py` -> `player:alex`
- `players/alex_v2/bot.py` -> `player:alex_v2`

### How do I run my bot?

Use uv command style:

```bash
uv run gamenight run-game --game connect_four --mode headless --bot-1 player:<your_bot_name> --bot-2 random
```

## Verifying A New Implementation (For Game Authors)

If you're modifying `game.py` (not just writing a player bot), don't rely on a handful of
headless matches to convince yourself the rules are right — board games like this hide
bugs in rarely-hit corners. Before calling an implementation done, exercise these edge
cases directly against the engine (`create_initial_state` / `step` / `legal_actions` /
the internal `_winner` helper):

- **Wins in every direction**: horizontal, vertical, and *both* diagonal orientations
  (`\` down-right and `/` down-left). It's easy to get one diagonal direction right and
  silently miss the other.
- **Gravity / stacking**: a disc must land on top of whatever is already in its column,
  not at a fixed row — verify two consecutive drops into the same column stack correctly.
- **Column-full legality**: once a column reaches the top, it must disappear from
  `legal_actions`, and attempting to drop into it should not silently corrupt state.
- **Draw detection**: a full board with *no* four-in-a-row must be reported as a draw
  (`done=True, winner=None`), not as a win for whoever happened to move last. This is the
  easiest case to get subtly wrong — a "draw" fixture you hand-build can easily contain an
  accidental four-in-a-row (diagonals are the usual culprit), so verify your fixture has
  `winner is None` *before* trusting it as a regression test.
- **Win-on-the-last-move precedence**: when the winning move also happens to fill the
  final empty cell, the result must be a win for the mover, not a draw — confirm the
  winner check runs before (or takes precedence over) the board-full check.
- **Terminal-state idempotency**: calling `step` again on an already-`done` state should
  be a safe no-op (return the same state, `done=True`), so a runner that calls it once too
  many times can't corrupt the result.

These exact checks (with passing fixtures) were run against this implementation during
development — see the game's test notes for the specific scenarios and results.
