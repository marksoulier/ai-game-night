# Player Bots

Each player creates a personal folder in this directory:

- `players/<your_name>/bot.py`

Example:

- `players/alex/bot.py`

Rules:

1. Do not edit other players' folders.
2. Do not modify baseline bots.
3. Implement one class named `PlayerBot` with:
   - `bot_id` field
   - `reset(context)`
   - `choose_action(observation, context)`

Not sure what's actually inside `observation`? Your editor can only tell you it's a
plain dict — `../../BOT_SPEC.md` is the full spec, and `../../EXAMPLES.md` has a
complete worked example. The short version: Mine Duel has **no hidden information** —
both players see the exact same shared board, so `observation["private_state"]` is
always `{}`. Everything you need is in `observation["public_state"]` and
`observation["context"]`.

## Do And Do Not

Do:

- Keep your bot code in your own folder only.
- Return only legal actions from `observation["legal_actions"]`.
- Create additional bots by creating additional folders.

Do not:

- Edit `bots/baselines/`.
- Edit other player folders.
- Look for hidden state that doesn't exist — there is no field anywhere that tells you
  where a mine is before it's been revealed (to either player).

## FAQ

### Can one player create multiple bots?

Yes. One folder maps to one selectable bot identity.

Examples:

- `players/mark/bot.py` -> `player:mark`
- `players/mark_v2/bot.py` -> `player:mark_v2`

Run any of them by folder name:

```bash
uv run gamenight run-game --game mine_duel --mode headless --bot-1 player:mark --bot-2 random
```
