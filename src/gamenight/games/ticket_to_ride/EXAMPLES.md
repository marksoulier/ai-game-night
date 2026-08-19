# Ticket to Ride Examples

One complete worked example, captured directly from the engine (seed `7`, 2 players).
Both players have finished `initial_tickets` (each kept the minimum, 2), `player_1`
has taken their first turn (drew 2 cards blind from the deck), and now it's
`player_2`'s first turn in the main `"action"` phase.

```json
{
  "public_state": {
    "phase": "action",
    "current_player": "player_2",
    "turn_index": 4,
    "done": false,
    "winner": null,
    "final_round_trigger": null,
    "face_up": ["yellow", "red", "purple", "black", "blue"],
    "train_deck_count": 100,
    "train_discard_count": 0,
    "ticket_deck_count": 24,
    "route_owner": [null, null, "... 100 entries total, all null this early ..."],
    "players": {
      "player_1": {"hand_size": 6, "ticket_count": 2, "trains_remaining": 45, "claimed_routes": [], "route_score": 0},
      "player_2": {"hand_size": 4, "ticket_count": 2, "trains_remaining": 45, "claimed_routes": [], "route_score": 0}
    },
    "final_scores": null
  },
  "private_state": {
    "your_hand": {"purple": 2, "white": 1, "blue": 0, "yellow": 0, "orange": 0, "black": 1, "red": 0, "green": 0, "wild": 0},
    "your_tickets": [
      {"ticket_id": 9, "city_a": "Dallas", "city_b": "New York", "points": 11},
      {"ticket_id": 14, "city_a": "San Francisco", "city_b": "Atlanta", "points": 17}
    ],
    "pending_ticket_choice": null,
    "pending_ticket_min_keep": null
  },
  "context": {
    "cities": {"Atlanta": [0.7806, 0.3669], "...": "...34 more..."},
    "routes": [{"route_id": 0, "city_a": "Vancouver", "city_b": "Calgary", "length": 3, "color": "gray", "twin_id": null}, "... 99 more ..."],
    "route_points": {"1": 1, "2": 2, "3": 4, "4": 7, "5": 10, "6": 15},
    "train_colors": ["purple", "white", "blue", "yellow", "orange", "black", "red", "green"],
    "num_players": 2,
    "trains_per_player": 45,
    "longest_path_bonus": 10
  }
}
```

(`cities`/`routes` are truncated above for readability -- in a real observation
they're the full 36-city / 100-route lists every turn, unchanged for the whole match;
see `data.py` for the complete data or print `context` yourself in a live run.)

Reading this:

- `player_2` holds 4 cards (`your_hand` sums to 4) and 2 tickets worth 11 and 17
  points -- neither ticket is "completed" yet since `claimed_routes` is empty for
  both players this early.
- `player_1`'s `hand_size` went from their initial 4 up to 6 -- they drew twice
  blind from the deck on their first turn (visible only as a count here; you'd never
  see *which* colors they drew, only they know that).
- `legal_actions` at this point (appended by the match runner, not shown above) has
  61 entries: 5 face-up draws + 1 deck draw + 1 `draw_tickets` + **54** different
  `claim_route` combinations. That's not 54 different routes -- it's every
  (route, color, wild-substitution) combination this hand can currently afford across
  every still-unclaimed route. A few samples:

```json
{"type": "claim_route", "route_id": 1, "color": "purple", "wild_count": 0}
{"type": "claim_route", "route_id": 1, "color": "white", "wild_count": 0}
{"type": "claim_route", "route_id": 2, "color": "purple", "wild_count": 0}
```

  Route `1` here is `Vancouver <-> Seattle` (gray, length 1) -- since it's gray,
  every color the player holds at least one of is a legal declaration, and since it's
  only length 1, no wildcards are needed at all (`wild_count: 0`). A longer route
  would show more combinations mixing in wildcards as `wild_count` increases.

## A finished game's `final_scores`

Once `done` is `true`, `public_state.final_scores` looks like this (one real 2-player
game, greedy vs. random):

```json
{
  "player_1": {
    "route_score": 43, "ticket_score": -66, "tickets_completed": 1, "tickets_total": 8,
    "longest_path_length": 11, "longest_path_bonus": 0, "total": -23
  },
  "player_2": {
    "route_score": 48, "ticket_score": -97, "tickets_completed": 1, "tickets_total": 8,
    "longest_path_length": 26, "longest_path_bonus": 10, "total": -39
  }
}
```

Both totals are negative here because both players (random-vs-random in this
particular sample) held far more tickets than they ever connected -- a real
illustration of why *not* over-collecting tickets you have no path toward matters.
`player_2`'s `longest_path_length` (26) beat `player_1`'s (11), so only `player_2`
picked up the +10 `longest_path_bonus`.
