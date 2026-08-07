# Splendor Examples

Five worked examples -- the opening `"action"`-phase observation, a purchase mid-game,
the two sub-phases (`"discard"`, `"noble_choice"`) a turn can drop into, a look at how
player count changes the numbers, and the market-vs-blind reserved-card visibility
split. All data below came from actually running `SplendorGame` (`seed=1` throughout,
for the 2-player, 3-player, and reserved-card examples -- same seed produces the same
card/tier arrangement regardless of player count, only the bank size, revealed-noble
count, and who's in `players`/`opponent_ids` differ) -- except `"noble_choice"`, which
is deliberately constructed, noted where that happens.

Splendor's `market` dict is keyed by **integer** tier numbers (`1`, `2`, `3`) in the real
Python object your bot receives -- JSON can't represent integer keys, so the blocks
below use Python literal syntax (` ```python `), not ` ```json `, wherever `market`
appears.

Every shape shown below has a matching `TypedDict` in `types.py` (`SplendorObservation`,
`SplendorAction`, `CardView`, `ReservedCardView`, ...) -- these examples are what those
types describe, field for field; see `BOT_SPEC.md`'s "Explicit Types" section.

## Example 1: Opening Observation (`"action"` phase, turn 0, 2-player match)

```python
{
    "public_state": {
        "phase": "action",
        "current_player": "player_1",
        "turn_index": 0,
        "done": False,
        "winner": None,
        "final_round_trigger": None,
        "bank": {"white": 4, "blue": 4, "green": 4, "red": 4, "black": 4, "gold": 5},
        "nobles": [
            {"id": "n02", "points": 3, "requirement": {"blue": 3, "green": 3}},
            {"id": "n10", "points": 3, "requirement": {"black": 4}},
            {"id": "n05", "points": 3, "requirement": {"black": 3, "white": 3}},
        ],
        "market": {
            1: {
                "face_up": [
                    {"id": "t1-24", "tier": 1, "bonus": "green", "points": 1, "cost": {"red": 2, "black": 2}},
                    {"id": "t1-03", "tier": 1, "bonus": "white", "points": 0, "cost": {"blue": 1, "green": 1, "red": 1}},
                    {"id": "t1-12", "tier": 1, "bonus": "blue",  "points": 0, "cost": {"red": 2, "black": 1}},
                    {"id": "t1-02", "tier": 1, "bonus": "white", "points": 0, "cost": {"blue": 2}},
                ],
                "remaining_in_deck": 36,
            },
            2: {"face_up": ["... 4 tier-2 cards ..."], "remaining_in_deck": 26},
            3: {"face_up": ["... 4 tier-3 cards ..."], "remaining_in_deck": 16},
        },
        "players": {
            "player_1": {"points": 0, "bonuses": {"white": 0, "blue": 0, "green": 0, "red": 0, "black": 0},
                         "tokens": {"white": 0, "blue": 0, "green": 0, "red": 0, "black": 0, "gold": 0},
                         "reserved_count": 0, "visible_reserved_cards": [], "owned_count": 0, "nobles": []},
            "player_2": {"...": "same shape, also all zero at turn 0"},
        },
    },
    "private_state": {"your_reserved_cards": []},
    "context": {
        "opponent_ids": ["player_2"],
        "colors": ["white", "blue", "green", "red", "black"],
        "reserve_limit": 3, "token_limit": 10, "win_threshold": 15,
        "pending_noble_choices": [],
    },
    "legal_actions": [
        {"type": "take_tokens", "colors": ["blue", "green", "white"]},
        {"type": "take_tokens", "colors": ["blue", "red", "white"]},
        {"type": "take_tokens", "colors": ["black", "blue", "white"]},
        "... 30 legal_actions total at turn 0: every 3-different-color combo, all five",
        "2-same-color takes (bank starts at 4 per color, so all five qualify), plus a",
        "reserve_card for each of the 12 face-up cards and each tier's blind deck top ...",
    ],
}
```

Notice `t1-02` costs a flat `{"blue": 2}` -- cheap, 0 points, but its `bonus` is
`"white"`. Buying it doesn't score anything by itself; it's a stepping stone toward
cards (and nobles) that need white bonuses later.

## Example 2: A Purchase, Mid-Game

Continuing from the same seed: `player_1` takes 2 blue tokens, `player_2` takes their
turn, then `player_1` purchases `t1-02` using exactly those 2 blue tokens.

```python
purchase_action = {"type": "purchase_card", "location": "market", "tier": 1, "card_id": "t1-02"}
```

The `step` result's `events` list (what gets written into the replay artifact for that
turn -- note this is a *different* list than what `viewer.update_state`'s `action`
argument receives; see `gui.py`'s `_describe` docstring if you're looking for this
detail while reading the GUI code):

```python
[{"type": "purchase_card", "player": "player_1", "tier": 1, "card_id": "t1-02", "bonus": "white", "points": 0}]
```

`player_1`'s state right after:

```python
{"bonuses": {"white": 1, "blue": 0, "green": 0, "red": 0, "black": 0}, "points": 0, "tokens": {"...": "blue back to 0, spent"}}
```

`points` didn't move (this card is worth 0) -- but `bonuses["white"]` is now 1,
permanently discounting every future card's white cost by 1. `t1-02` is gone from
`market[1]["face_up"]`, immediately replaced by the next card off tier 1's deck.

## Example 3: The Two Sub-Phases

### `"discard"` phase

`player_1` is holding 9 tokens (`white=3, blue=3, green=3`) and takes 1 red + 1 black,
pushing the total to 11 -- one over `context.token_limit` (10):

```python
{"type": "take_tokens", "colors": ["red", "black"]}
```

Resulting state: `phase` flips to `"discard"`, `current_player` is still
`"player_1"` (it's still their turn), and `legal_actions` becomes:

```python
[
    {"type": "discard_token", "color": "white"},
    {"type": "discard_token", "color": "blue"},
    {"type": "discard_token", "color": "green"},
    {"type": "discard_token", "color": "red"},
    {"type": "discard_token", "color": "black"},
]
```

One `discard_token` action (any color they're currently holding, `"gold"` included if
they have any) removes exactly 1 token from that color and puts it back in `bank`. Since
this player is at 11 (one over), a single discard brings them to 10 and `phase` returns
to `"action"` for the *next* player's turn. A player further over the limit (e.g. from a
reserve's free gold pushing them from 10 to 11 some other way) would see the same
`legal_actions` shape again on the very next observation, staying in `"discard"` until
back at 10.

### `"noble_choice"` phase

**This state was constructed directly for illustration**, not reached through normal
play (two nobles qualifying at the exact same moment is possible but not common) --
same spirit as Battleship's EXAMPLES.md engineering a specific "about to sink" shot
rather than waiting for one. Two nobles are in play, both requiring 2 blue bonuses;
`player_1` has 1 blue bonus already and purchases a free (`{}` cost) card whose
`bonus` is `"blue"`, bringing them to 2:

```python
{"type": "purchase_card", "location": "market", "tier": 1, "card_id": "..."}
```

Resulting state: `phase` flips to `"noble_choice"`, `current_player` is still
`"player_1"`, and:

```python
"context": {"pending_noble_choices": ["nA", "nB"], "...": "..."}
"legal_actions": [
    {"type": "choose_noble", "noble_id": "nA"},
    {"type": "choose_noble", "noble_id": "nB"},
]
```

Choosing one (`{"type": "choose_noble", "noble_id": "nB"}`) grants exactly that noble's
points and marks it visited; the other stays in `public_state.nobles` for any player to
potentially qualify for later. If only *one* noble had qualified, the engine would have
assigned it automatically and `player_1` would never have seen a `"noble_choice"` phase
at all -- it only appears when there's a real decision to make.

## Example 4: The Same Seed, 3 Players Instead of 2

Same `seed=1`, same card/tier arrangement as Example 1 -- but started with
`SplendorGame(num_players=3)` (e.g. `run-game --bots greedy,random,player:you`) instead
of the default 2. Everything about the market is identical; only the per-player-count
numbers and the player roster change:

```python
{
    "public_state": {
        "bank": {"white": 5, "blue": 5, "green": 5, "red": 5, "black": 5, "gold": 5},  # 5/color at 3p, not 4
        "nobles": [
            {"id": "n02", "points": 3, "requirement": {"blue": 3, "green": 3}},
            {"id": "n10", "points": 3, "requirement": {"black": 4}},
            {"id": "n05", "points": 3, "requirement": {"black": 3, "white": 3}},
            {"id": "n07", "points": 3, "requirement": {"blue": 4}},  # a 4th noble revealed (players + 1 = 4)
        ],
        "players": {
            "player_1": {"...": "..."},
            "player_2": {"...": "..."},
            "player_3": {"...": "..."},  # a third seat
        },
        "...": "market/phase/turn_index/etc. all unchanged from Example 1",
    },
    "context": {
        "opponent_ids": ["player_2", "player_3"],  # a list of two, not one
        "...": "colors/reserve_limit/token_limit/win_threshold all unchanged",
    },
}
```

`current_player` still only ever names one seat at a time, and `legal_actions` is still
just that one seat's options -- the extra players only show up in `public_state.players`
and `context.opponent_ids`, plus the larger `bank` and one extra `nobles` entry.

## Example 5: Reserved-Card Visibility (Market vs. Blind)

Same seed=1, 2-player match. `player_1` reserves `t1-24` from the tier-1 *market*, then
(a turn later) reserves blind off the top of the tier-3 *deck*. `player_1`'s own view,
`private_state.your_reserved_cards`, shows both in full, `source`-tagged:

```python
[
    {"id": "t1-24", "tier": 1, "bonus": "green", "points": 1, "cost": {"red": 2, "black": 2}, "source": "market"},
    {"id": "t3-19", "tier": 3, "bonus": "black", "points": 5, "cost": {"white": 3, "green": 6}, "source": "deck"},
]
```

`player_2`, observing the exact same state, sees a different amount of detail about
`player_1` -- full identity for the market-origin one, nothing but a count for the
blind one:

```python
# obs = game.observe(state, "player_2")
obs["public_state"]["players"]["player_1"] == {
    "...": "points/bonuses/tokens/owned_count/nobles unchanged from the shape shown above",
    "reserved_count": 2,
    "visible_reserved_cards": [
        {"id": "t1-24", "tier": 1, "bonus": "green", "points": 1, "cost": {"red": 2, "black": 2}},
        # -- notice: no "source" key here, and no second entry for t3-19. player_2
        # knows player_1 has 2 cards reserved (reserved_count) but can only identify
        # 1 of them (visible_reserved_cards) -- the other is genuinely unknown until
        # player_1 plays it (or the match ends and it's revealed as unplayed).
    ],
}
```

The rule in one sentence: `reserved_count - len(visible_reserved_cards)` is always the
number of an opponent's reserves that are truly hidden from you -- `0` if everything
they've reserved came from the market, up to `reserved_count` itself if all of it was
reserved blind.
