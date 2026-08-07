# mark_rl -- a learned Splendor bot

Mark's second Splendor bot, alongside the hand-tuned heuristic in `../mark/`. Same
idea (score every legal action, play the best-scoring one) but the scoring function
is a small MLP trained by self-play against `player:clayton`, not hand-written.

## Files

- **`bot.py`** -- the actual player bot (`PlayerBot`, loaded via `player:mark_rl`
  same as any other player folder). Pure stdlib: reads `weights.json`, extracts a
  64-dim feature vector per legal action (`encode`), scores it with a tiny tanh MLP
  (`forward`), plays the highest-scoring legal action. No numpy or torch at runtime
  -- see the module docstring for why (short version: this file gets `exec`'d
  directly by `core/bots.py`'s loader, in a process that only has `typer`
  installed, same as every other bot in the repo).
- **`train.py`** -- the training script. Plays batches of self-play games against
  an opponent (default `clayton`), and after each batch nudges the weights via
  REINFORCE (vanilla policy-gradient, softmax over the same per-action scores
  `bot.py` uses, Adam optimizer) toward what won and away from what lost. Needs
  `numpy` (see `requirements.txt`) -- reimplements `bot.py`'s forward pass in
  batched numpy for training speed, and self-checks the two agree on startup.
- **`requirements.txt`** -- just `numpy`, and only for `train.py`.
- **`weights.json`** -- the trained weights `bot.py` loads. Committed alongside
  `bot.py` so the bot is playable without re-running training.

## Training

```bash
cd src/gamenight/games/splendor/bots/players/mark_rl

# uv finds the project's pyproject.toml by searching upward from cwd, and merges
# this folder's requirements.txt into the same ephemeral env -- so both numpy and
# the editable `gamenight` package resolve, no venv setup needed.
uv run --with-requirements requirements.txt python train.py --episodes 20000

# keep training on top of the existing weights.json instead of from scratch:
uv run --with-requirements requirements.txt python train.py --episodes 5000 --resume

# just measure the current weights.json's win rate, no training:
uv run --with-requirements requirements.txt python train.py --eval-only --eval-games 200
```

`train.py --help` lists every knob (opponent, learning rate, temperature schedule,
batch size, eval cadence, ...); see the module docstring for the algorithm and why
each piece is there.

## Publishing (going blind, same as `clayton`/`hunter`)

Once the weights are good enough to submit for real, follow the project's usual
blind-submission flow (`gamenight encode-bot`, see `../../../BOT_SPEC.md` /
`core/bots.py`): compile `bot.py` to `bot.pyc` and stop committing the source.
`weights.json` still needs to be committed either way -- it's data, not strategy
source, and `bot.py`'s `Path(__file__).resolve().parent / "weights.json"` lookup
works identically whether `__file__` points at `bot.py` or `bot.pyc`.

```bash
uv run gamenight encode-bot --game splendor --player mark_rl
```
