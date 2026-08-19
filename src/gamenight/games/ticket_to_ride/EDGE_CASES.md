# Ticket to Ride Edge-Case Verification

`render_text`/`observe`/headless matches are good smoke tests, but Ticket to Ride's
turn-phase state machine and end-game scoring have far more surface area than this
repo's earlier games. Before trusting `game.py`, the following scenarios were run
directly against `TicketToRideGame` (via `create_initial_state`/`step`/`legal_actions`
plus a few internal helpers) and confirmed correct. Reproduce all of them at once with
the script referenced at the bottom.

| # | Edge case | How it was exercised | Result |
|---|---|---|---|
| 1 | Full random games complete for every supported player count | Played 2p/3p/4p/5p games to completion with `RandomBot` on both sides | All reach `done=True` with `final_scores` populated |
| 2 | Board data sanity | Counted routes/tickets/twin pairs from `data.py` | Exactly 100 routes, 30 tickets, 22 double-route pairs (44 routes with a twin) |
| 3 | Double-route exclusivity at 2-3 players | Forced a claim on one route of a twin pair in a 2-player game | The twin becomes unclaimable by *anyone*, not just the claimant |
| 4 | Double-route exclusivity at 4-5 players | Same setup at 4 players | The original claimant *cannot* claim the twin themselves; a *different* player can |
| 5 | Final-round trigger fires correctly | Forced a player's `trains_remaining` to drop to <=2 via a claim | `final_round_trigger` set to that player, `final_round_turns_left` set to the player count, game not yet `done` |
| 6 | Final-round countdown is exactly right | Played out the final round with random bots, tracking whose turn it was each time `phase == "action"` started | Every other player got exactly 1 more turn, **and the trigger player also got exactly 1 more turn** (not 0, not 2) -- see the bug writeup below |
| 7 | Ticket connectivity: disconnected | Held a ticket with zero claimed routes | Scores `-points`, counts as 0 completed |
| 8 | Ticket connectivity: connected | Built a real route chain (BFS over the actual map) connecting a real ticket's two cities, assigned it as `claimed_routes` | Scores `+points`, counts as 1 completed |
| 9 | Longest path on a branching graph | Built a 3-edge "hub" subgraph (one city, three routes) from real map data | Found the longest trail correctly picks the *best two* edges through the hub, not all three (the third dead-ends back through an edge already used) |
| 10 | Terminal-state idempotency | Called `step` again on an already-`done` state | Returns the *same* state object unchanged, `done=True` (safe no-op) |
| 11 | Legal-action gating | Checked `legal_actions` for the non-current player, and for anyone once `done` | Empty in both cases |
| 12 | Face-up 3-locomotive purge | Forced `face_up` to `[wild, wild, wild, red, blue]` | Entire display discarded and refilled from the deck; deck shrank by exactly 5 |
| 13 | Face-up purge doesn't over-trigger | Forced `face_up` to `[wild, wild, red, blue, green]` (only 2 wilds) | No purge |
| 14 | Deck-empty reshuffle | Emptied `train_deck`, populated `train_discard` | Drawing succeeds by reshuffling discard into deck; discard ends up empty |

## Bug #1: the final-round countdown was off by one

The official rule is "each player, including the one who triggered it, gets one final
turn." First implementation: set `final_round_turns_left = len(player_ids)` the
moment a player's trains hit <=2, then immediately run the same turn-ending logic
(decrement-and-check) that handles every other turn. That's wrong -- it counts the
*triggering* turn itself as one of the "N final turns," when the rule's "one final
turn" for the trigger player refers to their turn **after** the trigger, once the
rotation comes back around to them.

Caught by test #6 (`EDGE_CASES` script): tracking exactly which player started each
logical turn (`phase == "action"`) after the trigger fired showed the trigger player
appearing 0 times before the fix, not 1. **Fix**: the turn that sets
`final_round_trigger` advances to the next player *without* decrementing the new
countdown -- the countdown only applies to turns from that point forward. After the
fix, a 3-player game showed exactly one turn each for the other two players, plus one
more for the trigger player, in that order, before the game ended.

## Bug #2: 4-5 player games were getting silently truncated

`core/match.py`'s `run_match`/`run_match_with_observer` count `step()` calls (not
logical player turns) against a `max_turns` budget, defaulting to 200 -- fine for
every earlier game here, where a turn is always exactly one `step()`. Ticket to
Ride's turns can be 2-3 steps (draw two cards, or draw-then-choose-tickets), so the
effective turn budget was really more like 70-100 logical turns. Measured directly:

```
uv run gamenight run-game --game ticket_to_ride --mode headless --bots greedy,random,greedy,random
# -> winner=None turns=200   (before the fix -- NOT a real draw, just cut off)
```

A 4-player game reporting `winner=None` at exactly the 200-turn ceiling isn't a tied
score -- `MatchResult.winner=None` is indistinguishable from a real draw to every
consumer of it (series stats, brackets), which is actively misleading. Measured the
actual step counts needed to finish for real (uncapped `max_turns`, 10-40 games per
player count, mixed greedy/random bots):

| Players | Max steps observed |
|---|---|
| 2 | 144 |
| 3 | 213 |
| 4 | 300 |
| 5 | 353 (up to 385 in a larger random-only sample) |

**Fix, in two parts:**

1. `core/match.py`: `max_turns` on `run_match`/`run_match_with_observer` changed from
   a hardcoded `int = 200` default to `int | None = None`. When not explicitly
   overridden, the actual budget resolves via a new `_resolve_max_turns` helper that
   checks the game instance for an optional `RECOMMENDED_MAX_TURNS` class attribute,
   falling back to the same `200` as before. Every existing call site in `cli/main.py`
   and `core/bracket.py` already calls `run_match(...)` without passing `max_turns`
   explicitly, so they all pick this up automatically with zero further changes --
   and every other game (none of which defines `RECOMMENDED_MAX_TURNS`) is
   byte-for-byte unaffected.
2. `TicketToRideGame.RECOMMENDED_MAX_TURNS = 1200` -- comfortable headroom over the
   worst observed (385), cheap to raise further since `step()` itself is fast; the
   cost of a too-high cap is negligible, the cost of a too-low one is silently wrong
   results.

Re-measured after the fix: the same 4-player command above now reaches a real
conclusion (`winner=player_3 turns=271`) instead of a false `None` at the ceiling.

## Reproducing

```bash
uv run python3 -c "
from gamenight.games.ticket_to_ride.game import TicketToRideGame
from gamenight.games.ticket_to_ride.data import ROUTES

g = TicketToRideGame(num_players=2)

# Case 3: double-route exclusivity at 2-3 players
s = g.create_initial_state(seed=5)
twin_route = next(r for r in ROUTES if r.twin_id is not None)
s['route_owner'][twin_route.route_id] = 'player_1'
legal = g.legal_actions({**s, 'phase': 'action', 'current_player': 'player_2'}, 'player_2')
still_claimable = any(a['type'] == 'claim_route' and a['route_id'] == twin_route.twin_id for a in legal)
print('twin still claimable (should be False):', still_claimable)
"
```

The full 14-case suite above lives as a throwaway script during development -- this
table and the two bug writeups are the durable record, per `docs/how_to_add_game.md`'s
verification workflow.
