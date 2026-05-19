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
uv run gamenight run-game --game tictactoe --mode headless --bot-x player:mark_v2 --bot-o random
```
