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

Not sure what's actually inside `observation`? `../../BOT_SPEC.md` is the full spec,
`../../EXAMPLES.md` has a complete worked example. The short version: a turn here can
take more than one call to `choose_action` (draw two cards, or draw-then-choose
tickets) — check `observation["public_state"]["phase"]` at the top of your function
and branch on it, the same way you'd already branch on Battleship's placement/battle
phases. It's still exactly one method — see `../../prompts/greedy_bot_prompt.md` for
a full worked example bot if you want a starting point.

## Do And Do Not

Do:

- Keep your bot code in your own folder only.
- Return only legal actions from `observation["legal_actions"]`.
- Create additional bots by creating additional folders.

Do not:

- Edit `bots/baselines/`.
- Edit other player folders.
- Look for opponent hand/ticket *contents* anywhere in `observation` — they don't
  exist. You can see opponents' hand *size* and ticket *count*
  (`observation["public_state"]["players"][pid]`), never what's actually in them.

## FAQ

### Can one player create multiple bots?

Yes. One folder maps to one selectable bot identity.

Examples:

- `players/mark/bot.py` -> `player:mark`
- `players/mark_v2/bot.py` -> `player:mark_v2`

Run any of them by folder name:

```bash
uv run gamenight run-game --game ticket_to_ride --mode headless --bots player:mark,random,greedy,random
```

### How many players can I test against?

2-5 — pass one bot name per seat via `--bots` (comma-separated), or use
`--bot-1`/`--bot-2` for exactly 2.
