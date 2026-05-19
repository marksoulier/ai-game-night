# AI Game Night

Modular Python framework for running board, card, and dice game tournaments where players build bots quickly with LLM help.

## Goals

- Keep games isolated from each other.
- Keep shared infrastructure reusable across games.
- Make bot interfaces simple enough for one-prompt generation.
- Support human, random, greedy, and player bots.
- Run headless tournaments, optional GUI play, and replay mode.

## Quick Start

1. Install uv.
2. Install the latest Python with uv (example: 3.13):

```bash
uv python install 3.13
```

3. Sync dependencies with that Python:

```bash
uv sync --python 3.13
```

4. List available games:

```bash
uv run gamenight list-games
```

5. Run a headless sample match:

```bash
uv run gamenight run-game --game tictactoe --mode headless
```

6. Replay the match:

```bash
uv run gamenight replay --replay-file artifacts/latest_replay.json
```

## Player Demo

1. Run random vs random:

```bash
uv run gamenight run-game --game tictactoe --mode headless --bot-x random --bot-o random --replay-file artifacts/random_vs_random.json
```

2. Replay the random match:

```bash
uv run gamenight replay --replay-file artifacts/random_vs_random.json
```

3. Run human vs random (you play as X):

```bash
uv run gamenight run-game --game tictactoe --mode headless --bot-x human --bot-o random --replay-file artifacts/human_vs_random.json
```

3b. Run human vs random with live GUI board:

```bash
uv run gamenight run-game --game tictactoe --mode gui --bot-x human --bot-o random --gui-delay 0.4 --replay-file artifacts/human_vs_random_gui.json
```

This mode shows a live Tic-Tac-Toe window while you still choose moves in terminal prompts.

4. Create your own bot folder from the example:

```bash
mkdir -p src/gamenight/games/tictactoe/bots/players/<your_name>
cp src/gamenight/games/tictactoe/bots/players/example_player/bot.py src/gamenight/games/tictactoe/bots/players/<your_name>/bot.py
```

5. Run your bot against random:

```bash
uv run gamenight run-game --game tictactoe --mode headless --bot-x player:<your_name> --bot-o random --replay-file artifacts/<your_name>_vs_random.json
```

## Large Series With Configurable First Player

Run many games between two bots and control who starts:

```bash
uv run gamenight run-series --game tictactoe --bot-a player:mark --bot-b random --games 1000 --starting-policy random --order-seed 20260518 --order-key mark-vs-random-season1 --summary-file artifacts/mark_vs_random_series.json
```

`run-series` supports:

- `--starting-policy fixed-a`
- `--starting-policy fixed-b`
- `--starting-policy alternate`
- `--starting-policy random`

Use `--order-seed` and `--order-key` together to get reproducible but uniquely configured randomized first-player order.

## Repository Layout

- `src/gamenight/core`: Shared contracts and engine infrastructure.
- `src/gamenight/games`: Game modules. Each game has its own bots and prompts.
- `docs`: Framework and contribution docs.
- `scripts`: Event-level script entry points.
- `artifacts`: Match outputs, statistics, and replay files.

Game spotlight page:

- `src/gamenight/games/tictactoe/README.md`

## Player Workflow

1. Create branch: `player/<name>`.
2. Pick a game.
3. Create a folder under `games/<game>/bots/players/<name>`.
4. Add your bot implementation.
5. Submit PR.

See `docs/git_flow_for_players.md` and each game's `BOT_SPEC.md`.

## Agent Instruction Split

- Infrastructure/framework agent instructions: `infrastructure.agent.md`
- Player bot helper agent instructions: `player.agent.md`
- Player bot implementation instructions: each game's `BOT_SPEC.md`

Use infrastructure instructions for core engine, CLI, tournament, replay, and extension-point work.
Use player agent instructions for setup/scaffold/run help for participants.
Use BOT_SPEC files when implementing or updating a game bot.