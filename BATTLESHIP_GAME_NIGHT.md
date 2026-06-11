# Battleship Game Night

Welcome! Tonight you'll write a Battleship-playing bot in Python (with LLM help), merge
it in secret, get one round of improvements in, and then watch a final bracket decide
the winner. This doc has everything you need: the rules, the code shapes, your git
workflow, and the schedule for the night.

---

## 1. The Game (Quick Rules Refresher)

Battleship is a two-player, hidden-information game played on two 10x10 grids.

- Each side secretly places a fleet of **5 ships**: carrier (5 cells), battleship (4),
  cruiser (3), submarine (3), destroyer (2) — largest to smallest, one at a time, each
  placed horizontally or vertically. Ships can't overlap or hang off the board.
- Once both fleets are placed, players take turns firing **one shot per turn** at a
  cell on the opponent's grid — no bonus turn for a hit, just like the physical game.
- Each shot is a **miss** (open water), a **hit** (lands on an unsunk ship), or a
  **sunk** (that was the ship's last unhit cell — and the moment it sinks, every one
  of your earlier shots that hit it gets retroactively labeled with that ship's name,
  the classic "you sank my Battleship!" reveal).
- First player to sink all 5 of the opponent's ships wins. There's no draw in a
  finished game — somebody's whole fleet always eventually goes under.

### This Game Night's Setup

- Board: **10x10**, fixed fleet of 5 ships (carrier/battleship/cruiser/submarine/
  destroyer) as above — this is not configurable per bot.
- Two seats: `player_blue` and `player_orange`. `player_blue` places their full fleet
  first, then `player_orange` places theirs, then `player_blue` fires first.
- **Your bot controls both phases** — placement *and* battle. There's no separate
  "setup screen"; where you put your ships is itself a strategic decision your code
  makes.
- **Points**: alongside win/loss, each player has a live "points" score equal to how
  many of their own ship cells have *not* been hit yet (max 17 across the fleet — 5+4+
  3+3+2). This is shown during the match and used as a tiebreaker in the final bracket
  if a series ends with equal wins (the bot that took less damage overall wins the
  tiebreak).

---

## 2. Setup

If you haven't already:

```bash
uv python install 3.13
uv sync --python 3.13
uv run gamenight list-games
```

You should see `battleship` in the list.

---

## 3. Phase 1: Placement (In Code)

While `state["phase"] == "placement"`, your bot is asked, one ship at a time (carrier
down to destroyer), where to put it.

**`observation` highlights during placement:**

```python
observation["public_state"]["phase"]              # "placement"
observation["context"]["next_ship_to_place"]      # e.g. "cruiser" -- the ship you must place now
observation["private_state"]["your_fleet"]        # ships you've already placed
observation["legal_actions"]                      # every legal placement for next_ship_to_place
```

**Action you return:**

```python
{"type": "place_ship", "ship": "cruiser", "row": 2, "col": 0, "orientation": "horizontal"}
```

`(row, col)` is the ship's *first* cell; `"horizontal"` extends rightward (same row,
increasing column), `"vertical"` extends downward (same column, increasing row).
`legal_actions` only ever contains placements that are in-bounds and don't overlap a
ship you've already placed — pick one of those.

A reasonable first heuristic: spread your fleet out (don't cluster ships together) so
one lucky streak of opponent hits doesn't reveal your whole layout — see
`bots/baselines/greedy_bot.py` for a worked example.

---

## 4. Phase 2: Battle (In Code)

Once both fleets are placed, `state["phase"] == "battle"` and players alternate firing.

**`observation` highlights during battle:**

```python
observation["private_state"]["tracking_grid"]  # 10x10: "?" unknown, "M" miss, "H" hit, "X" hit & sunk
observation["private_state"]["your_shots"]      # your shot history with results
observation["private_state"]["your_board"]      # your own waters: your ships + incoming shots
observation["public_state"]["points"]           # {"player_blue": N, "player_orange": N} cells not yet hit
observation["legal_actions"]                    # every cell you haven't fired at yet
```

**Action you return:**

```python
{"type": "fire", "row": 3, "col": 7}
```

`row`/`col` are integers `0`-`9`. A reasonable first upgrade from "fire in a fixed
sweep": once `tracking_grid` shows an `"H"` you haven't sunk yet, fire at one of its
orthogonal neighbors instead of continuing your sweep ("hunt-and-target") — again see
`bots/baselines/greedy_bot.py`.

For the full field-by-field reference, see
`src/gamenight/games/battleship/BOT_SPEC.md`, and for two complete worked
observation/action examples (one per phase) see
`src/gamenight/games/battleship/EXAMPLES.md`.

---

## 5. Branches & Creating Your Player Bot

1. Create your branch:

   ```bash
   git checkout -b player/<your_name>
   ```

2. Scaffold your bot folder from the example:

   ```bash
   mkdir -p src/gamenight/games/battleship/bots/players/<your_name>
   cp src/gamenight/games/battleship/bots/players/example_player/bot.py src/gamenight/games/battleship/bots/players/<your_name>/bot.py
   ```

3. Edit **only** `src/gamenight/games/battleship/bots/players/<your_name>/bot.py`.
   Don't edit baseline bots, other players' folders, or shared `src/gamenight/core`
   code.

### What Your Bot Code Looks Like (Input/Output)

Your file must define a class `PlayerBot` with two methods:

```python
class PlayerBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        # Called once at the start of each match. Reset any per-match state here.
        return None

    def choose_action(self, observation: dict, context: MatchContext) -> dict:
        # INPUT:  observation (see Phase 1 / Phase 2 above) + context (game_id, seed,
        #         player_ids, max_turns -- fixed facts, same every turn)
        # OUTPUT: exactly one of the dicts already in observation["legal_actions"]
        return observation["legal_actions"][0]
```

- **Input**: `observation` (a plain dict — `public_state` / `private_state` /
  `context` / `legal_actions`, see Phases 1 & 2 above) and `context` (the match-level
  `MatchContext`).
- **Output**: exactly one dict from `observation["legal_actions"]`. Anything else
  (wrong shape, illegal placement, already-fired-at cell) is rejected by the engine.

If you'd rather have typed, autocomplete-friendly access instead of raw dict lookups,
the example bot file also includes an **optional** `BattleshipObservation` dataclass
with a `.from_dict(observation)` constructor — entirely opt-in, delete it if you don't
want it.

### Optional: Extra Python Packages

If your bot needs a package this project doesn't already include (e.g. `numpy`):

1. Add a `requirements.txt` next to your `bot.py`:
   `src/gamenight/games/battleship/bots/players/<your_name>/requirements.txt`

2. **List one package name per line, with NO version pin** — just the name (e.g.
   `numpy`, not `numpy==1.26.0`). This is required so files stay trivial to merge and
   everyone gets a consistent, current resolution:

   ```
   numpy
   networkx
   ```

3. Run with the overlay flag:

   ```bash
   uv run --with-requirements src/gamenight/games/battleship/bots/players/<your_name>/requirements.txt \
     gamenight run-game --game battleship --mode headless --bot-1 player:<your_name> --bot-2 random
   ```

This keeps extra packages isolated to your bot's runs only — nothing touches the shared
`pyproject.toml` or lockfile.

---

## 6. Training / Iterating Over Many Games

A handful of games isn't enough to tell if a change helped — use `run-series` to play
your bot against a baseline (or another player's bot) many times in a row:

```bash
uv run gamenight run-series --game battleship \
  --bot-a player:<your_name> --bot-b greedy \
  --games 100 --starting-policy alternate \
  --summary-file artifacts/<your_name>_vs_greedy.json
```

This writes a JSON summary with win counts for each side. Tweak your bot, rerun, and
compare `wins_bot_a` across runs to see if your change actually helped — alternate
which bot starts (`--starting-policy alternate`) so the result isn't just an artifact
of who fires first.

Want to *watch* a series live instead of just getting numbers? Add `--mode gui`:

```bash
uv run gamenight run-series --game battleship \
  --bot-a player:<your_name> --bot-b greedy \
  --games 5 --starting-policy alternate --mode gui --gui-delay 0.2 \
  --summary-file artifacts/<your_name>_vs_greedy_gui.json
```

Each board shows the bot's name on top and a running `Wins: N  Losses: N` underneath.
Use small `--games` counts in GUI mode (single digits) — it plays every turn live, so
it's slow for stat-gathering. Use headless `run-series` with `--games 100+` for that.

---

## 7. Playing One Game Between Two Bots

Headless (fast, no window):

```bash
uv run gamenight run-game --game battleship --mode headless \
  --bot-1 player:<your_name> --bot-2 greedy \
  --replay-file artifacts/<your_name>_vs_greedy.json
```

GUI ("TV view" — both fleets fully revealed, side by side, for spectators only —
neither bot ever sees the opponent's fleet):

```bash
uv run gamenight run-game --game battleship --mode gui \
  --bot-1 player:<your_name> --bot-2 greedy --gui-delay 0.4 \
  --replay-file artifacts/<your_name>_vs_greedy_gui.json
```

Replay a saved match as text afterwards:

```bash
uv run gamenight replay --replay-file artifacts/<your_name>_vs_greedy.json
```

Bot names: `greedy`, `random`, `human`, or `player:<folder_name>`.

---

## 8. Tonight's Schedule

| Time | What happens |
| --- | --- |
| **0:00 – 0:30** | **Build.** Code your bot on your `player/<your_name>` branch. Use `run-game` and `run-series` to test as you go. |
| **0:30** | **First submission (secret).** Compile and merge — see "Submitting Your Bot" below. **Only the compiled `.pyc` goes into `main`** — keep your `bot.py` source local/private so nobody can read your strategy. |
| **0:30 – 0:50** | **Keep improving.** Continue editing your local `bot.py` (source). Test against `greedy`/`random`/your own earlier build as much as you like. |
| **0:50 (10 min before the hour)** | **Final submission (secret).** Re-compile and merge your updated bot the same way — this overwrites your earlier `.pyc` on `main`. |
| **1:00** | **Final bracket.** Everyone's submitted bots face off in a single-elimination bracket. Winners announced! |

### Submitting Your Bot (Secret / Compiled)

Each submission step is the same two commands:

```bash
uv run gamenight encode-bot --game battleship --player <your_name>
```

This compiles your `bot.py` into `bot.pyc` right next to it. Then:

1. Make sure `bot.pyc` is staged for commit.
2. **Remove or `.gitignore` `bot.py`** before committing/merging — only `bot.pyc`
   should land on `main`. The loader checks for `bot.py` first and only falls back to
   `bot.pyc` when no source is present, so your bot still runs as `player:<your_name>`
   for everyone, with no extra steps.
3. Commit and merge into `main` (ask the organizer for the exact merge command if
   you're not comfortable with git — e.g. open a PR and merge it, or push directly per
   the night's git flow).

Keep working on your real `bot.py` source locally between submissions — just remember
to re-run `encode-bot` and re-merge at the 10-minutes-before mark.

> Heads up: `.pyc` is "don't spoil the reveal," not real security — it's decompilable,
> and variable/string names survive compilation as-is. Don't put your secret strategy
> *in plain English* in a variable name if you want it to stay a surprise.

---

## 9. The Final Bracket

At the 1-hour mark, the organizer runs a single-elimination bracket across everyone's
submitted bots:

```bash
uv run gamenight run-bracket --game battleship \
  --bots greedy,random,player:alex,player:sam,player:jordan \
  --games-per-match 3 \
  --output-dir artifacts/bracket
```

- Each matchup is a short series (`--games-per-match`); whoever wins more games
  advances. Bots alternate who goes first each game.
- Ties in a series are broken by total **points** (cells not yet hit) — see section 1
  — and finally by bracket order.
- A replay file is saved for every game played, plus a `bracket_summary.json` with the
  whole bracket tree and the champion. Replay any game with
  `uv run gamenight replay --replay-file <path>`.

Good luck, and may your hunt-and-target be ever in your favor!
