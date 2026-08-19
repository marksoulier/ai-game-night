# Ticket to Ride Bot Spec

This document defines the exact bot interface for Ticket to Ride.

## Bot Class Contract

Implement class `PlayerBot` with methods:

- `reset(context)`
- `choose_action(observation, context)`

Same contract as every other game here -- **still exactly one method.** Ticket to
Ride's turn is a small state machine (see "Turn Structure" below), but the framework
just calls `choose_action` again for each step of it, with a fresh `observation`
reflecting whatever's true right now. There's no second method to implement, no new
class shape -- `phase` in `observation["public_state"]` tells you which step of a
turn you're in, and you branch on it inside the one function, the same way Battleship
bots already branch on `"placement"` vs `"battle"`.

## The Game In Short

The official USA map: 36 cities, 100 routes (22 of them "double routes" -- two
parallel routes between the same two cities), 30 Destination Ticket cards, 2-5
players. Claim routes with matching-colored train cards to score points; hold
Destination Tickets that pay off if your claimed routes connect their two cities (and
cost you points if they don't) at game end. See `../../README.md` for the full
ruleset and the citations behind every number in this doc.

## Turn Structure

A logical turn is 1-3 `choose_action` calls, not always 1:

- **Claim a route**: exactly 1 call. Fully resolved in one action.
- **Draw train cards**: 1 call if your first draw is a face-up locomotive (that ends
  your turn immediately); otherwise 2 calls (`phase` goes `"action"` ->
  `"draw_second_card"` for the same player).
- **Draw destination tickets**: always 2 calls (`phase` goes `"action"` ->
  `"choose_tickets"` for the same player -- you draw 3, then choose which to keep).

`current_player` only changes once a full logical turn resolves -- while you're mid
sub-phase, `state["current_player"]` (and therefore who the match runner asks next)
stays you. There's also a one-time setup era before normal turns start:
`phase == "initial_tickets"` cycles through every player once (draw 3, keep >= 2)
before the first real "action" phase begins with `player_1`.

## Information Policy

**Two independent things are private per player**, unlike every earlier game here
(which has at most one): your train car hand (`your_hand`) and your destination
tickets (`your_tickets`). Everything else -- the face-up market, who owns which
route, everyone's hand *size* and tickets *count* (not contents) -- is public. This
mirrors Splendor's "count public, contents private" pattern for reserved cards,
applied to two different things at once instead of one.

`your_tickets` accumulates over the game and stays private throughout play; it only
becomes visible to everyone (via `public_state.final_scores`) once the match ends,
for scoring transparency.

## Observation Object

`public_state` -- true for everyone, never redacted:

- `phase`: `"initial_tickets"` | `"action"` | `"draw_second_card"` | `"choose_tickets"` | `"done"`
- `current_player`, `turn_index`, `done`, `winner` (`null` covers "still playing" and "ended tied")
- `final_round_trigger`: the player id who first dropped to <=2 trains, or `null`
- `face_up`: list of 5 colors (or fewer, in the rare case the deck+discard are both
  exhausted) currently drawable, e.g. `["red", "wild", "blue", "black", "orange"]`
- `train_deck_count`, `train_discard_count`, `ticket_deck_count`: sizes only, never
  the actual remaining order (that stays hidden from everyone, bots included -- see
  `docs/ARCHITECTURE.md`'s Information Policy on undealt deck order)
- `route_owner`: a 100-entry list, index = `route_id`, value = owning player id or `null`
- `players`: `{pid: {"hand_size", "ticket_count", "trains_remaining", "claimed_routes", "route_score"}}`
  for every player, including yourself (your own hand/tickets *contents* are only in
  `private_state`, this is just sizes/counts)
- `final_scores`: `null` until `done`, then `{pid: {"route_score", "ticket_score",
  "tickets_completed", "tickets_total", "longest_path_length", "longest_path_bonus",
  "total"}}` for every player

`private_state` -- only what *you* would know:

- `your_hand`: `{"purple": 2, "white": 0, ..., "wild": 1}` -- every color, including zeros
- `your_tickets`: `[{"ticket_id", "city_a", "city_b", "points"}, ...]` -- every ticket
  you're holding, whether or not it's currently connected
- `pending_ticket_choice`: the 3 (or fewer, late-game) tickets just drawn, only
  non-`null` during your own `"initial_tickets"`/`"choose_tickets"` phase
- `pending_ticket_min_keep`: how many of `pending_ticket_choice` you must keep (2 on
  the initial deal, 1 on every later draw), only non-`null` alongside `pending_ticket_choice`

`context` -- fixed facts about the match:

- `cities`: `{"Seattle": [x, y], ...}` -- all 36, normalized `[0, 1]` coordinates
- `routes`: `[{"route_id", "city_a", "city_b", "length", "color", "twin_id"}, ...]` -- all 100
- `route_points`: `{1: 1, 2: 2, 3: 4, 4: 7, 5: 10, 6: 15}` -- the official length->points table
- `train_colors`: the 8 colors (not including `"wild"` or a route's own `"gray"`)
- `num_players`, `trains_per_player` (45), `longest_path_bonus` (10)

## Actions, One Per Phase

```json
{"type": "draw_card", "source": "faceup", "index": 2}
{"type": "draw_card", "source": "deck"}
{"type": "draw_tickets"}
{"type": "claim_route", "route_id": 17, "color": "black", "wild_count": 1}
{"type": "choose_tickets", "keep": [4, 11]}
```

- `draw_card`: `source` is `"faceup"` (with `index` 0-4 into `public_state.face_up`)
  or `"deck"` (blind draw, color unknown until it lands in your hand). A face-up
  locomotive is always a legal pick on either draw of a turn -- picking one as your
  *first* draw just ends your turn right after (no second draw), rather than being
  illegal to pick.
- `claim_route`: `color` is the color you're paying with -- always the route's own
  color for non-gray routes, your choice of any of the 8 for a `"gray"` route (`null`
  specifically means "paying entirely in wildcards on a gray route," where the color
  genuinely doesn't matter). `wild_count` is how many of the route's `length` cards
  are locomotives; the rest must be `color`. Only actions your hand can actually
  afford appear in `legal_actions` -- you never need to check affordability yourself.
- `choose_tickets`: `keep` is a sorted list of `ticket_id`s from
  `pending_ticket_choice`, sized `pending_ticket_min_keep` or larger. Every legal
  subset of the right size is pre-enumerated in `legal_actions` -- you're picking one
  whole valid combination, not building it cell-by-cell.

## What You Must Return

Exactly one of the dicts already sitting in `observation["legal_actions"]`. Never
construct an action by hand from fields you computed yourself -- for `claim_route` in
particular, hand affordability and the double-route claiming rules (see README.md)
are already baked into which actions are offered.

## Verifying A New Implementation

Before trusting a change to `game.py`, walk it through (at minimum) the cases in
`EDGE_CASES.md`: double-route exclusivity at 2-3 vs 4-5 players, the final-round
countdown (exactly N more turns, including the trigger player's own next turn --
not N-1, not N+1), ticket connectivity scoring (connected vs. not), the longest-path
search on a hand-built branching graph, the face-up 3-wildcard purge rule, and
deck-empty reshuffling.
