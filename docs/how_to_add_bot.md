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
uv run gamenight run-game --game tictactoe --mode headless --bot-1 player:<your_bot_name> --bot-2 random
```

## Optional: Bot-Specific Python Packages

If your bot needs a package that isn't already part of this project (say, `numpy` for
faster board math, or a search/graph library), you don't need to touch the shared
`pyproject.toml` or lockfile, and you don't need anyone's permission to add it — declare
it just for your bot and let `uv` layer it in for that run only.

1. Add a `requirements.txt` next to your `bot.py`:

   - `src/gamenight/games/<game>/bots/players/<your_bot_name>/requirements.txt`

   List one package name per line, with **no version pin** — assume the current/latest
   version of each package (this keeps the file trivial to read, write, and merge):

   ```
   numpy
   networkx
   ```

2. Run your bot with `--with-requirements` pointing at that file. `uv` builds a small
   cached overlay environment with those packages layered on top of the project's
   normal environment, used only for that one command — your `bot.py` then simply
   `import`s the package like normal:

   ```bash
   uv run --with-requirements src/gamenight/games/<game>/bots/players/<your_bot_name>/requirements.txt \
     gamenight run-game --game <game> --mode headless --bot-1 player:<your_bot_name> --bot-2 random
   ```

This is genuinely isolated and easy to "pull and remove": nothing here ever touches the
shared project environment, `pyproject.toml`, or `uv.lock`, so running someone else's
bot is just running the same command against their `requirements.txt`, and getting rid of
a bot's extra packages is as simple as not passing the flag on your next run (or deleting
the file). uv caches these overlay environments so repeat runs are fast; if you ever want
to reclaim the disk space they use, `uv cache clean` clears uv's caches — note that this
clears caches for *all* of your uv projects, not just this one.

## Optional: Submitting A "Blind" Bot (Encoded)

Running a "everyone submits by the halfway mark, then plays everyone else's bot" format?
You can share a compiled version of your bot instead of its source, so opponents can run
it without reading (and being spoiled by) your strategy first:

```bash
uv run gamenight encode-bot --game <game> --player <your_bot_name>
```

This compiles `bot.py` into `bot.pyc` (Python bytecode) right next to it. Commit
`bot.pyc` and remove (or `.gitignore`) `bot.py` — the loader checks for `bot.py` first
and only falls back to `bot.pyc` when no source file is present, so opponents run it
exactly the same way (`player:<your_bot_name>`) with no extra steps on their end.

**Be clear-eyed about what this buys you — it's a fun reveal mechanic, not a vault:**

- It's obscurity, not security. `.pyc` isn't readable as text in an editor, but
  decompilers (`decompyle3` and friends) can reconstruct close-to-original source from
  it without much effort.
- Identifiers and string literals survive compilation **as-is** — only comments and
  formatting are stripped. `strings bot.pyc | grep -i minimax` finds a variable named
  `MAX_MINIMAX_DEPTH` just as easily as grepping the source would. If a name or string
  would spoil your strategy on sight, keep it out of your code as *written text* — the
  encoding step won't hide it for you.
- It's tied to the Python version that compiled it. This project pins Python 3.13 via
  uv, so as long as everyone runs it the normal `uv run gamenight ...` way, this is a
  non-issue — but a `.pyc` compiled under a different Python minor version won't load.

In short: great for "don't spoil the surprise before the showdown" among people who
already trust each other enough to run each other's code locally. Not a substitute for
not running code from people you don't trust.
