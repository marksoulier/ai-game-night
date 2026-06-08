# Tic-Tac-Toe Bot Spec

This document defines the exact bot interface for Tic-Tac-Toe.

## Bot Class Contract

Implement class `PlayerBot` with methods:

- `reset(context)`
- `choose_action(observation, context)`

## Observation Object

`observation` fields:

- `public_state.board`: list of 9 strings (`"X"`, `"O"`, or `" "`)
- `public_state.current_player`: `"player_x"` or `"player_o"`
- `public_state.turn_index`: integer turn count
- `public_state.done`: bool
- `public_state.winner`: `"player_x"`, `"player_o"`, or `null`
- `private_state.marker`: `"X"` or `"O"`
- `context.opponent_id`: opponent player id
- `context.board_size`: `3`
- `context.win_length`: `3`
- `legal_actions`: list of available actions

## Action Schema

Each legal action has shape:

```json
{"type": "place", "index": 0}
```

`index` is between 0 and 8.

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
uv run gamenight run-game --game tictactoe --mode headless --bot-1 player:<your_bot_name> --bot-2 random
```
