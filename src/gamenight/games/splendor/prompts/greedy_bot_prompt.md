# Prompt: Generate Splendor Greedy Bot

You are writing a Python class for this repository.

Task:

- Create class `PlayerBot` in `bot.py`.
- The class must expose:
  - `__init__(self, bot_id: str)`
  - `reset(self, context)`
  - `choose_action(self, observation, context)`
- Type `choose_action`'s `observation` parameter as `SplendorObservation` and its
  return type as `SplendorAction`, both imported from `gamenight.games.splendor.types`
  -- these are `TypedDict`s describing the exact same dict, at zero runtime cost, so
  this is a straight signature change, not a conversion step. See `types.py` for every
  field's type.

Rules:

1. Read only from the provided `observation` and `context`.
2. Never use hidden information -- the only thing `observation` ever redacts is a
   *blind*-reserved card's identity (`source: "deck"`) for anyone but its owner. A
   card reserved from the face-up market (`source: "market"`) is legitimately visible
   for every player via `public_state.players[<id>].visible_reserved_cards` -- reading
   that is expected, not a leak. You always see your own reserved cards in full,
   either way, in `private_state.your_reserved_cards`.
3. Return one action from `observation["legal_actions"]`.
4. If your preferred action isn't legal, fall back to a legal action.
5. This is a 2-4 player game -- don't assume there's exactly one opponent. Use
   `context.opponent_ids` (a list) rather than looking for a single opponent id.

Splendor has three phases -- check `observation["public_state"]["phase"]` first and
branch:

## Phase `"action"`: purchase > reserve > take tokens > pass

1. **If any `purchase_card` action is legal, prefer it.** Converting tokens into a
   permanent bonus + points is almost always better than sitting on tokens.
   - If any affordable purchase's points would bring
     `public_state.players[current_player].points` to `context.win_threshold` (15) or
     higher, take the highest-point such purchase -- win now rather than let the
     opponent catch up during your one remaining "grace" turn.
   - Otherwise, among affordable purchases, prefer the highest `points`; break ties by
     the lowest total cost (`sum(card["cost"].values())`) so you don't overspend tokens
     on an equally-good option.
2. **Else, if any `reserve_card` action is legal, reserve.** Prefer reserving the
   highest-`points` card currently face-up across all tiers (denying it to the
   opponent, banking a future purchase, and picking up a free gold token if the bank
   has any left). If only blind (`"location": "deck"`) reserves are available, prefer
   the highest tier number.
3. **Else, take tokens.** Prefer the "3 different colors" form over "2 of the same"
   (more flexible for future purchases). Among 3-different options, prefer whichever
   set of colors the current face-up market demands the most -- sum each color's
   `cost` amount across every face-up card in `public_state.market`, and pick the
   `take_tokens` action whose colors have the highest combined demand.
4. **Else**, return the `{"type": "pass"}` action (only ever offered when nothing else
   is legal).

## Phase `"discard"`

Discard whichever color you're currently holding the most of, preferring to keep
`"gold"` for last (it substitutes for any color, so it's the most valuable token to
hold onto). Look up your own token counts in
`public_state.players[current_player].tokens`.

## Phase `"noble_choice"`

Pick the first id in `context.pending_noble_choices` -- in this implementation every
noble is worth the same 3 points, so there's no scoring difference between them.

Observation schema summary:

- `observation["public_state"]["phase"]`: which of the three phases above you're in
- `observation["public_state"]["market"]`: `{1: {...}, 2: {...}, 3: {...}}` (integer
  tier keys), each `{"face_up": [card, ...], "remaining_in_deck": int}`
- `observation["public_state"]["players"][player_id]`: `points`, `bonuses`, `tokens`
  (includes `"gold"`), `reserved_count`, `visible_reserved_cards` (their market-origin
  reserves, in full), `owned_count`, `nobles` -- for **every** player in the match,
  this is all public
- `observation["private_state"]["your_reserved_cards"]`: your own reserved cards, in
  full regardless of origin, each tagged `"source": "market"` or `"source": "deck"`
  (only used for the purchase-scoring step above, since `market` alone won't include
  them)
- `observation["context"]["win_threshold"]`: 15
- `observation["legal_actions"]`: only ever legal actions for whichever phase you're in

Implementation notes:

- A card's shape is always `{"id", "tier", "bonus", "points", "cost"}` -- `cost` only
  lists colors with a nonzero amount.
- `take_tokens` actions never include `"gold"` in `colors` -- gold only ever comes from
  reserving.
- Don't assume `legal_actions` always contains a `purchase_card` or `reserve_card`
  option -- early game, most turns are `take_tokens` only.

Output:

- Return valid Python code only.
