# How To Add A Bot

Choose a game, then add your bot in that game's player folder namespace.

Example location:

- `src/gamenight/games/tictactoe/bots/players/<your_name>/bot.py`

Your class must be named `PlayerBot` and implement:

- `reset(context)`
- `choose_action(observation, context)`

Your bot should only use fields described in that game's `BOT_SPEC.md`.

## Allowed Scope

Allowed:

- `src/gamenight/games/<game>/bots/players/<your_bot_name>/bot.py`

Do not modify:

- Other player bot folders
- `src/gamenight/games/<game>/bots/baselines/`
- Shared infrastructure in `src/gamenight/core` unless explicitly asked

## Multiple Bots Per Player

One folder is one bot identity.
If you want multiple versions, create multiple folders.

Examples:

- `players/mark` (run as `player:mark`)
- `players/mark_v2` (run as `player:mark_v2`)
- `players/mark_experiment_a` (run as `player:mark_experiment_a`)

## Run Commands (uv)

Use uv commands in this repository.

```bash
uv run gamenight run-game --game tictactoe --mode headless --bot-x player:<your_bot_name> --bot-o random
```
