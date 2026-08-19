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

### Tournament Mode (Round Robin + Seeded Bracket)

`run-tournament` runs a full event in one command: shuffle the entrants, play a round
robin (every entrant plays every other entrant once), seed a single-elimination bracket
from the round-robin standings (best vs. worst, cross-paired so 1v4/2v3 rather than
1v2/3v4), then run that bracket. It writes `tournament_summary.json` (round-robin
standings + results, bracket rounds, overall standings, champion) plus every game's
replay file.

```bash
uv run gamenight run-tournament --game splendor \
  --bots greedy,random,player:mark,player:alice \
  --round-robin-games 1 --bracket-games 3 \
  --output-dir artifacts/tournament
```

Entrant count is unconstrained — 2 is a valid (if short) tournament, and there's no
upper bound; the bracket phase byes an odd one out per round exactly like `run-bracket`
does on its own. This works for any game with a `GameProtocol` implementation, not just
Splendor.

### Bracket Reveal GUI

`replay-bracket-gui` turns a saved `bracket_summary.json` or `tournament_summary.json`
(from `run-bracket` or `run-tournament`) into a live "reveal" window: the full bracket
tree with later rounds blank, a "Play Next Match" button that replays each match's saved
games on an embedded board (first game slow, the rest fast), and the winner propagating
into the next round until a champion is crowned. If a `tournament_summary.json` is
present, round-robin standings and a live-updating overall-standings table are shown
alongside the tree.

```bash
uv run gamenight replay-bracket-gui --game splendor --bracket-dir artifacts/tournament
```

- `--final` skips the reveal animation and shows the completed bracket immediately
  (useful for re-opening a bracket you've already revealed once).
- `--first-game-delay` / `--rest-delay` control playback speed (a match's first game
  plays slow enough to follow, the rest play fast).

This is currently implemented per-game (`games/<game>/bracket_gui.py`) rather than
generically, the same way each game gets its own `gui.py` — Battleship and Splendor both
have one; a new game needs its own before `replay-bracket-gui --game <new_game>` works
(it errors clearly, naming the game, if one isn't registered yet).

### Checking Bot Speed (Admin)

`check-bot-speed` times every submitted player bot's `choose_action` calls, one bot at a
time (playing headless games against fast `--opponent` baselines filling every other
seat), and warns about anyone slower than a threshold — run this before a live
tournament, where one slow bot stalls the whole room waiting on it every time it's up.

```bash
uv run gamenight check-bot-speed --game splendor --games 3 --threshold 0.5
```

```
Checking 7 bot(s) for 'battleship': example_player, goob, jayse, josh, mark, phil, tanner
(2 game(s) each, vs 'random' filling other seats, threshold 0.5s/action)

  player:example_player       actions=176  mean=    0.0ms  max=    0.0ms  [ok]
  player:phil                 actions=116  mean=  822.5ms  max=  900.1ms  [SLOW]
    WARNING: player:phil took 0.90s on its slowest action (> 0.50s threshold) -- too slow for a live tournament.
  ...

Result: one or more bots need attention before the tournament (see WARNINGs above).
```

- `--games`: more games means more sampled actions (and more confidence an occasional
  slow call — e.g. first-call import overhead — isn't a fluke either way).
- `--opponent`: kept to a fast baseline (`random` by default) on purpose — a `greedy` or
  `human` opponent would add its own thinking time to the loop and make it unclear whose
  slowness you're looking at. Only the bot-under-test's `choose_action` calls are timed.
- `--only name1,name2`: check specific bots instead of everyone under `bots/players/`.
- Also flags any bot that raises an exception mid-action (the match engine's normal
  fallback-to-`legal_actions[0]` behavior masks this in a real match — this surfaces it
  explicitly instead of letting a broken bot look merely "fine" all game).
- Exits with status `1` if anything was flagged, `0` if every bot is clean — usable in a
  pre-tournament checklist/script, not just read by eye.
- Works for any game with player bots, not just Splendor: `--game battleship`,
  `--game connect_four`, etc.
- A thin `scripts/check_bot_speed.py` wrapper exists too, matching `scripts/run_game.py`'s
  pattern, for running it directly with `uv run python scripts/check_bot_speed.py ...`.

## Splendor

Splendor is a shared-market engine-builder: no hidden fleets, almost no hidden
information at all (see `games/splendor/README.md`'s Information Policy) — the only
thing redacted (from bots -- the GUI shows it openly) is which cards a player has
reserved. Its GUI seats players around the table (you at the bottom, opponents fanned
around the rest, 2-4 of them) with the market/bank/nobles shared in the center, each
mat showing points, owned cards as color-coded stacks, tokens, and reserved cards in
full — and scrolls/pans rather than clipping once that's a lot of board to show.

```bash
uv run gamenight run-game --game splendor --mode gui --bots greedy,random,player:mark --gui-delay 0.4 --replay-file artifacts/splendor_gui.json
```

Splendor tracks **points** (prestige points, same field name real Splendor uses) the
same way Battleship tracks remaining ship cells — exposed via `remaining_points()`, used
by `run-bracket`/`run-series` as a tiebreaker when a series ends with equal wins.

This repo's `SplendorGame` supports 2-4 players (`SplendorGame(num_players=N)`,
`player_ids = ["player_1", ..., "player_N"]`) — use `--bots name1,name2,name3` on
`run-game` for 3-4 players instead of `--bot-1`/`--bot-2`. See
`games/splendor/README.md`'s Player Count section for the infrastructure behind this
(a factory-based `GameRegistry`) and what's still 2-competitor-only (`run-series`,
`run-bracket`, `run-tournament`).

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
- `src/gamenight/games/mine_duel/README.md`

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