# Player Bot Agent Instructions

Purpose: this file defines the working contract for the agent helping a participant create and run a personal game bot.

This is not infrastructure guidance.
Infrastructure tasks belong to `infrastructure.agent.md`.

## Primary User Journey

When a new participant opens this repo and asks for help, complete this flow end-to-end:

1. Environment setup with uv.
2. Scaffold a personal bot from the example.
3. Make the smallest working bot change.
4. Run the bot versus a baseline.
5. Give the participant the exact command to play or rerun.

## Required Setup Commands

Use uv command style in this repository.

1. `uv python install 3.13`
2. `uv sync --python 3.13`
3. `uv run gamenight list-games`

If setup is already complete, proceed without reinstalling.

## Bot Creation Rules

- One folder equals one selectable bot identity.
- Bot path format: `src/gamenight/games/tictactoe/bots/players/<bot_name>/bot.py`.
- Load name format at runtime: `player:<bot_name>`.
- Required class name: `PlayerBot`.
- Required methods: `reset(context)`, `choose_action(observation, context)`.

## Safe Scaffolding Workflow

1. Create bot folder.
2. Copy from `example_player/bot.py`.
3. Make minimal edits only in the new folder.
4. Do not edit other player folders or baseline bots.

Scaffold command example:

`mkdir -p src/gamenight/games/tictactoe/bots/players/<bot_name> && cp src/gamenight/games/tictactoe/bots/players/example_player/bot.py src/gamenight/games/tictactoe/bots/players/<bot_name>/bot.py`

## Optional: Extra Python Packages Per Bot

If a participant's bot needs a package outside this project's normal dependencies, do
not add it to the shared `pyproject.toml`/lockfile. Instead point them at the
"Optional: Bot-Specific Python Packages" section of `docs/how_to_add_bot.md`:

1. Create `requirements.txt` next to their `bot.py`, one package name per line, **no
   version pins** (assume current/latest).
2. Prefix their run command with `uv run --with-requirements <path-to-requirements.txt>`
   in place of plain `uv run` — e.g.:

   `uv run --with-requirements src/gamenight/games/tictactoe/bots/players/<bot_name>/requirements.txt gamenight run-game --game tictactoe --mode headless --bot-1 player:<bot_name> --bot-2 random`

This keeps each bot's extra dependencies isolated to that one run (uv layers them into a
cached overlay environment) and trivially removable — nothing persists in the shared
project environment, so picking up or dropping a bot's packages is just adding or
omitting the flag.

## Optional: Submitting A Blind Bot

For "submit by the halfway mark, then play everyone else's bot" formats, point a
participant at:

`uv run gamenight encode-bot --game <game> --player <bot_name>`

This compiles their `bot.py` to `bot.pyc`. Tell them to commit `bot.pyc` and remove (or
`.gitignore`) `bot.py` — opponents then load and run it the normal `player:<bot_name>`
way (the loader prefers `bot.py` when present, falls back to `bot.pyc` otherwise), no
extra steps needed on their end. Be upfront that this is a fun "don't spoil the reveal"
mechanic, not real secrecy — `.pyc` is decompilable and keeps identifiers/string literals
intact, so a descriptively-named constant is just as visible as it would be in source.
See "Optional: Submitting A 'Blind' Bot (Encoded)" in `docs/how_to_add_bot.md` for the
full caveats before recommending it as a privacy measure.

## Validation Commands

Headless quick check:

`uv run gamenight run-game --game tictactoe --mode headless --bot-1 player:<bot_name> --bot-2 random --replay-file artifacts/<bot_name>_vs_random.json`

GUI play check:

`uv run gamenight run-game --game tictactoe --mode gui --bot-1 player:<bot_name> --bot-2 random --gui-delay 0.4 --replay-file artifacts/<bot_name>_vs_random_gui.json`

## What To Tell The Participant

Always provide:

1. The created bot folder path.
2. The exact run command they can execute immediately.
3. One next-step suggestion (for example, improve opening move choice).

## Out Of Scope

- Do not redesign core engine or CLI for player-bot requests.
- Do not change shared infrastructure unless explicitly requested.
- Do not read hidden game information not present in BOT_SPEC.