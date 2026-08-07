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

Not sure what's actually inside `observation`? You don't have to guess or rely only on
prose docs -- `../../types.py` has a `TypedDict` for every shape (`SplendorObservation`,
`SplendorAction`, `CardView`, ...) describing the exact plain dict you actually receive,
at zero runtime cost: type your `choose_action` as `observation: SplendorObservation`
(instead of the generic `Observation`) and your editor/type checker understands every
nested field from there on, no conversion step needed. `example_player/bot.py` already
does this, and its `choose_action` docstring walks through every field for all three
phases, with the type and valid range of each one, annotated inline right where you'll
be reading and writing code. The same shape is also documented in `../../BOT_SPEC.md`
(the full spec) and `../../EXAMPLES.md` (complete worked examples) -- all four describe
the same thing, just at different levels of "show me in the code" vs. "give me the
reference doc."

## The three phases, in one paragraph

Most turns, you'll only ever see `phase == "action"`: take tokens, reserve a card, or
purchase one. The engine only drops you into `"discard"` if that action pushed you over
10 tokens, and into `"noble_choice"` if your new bonuses suddenly qualify for two or
more nobles at once (a single qualifying noble is assigned automatically -- no decision
needed). Both are still *your* turn, just an extra required step or two before it passes
to the next player.

## Player count

Splendor supports 2-4 players (`--bot-1`/`--bot-2` for exactly two, or `--bots
name1,name2,name3` for 3-4 -- see the FAQ below). Nothing about your bot's code needs to
change based on player count: `context.opponent_ids` is just a list (1 to 3 entries)
instead of a single id, and `public_state.players` has one entry per seat.

## Do And Do Not

Do:

- Keep your bot code in your own folder only.
- Return only legal actions from `observation["legal_actions"]`.
- Create additional bots by creating additional folders.

Do not:

- Edit `bots/baselines/`.
- Edit other player folders.
- Depend on hidden state or data not present in the game spec -- in particular, the
  only thing your `observation` ever redacts is a *blind*-reserved card's identity for
  someone else (`source: "deck"` in their case, though you'd never see that key for
  anyone but yourself). An opponent's *market*-reserved cards are legitimately visible
  to you via `public_state.players[<id>].visible_reserved_cards` -- see
  `../../BOT_SPEC.md`'s "Reserved-Card Visibility" section. You always see your own
  reserved cards in full, either way.

## FAQ

### Can one player create multiple bots?

Yes. One folder maps to one selectable bot identity.

Examples:

- `players/mark/bot.py` -> `player:mark`
- `players/mark_v2/bot.py` -> `player:mark_v2`
- `players/mark_engine_rush/bot.py` -> `player:mark_engine_rush`

You can run any of them by folder name:

```bash
uv run gamenight run-game --game splendor --mode headless --bot-1 player:mark_v2 --bot-2 random
```

Or seat it in a 3-4 player game with `--bots`:

```bash
uv run gamenight run-game --game splendor --mode headless --bots player:mark_v2,random,greedy
```
