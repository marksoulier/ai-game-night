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
uv run gamenight run-game --game tictactoe --mode headless --bot-1 random --bot-2 random --replay-file artifacts/random_vs_random.json
```

2. Replay the random match:

```bash
uv run gamenight replay --replay-file artifacts/random_vs_random.json
```

3. Run human vs random (you play as X):

```bash
uv run gamenight run-game --game tictactoe --mode headless --bot-1 human --bot-2 random --replay-file artifacts/human_vs_random.json
```

3b. Run human vs random with live GUI board:

```bash
uv run gamenight run-game --game tictactoe --mode gui --bot-1 human --bot-2 random --gui-delay 0.4 --replay-file artifacts/human_vs_random_gui.json
```

This mode shows a live Tic-Tac-Toe window while you still choose moves in terminal prompts.

4. Create your own bot folder from the example:

```bash
mkdir -p src/gamenight/games/tictactoe/bots/players/<your_name>
cp src/gamenight/games/tictactoe/bots/players/example_player/bot.py src/gamenight/games/tictactoe/bots/players/<your_name>/bot.py
```

5. Run your bot against random:

```bash
uv run gamenight run-game --game tictactoe --mode headless --bot-1 player:<your_name> --bot-2 random --replay-file artifacts/<your_name>_vs_random.json
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

## Battleship Spectator GUI

Battleship's GUI is a "TV broadcast" view: both fleets are fully revealed side by side
(spectator-only — neither bot ever sees this). Each board shows, in order:

- the bot's name on top (whatever you passed for `--bot-1`/`--bot-2`/`--bot-a`/`--bot-b`,
  e.g. `greedy` or `player:mark`),
- the live board itself,
- a `Wins: N   Losses: N` line underneath that player's board.

### Single game

```bash
uv run gamenight run-game --game battleship --mode gui --bot-1 greedy --bot-2 random --gui-delay 0.4 --replay-file artifacts/battleship_gui.json
```

Plays one game with the live board. When it finishes, the winner's board shows
`Wins: 1  Losses: 0` and the loser's shows `Wins: 0  Losses: 1` (both show `0-0` if the
match hits the turn limit with no winner). Close the window to return to the terminal.

### Series (live replay of many games)

```bash
uv run gamenight run-series --game battleship --bot-a greedy --bot-b random --games 5 --starting-policy alternate --mode gui --gui-delay 0.2 --summary-file artifacts/battleship_series.json
```

Runs the whole series in one window: each game plays out live, and after each game the
`Wins`/`Losses` line under each board updates to the running total for whichever bot is
currently on that side (bots swap sides as the starting player alternates, so the name
above each board updates too). Use a small `--gui-delay` (or `0`) for longer series —
GUI mode plays every turn of every game live, so it's best for double-digit `--games`
counts, not the hundreds/thousands you'd use for `--mode headless` stat-gathering.

`run-bracket` (below) does not currently have a GUI mode — it runs headless and writes
replay files you can review afterwards with `gamenight replay`.

## Final Bracket (Game Night Wrap-Up)

`run-bracket` runs a single-elimination bracket between any set of bots, with each
matchup decided by a short series of games. It writes a replay file for every game
played plus a `bracket_summary.json` describing the whole bracket — built for the
"play the AI video / show the stats" finale at the end of game night.

```bash
uv run gamenight run-bracket --game battleship \
  --bots greedy,random,player:mark,player:alice \
  --games-per-match 3 \
  --output-dir artifacts/bracket
```

- `--bots`: comma-separated list of entrants, in seed order. Use `greedy`, `random`,
  `human`, or `player:<folder_name>` for each one (same names as `--bot-1`/`--bot-2`).
  Names must be unique, so don't enter the same baseline (e.g. `greedy`) twice.
- `--games-per-match`: how many games each pairing plays. Bots alternate who goes
  first each game.
- `--seed`: optional base seed for reproducible matches.
- `--output-dir`: where replay files and `bracket_summary.json` are written.

Bracket pairing is sequential (1v2, 3v4, ...); if the entrant count is odd, the last
entrant in each round gets a bye. The series winner is whichever bot wins more games;
ties are broken by total points (battleship only — see below) and finally by bracket
order.

The CLI prints the bracket as it completes, e.g.:

```
Bracket: battleship  |  games per match: 3
Entrants: greedy, random, player:mark, player:alice

-- Round 1 --
  greedy vs random: 2-1 -> winner greedy
  player:mark vs player:alice: 2-1 -> winner player:mark

-- Round 2 --
  greedy vs player:mark: 1-1 -> winner greedy (tiebreak: points, points 24-19)

Champion: greedy
```

### Battleship Points

Battleship now tracks **points** alongside wins: a player's points are the number of
their own ship cells that have *not* been hit (out of 17 total across the fleet). This
is exposed in `observe()`'s `public_state.points` and shown in `render_text` /
`bracket_summary.json`, and is used by `run-bracket` as a tiebreaker when a series ends
with equal wins — the bot that took less damage overall wins the tiebreak.

## Replaying Matches

Every `run-game`, `run-bracket`, etc. writes a JSON replay file (a list of per-turn
events: state, action, rewards). Replay it as readable text with:

```bash
uv run gamenight replay --replay-file artifacts/latest_replay.json
```

- `--rows N` limits how many turns are printed (default 30).
- For a bracket, each game's replay is saved under `--output-dir` as
  `round{R}_match{M}_{bot_a}_vs_{bot_b}_game{N}.json` — replay any of them the same way:

```bash
uv run gamenight replay --replay-file artifacts/bracket/round1_match1_greedy_vs_random_game1.json
```

To watch a match visually instead of as text, re-run it in GUI mode (this plays a new
game rather than replaying the saved file, since the GUI viewer drives `run-game`
directly):

```bash
uv run gamenight run-game --game battleship --mode gui --bot-1 greedy --bot-2 random --gui-delay 0.4
```

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