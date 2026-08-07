# Splendor Bot Spec

This document defines the exact bot interface for Splendor.

## Bot Class Contract

Implement class `PlayerBot` with methods:

- `reset(context)`
- `choose_action(observation, context)`

## Player Count

Splendor supports **2 to 4 players** (`SplendorGame.MIN_PLAYERS`/`MAX_PLAYERS`). Player
ids are `player_1`, `player_2`, ... up to however many bots the match was started with
(see the top-level README's `--bots` flag). Nothing else about the observation shape
changes with player count -- `public_state.players` just has more entries, and
`context.opponent_ids` lists however many opponents you actually have (1 to 3).

## Explicit Types

Every shape in this document has a matching `TypedDict` in `types.py`
(`SplendorObservation`, `SplendorAction`, `CardView`, `ReservedCardView`, `NobleView`,
`PlayerPublicView`, `Context`, and one class per action type). These describe the exact
same plain dict your `choose_action` already receives -- no conversion, no wrapper
object, zero runtime cost -- so typing your method signature as `observation:
SplendorObservation` (instead of the generic `Observation`) gets you real editor
autocomplete and type-checker coverage on every field below, including `action["type"]`
narrowing which other fields are valid once you've checked it (the same way narrowing
any tagged union works). `bots/players/example_player/bot.py` uses this as the default;
`types.py` itself has the full field-by-field reference with inline comments.

## Observation Object

Splendor has **three phases** and is **almost perfect information** -- `observation`
always has the same top-level shape, but `legal_actions` (and, during
`"noble_choice"`, `context.pending_noble_choices`) depend on which phase you're in.

`public_state` -- true for everyone, never redacted:

- `phase`: `"action"` | `"discard"` | `"noble_choice"` -- see "Phases" below
- `current_player`: whose turn it is right now (stays the same across all of a turn's
  sub-steps, even through `"discard"`/`"noble_choice"`)
- `turn_index`: integer, incremented on every step -- including discard/noble
  sub-steps, so it advances faster than "how many real turns have happened"
- `done` / `winner`: match status. `winner` is `null` both while the game continues
  *and* in the (rare) case of a genuine tie -- see "Win Condition" below
- `final_round_trigger`: `null` until a player reaches 15+ points; from then on it
  holds that player's id, and the match ends once every player has had one more equal
  turn (Splendor's real "everyone gets an equal number of turns" rule -- reaching 15
  doesn't end the game on the spot)
- `bank`: `{"white": N, "blue": N, "green": N, "red": N, "black": N, "gold": 5}` shape
  -- the shared token supply. `N` scales with player count: 4 per color at 2 players,
  5 at 3, 7 at 4 (gold is always 5, regardless of player count)
- `nobles`: the nobles currently in play (`players + 1` of them -- 3/4/5 for a 2/3/4
  player match), each `{"id": ..., "points": 3, "requirement": {"white": 3, "blue":
  3}}` -- requirement keys are bonus colors, never gold
- `market`: `{1: {...}, 2: {...}, 3: {...}}` (tier number -> tier info), each tier
  `{"face_up": [card, ...], "remaining_in_deck": N}` -- `face_up` has up to 4 cards
  (fewer once that tier's deck is exhausted and nothing's left to refill it with);
  `remaining_in_deck` is a count only, never the cards themselves
- `players`: `{player_id: {...}}` for **every player in the match** (including you --
  2 to 4 entries), each `{"points": int, "bonuses": {color: int, ...}, "tokens":
  {color: int, ..., "gold": int}, "reserved_count": int, "visible_reserved_cards":
  [card, ...], "owned_count": int, "nobles": [noble_id, ...]}` -- notice this is public
  for every opponent too: points, bonuses, and token counts are all visible in real
  Splendor, exactly like watching across a table. `visible_reserved_cards` is the
  market-origin subset of that player's reserved cards, shown to you in full (see
  "Reserved-Card Visibility" below); `reserved_count - len(visible_reserved_cards)` is
  how many of theirs are blind-origin and stay genuinely unknown to you.

`private_state` -- your own reserved cards, always in full:

- `your_reserved_cards`: your own reserved cards in full (`{"id", "tier", "bonus",
  "points", "cost", "source"}` each -- `source` is `"market"` or `"deck"`, see below),
  regardless of how you acquired them. This exists under `private_state` only because
  they're *yours*, not because they're secret from you -- you always know your own.

## Reserved-Card Visibility

This is Splendor's one real information-policy subtlety, worth calling out on its own:
**not all reserved cards are equally hidden.** A card reserved from the face-up market
was watched leaving the market by literally everyone at the table the instant before it
happened -- there's nothing left to hide, so `observe()` shows it to every player via
`visible_reserved_cards`, tagged `"source": "market"` in your own `your_reserved_cards`.
A card reserved blind off the top of a deck, by contrast, is genuinely never seen by
anyone but the player who reserved it (`"source": "deck"`) -- that's the actual
hidden-information surface of this game, and the only thing `observe()` ever redacts
from an opponent's view. Don't assume a low `reserved_count` for an opponent means
"nothing to worry about," and don't assume every reserved card is a mystery -- check
`visible_reserved_cards` first; only the gap between it and `reserved_count` is unknown.

`context` -- fixed facts about the match:

- `opponent_ids`: every other seat's id, in turn order (a list of 1 to 3 entries,
  depending on player count -- there is no singular "the opponent" in a 3-4 player
  game, so this is always a list even at 2 players)
- `colors`: `["white", "blue", "green", "red", "black"]` -- the 5 gem colors.
  `"gold"` is a wildcard token, never a color you can request via `take_tokens`.
- `reserve_limit`: `3`
- `token_limit`: `10` -- the trigger for the `"discard"` phase
- `win_threshold`: `15` -- points needed to trigger the final round
- `pending_noble_choices`: list of noble ids, non-empty **only** during
  `phase == "noble_choice"`

`legal_actions`: every legal action for the current phase -- see Action Schema.

## Card Shape

Every card, wherever it appears (`market[tier].face_up`, `owned` cards implied by
`bonuses`/`owned_count`, `visible_reserved_cards`):

```json
{"id": "t2-05", "tier": 2, "bonus": "red", "points": 1, "cost": {"green": 4, "black": 2}}
```

`cost` only lists colors with a nonzero amount -- a color absent from `cost` costs 0.
`bonus` is the permanent discount color you gain by owning this card (see "Paying for a
card" below). See `../README.md`'s "Card Data" note for how this repo's specific 90-card
table was produced.

The one exception is `private_state.your_reserved_cards`, where every card gets one
extra field:

```json
{"id": "t2-05", "tier": 2, "bonus": "red", "points": 1, "cost": {"green": 4, "black": 2}, "source": "market"}
```

`source` is `"market"` (reserved from the face-up market) or `"deck"` (reserved blind) --
see "Reserved-Card Visibility" above.

## Action Schema

### Phase `"action"` -- your main move, exactly one of:

**Take tokens** -- 3 different colors, or 2 of the same:

```json
{"type": "take_tokens", "colors": ["blue", "green", "red"]}
{"type": "take_tokens", "colors": ["blue", "blue"]}
```

`colors` never includes `"gold"` this way. `legal_actions` only offers the 2-same form
for a color with at least 4 left in `bank`, and only offers combinations of 3 different
colors that currently have at least 1 token each in `bank` -- if fewer than 3 colors
have any tokens left, the one action offered takes all of the colors that do (matching
the real rulebook: you can't voluntarily take fewer than what's available).

**Reserve a card** (up to `context.reserve_limit` at once):

```json
{"type": "reserve_card", "location": "market", "tier": 2, "card_id": "t2-05"}
{"type": "reserve_card", "location": "deck", "tier": 3}
```

`"location": "market"` reserves a specific face-up card (it's replaced from that tier's
deck immediately, same as a purchase). `"location": "deck"` reserves blind off the top
of that tier's face-down pile -- there's no `card_id` in the action because you don't
know which card it is yet; it appears in `private_state.your_reserved_cards` on your
next observation. Either way, if `bank["gold"] > 0` you automatically gain 1 gold token
(no separate decision).

**Purchase a card** (from the market or your own reserve):

```json
{"type": "purchase_card", "location": "market", "tier": 2, "card_id": "t2-05"}
{"type": "purchase_card", "location": "reserved", "tier": 2, "card_id": "t2-05"}
```

Only affordable cards appear in `legal_actions` -- see "Paying for a card" below.

**Pass** -- only ever offered when none of the above is possible:

```json
{"type": "pass"}
```

### Phase `"discard"` -- one token at a time, repeated until back to `context.token_limit`:

```json
{"type": "discard_token", "color": "blue"}
```

`color` can be any of the 5 gem colors or `"gold"`. `legal_actions` lists one action per
color you're currently holding at least 1 of. You stay in this phase (still your turn,
`turn_index` still advancing) until your total token count is back to 10 or fewer.

### Phase `"noble_choice"` -- only when 2+ nobles qualify simultaneously:

```json
{"type": "choose_noble", "noble_id": "n03"}
```

One action per id in `context.pending_noble_choices`. If exactly one noble qualifies,
the engine assigns it automatically and you never see this phase at all.

## Paying For A Card

A card's cost is reduced, color by color, by your `bonuses` in that color (permanent
discounts from cards you already own -- unlike tokens, bonuses are never spent). What's
left after bonuses is paid from your matching-color tokens first, then `gold` tokens as
a wildcard for any remaining shortfall. A card only appears as a legal `purchase_card`
action if your tokens + bonuses can cover its full cost this way.

## Win Condition

Reaching `context.win_threshold` (15) points does **not** end the match immediately --
it sets `public_state.final_round_trigger` to your id, and the match continues until
every other player has had one more equal turn (in a 2-player game that's exactly one
more opponent turn; in a 4-player game, the other three each get one), matching the
real rulebook's fairness rule. At that point `done` becomes `true` and `winner` is
decided by points, then (if still tied) fewest `owned_count` cards -- fewer cards to
reach the same score is the stronger, more efficient engine, applied among however many
players are tied (not just two). A genuine tie surviving both tiebreaks is possible and
reported as `winner: null`.

## Context Object

`context` (the `MatchContext` passed to `reset`/`choose_action`, distinct from
`observation["context"]`) includes:

- `game_id`
- `seed`
- `player_ids`
- `max_turns`

## Bot Author Rules

Do:

- Read only fields in this spec.
- Return one of the provided legal actions.
- Keep implementation inside your own player folder.

Do not:

- Read hidden/off-spec information -- in particular, there is no field anywhere in
  your `observation` that reveals a *blind*-reserved card's identity for any opponent
  (`source: "deck"` ones). Market-origin reserves (`source: "market"`) are legitimately
  visible via `visible_reserved_cards` -- see "Reserved-Card Visibility" above -- so
  reading those is expected, not a leak.
- Edit baseline bots or other players' folders.
- Change shared core infrastructure for player-bot tasks.

## FAQ

### Can I create more than one bot?

Yes. One folder equals one bot identity.

For example:

- `players/alex/bot.py` -> `player:alex`
- `players/alex_v2/bot.py` -> `player:alex_v2`

### How do I run my bot?

Head-to-head (2 players):

```bash
uv run gamenight run-game --game splendor --mode headless --bot-1 player:<your_bot_name> --bot-2 random
```

3 or 4 players -- use `--bots` (comma-separated, in seat order) instead of
`--bot-1`/`--bot-2`:

```bash
uv run gamenight run-game --game splendor --mode headless --bots player:<your_bot_name>,random,greedy
```

## Verifying A New Implementation (For Game Authors)

If you're modifying `game.py`, don't rely on a handful of headless matches to convince
yourself the rules are right -- Splendor has more moving state than Battleship (a shared
market that refills, per-color bonuses, a multi-step turn, an end-condition that isn't
"first to trigger wins") and several of those interact in ways a casual playthrough
won't stress. Before calling an implementation done, exercise these directly against the
engine (`create_initial_state` / `step` / `legal_actions` / `observe`):

- **Take-tokens scarcity rule**: with fewer than 3 colors available in `bank`, the only
  `take_tokens` (3-different-style) action offered takes exactly the colors that remain
  -- never a player-chosen subset, never a phantom 3rd color.
- **Affordability and bonuses**: a card whose cost is fully covered by `bonuses` alone
  (0 tokens needed) is purchasable with an otherwise-empty token pool; a card needing
  exactly your remaining `gold` count after bonuses+tokens is purchasable, one more than
  that is not.
- **Market refill**: purchasing or reserving a face-up card immediately pulls a
  replacement from that tier's deck (if any) -- `face_up` should return to 4 cards, or
  end up permanently short only once that tier's deck is truly empty.
- **Reserve limit and blind reserve**: a 4th `reserve_card` action must never appear
  once a player already has 3 reserved; reserving blind from an empty tier deck must
  raise, not silently reserve nothing.
- **Reserved-card visibility split**: a market-reserved card must appear, in full, in
  every other player's `visible_reserved_cards` for that owner -- and a blind-reserved
  card must appear in `reserved_count` but *never* in `visible_reserved_cards`, for
  anyone but the owner (whose own `private_state.your_reserved_cards` always shows
  both kinds, tagged with the correct `source`). A card purchased out of a player's
  reserve must not carry a stray `source` field once it's in `owned` -- that field only
  means something while a card is still reserved.
- **Discard phase loop**: pushing a player over 10 tokens (e.g. via `take_tokens` while
  already near the cap) must flip `phase` to `"discard"` and offer one `discard_token`
  per held color, looping (still the same player, `turn_index` still advancing) until
  back at 10 -- then automatically continue into the noble check, not straight to the
  next player's turn.
- **Noble auto-assign vs. choice**: a purchase that qualifies for exactly one noble
  assigns it with no extra step; a purchase that qualifies for two at once must flip
  `phase` to `"noble_choice"` with both ids in `context.pending_noble_choices`, and
  never auto-pick one for the player.
- **Player-count scaling**: `bank` per-color counts must be exactly 4/5/7 at 2/3/4
  players (gold always 5), and `nobles` must reveal exactly `players + 1` (3/4/5).
- **N-player turn rotation**: `current_player` must cycle through every seat in order
  (`player_1` -> `player_2` -> ... -> back to `player_1`), not assume exactly two seats.
- **Final-round timing (N players)**: reaching 15 points must set `final_round_trigger`
  but leave `done=False`, and the match must continue until *every other* player has
  had one more turn -- not end after just one more turn in a 3-4 player match.
- **Winner tiebreak (including multi-way)**: an equal-points final state must resolve
  by `owned_count` (fewer cards wins) among however many players are tied on points --
  not just a pair -- and a state still tied after both tiebreaks must resolve to
  `winner: null`, not crash or default to one player.
- **Terminal-state idempotency**: calling `step` again after `done=True` must be a safe
  no-op, not a crash or silent corruption.

These exact checks (with passing fixtures) are recorded in `EDGE_CASES.md`.
