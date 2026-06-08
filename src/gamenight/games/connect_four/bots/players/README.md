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
plain dict — every game has a different shape. Open `example_player/bot.py`: its
`choose_action` docstring walks through every field Connect Four puts in `observation`
(and `context`), with the type and valid range of each one, annotated inline right where
you'll be reading and writing code. The same shape is also documented in `../../BOT_SPEC.md`
(the full spec) and `../../EXAMPLES.md` (a complete worked request/response example) —
all three describe the same thing, just at different levels of "show me in the code" vs.
"give me the reference doc."

## Do And Do Not

Do:

- Keep your bot code in your own folder only.
- Return only legal actions from `observation["legal_actions"]`.
- Create additional bots by creating additional folders.

Do not:

- Edit `bots/baselines/`.
- Edit other player folders.
- Depend on hidden state or data not present in the game spec.

## FAQ

### Can one player create multiple bots?

Yes. One folder maps to one selectable bot identity.

Examples:

- `players/mark/bot.py` -> `player:mark`
- `players/mark_v2/bot.py` -> `player:mark_v2`
- `players/mark_minimax/bot.py` -> `player:mark_minimax`

You can run any of them by folder name:

```bash
uv run gamenight run-game --game connect_four --mode headless --bot-1 player:mark_v2 --bot-2 random
```
