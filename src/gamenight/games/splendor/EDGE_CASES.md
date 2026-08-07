# Splendor Edge-Case Verification

Splendor has more moving state than any earlier game in this repo: a shared market that
refills itself, permanent per-color bonuses, a multi-step turn (main action, then an
optional forced discard, then an optional noble choice), and an end condition that isn't
"the game stops the instant someone crosses the line." Headless smoke matches exercise
whatever a bot happens to do -- they won't reliably reach a forced discard, a
two-nobles-at-once tie, or the exact final-round handoff. Before trusting `game.py`, the
following scenarios were run directly against `SplendorGame` (via `create_initial_state`
/ `step` / `legal_actions` / `observe`) and confirmed correct:

| # | Edge case | How it was exercised | Result |
|---|---|---|---|
| 1 | Full-game smoke, 20 seeds | Played 20 complete random-vs-random games (`legal_actions` -> `random.choice` -> `step`, looped to `done`), asserting `legal_actions` is never empty for a non-terminal state and every game finishes well under a 2000-turn cap | All 20 finished (59-91 turns), reaching sane final scores (winner always >= runner-up per the tiebreak rule) |
| 2 | Take-tokens scarcity rule | Forced `bank` down to only 2 nonzero colors (`green: 2, red: 1`, rest 0) and read `legal_actions` | The only "3-different-style" `take_tokens` action offered was exactly `{"colors": ["green", "red"]}` -- never a phantom 3rd color, never a player-chosen smaller subset when more were available |
| 3 | Affordability with bonuses + gold | Checked `_affordable` directly: a card costing `{"blue": 2, "green": 1}` against bonuses `{"blue": 2, "green": 1}` (fully covered, 0 tokens) -> affordable; against bonuses `{"blue": 1, "green": 1}` with 0 gold -> not affordable (short 1 blue); same state with 1 gold token -> affordable (gold covers the shortfall) | All three assertions passed |
| 4 | Market refill on purchase | Bought a tier-1 face-up card directly (`step` with a `purchase_card` action) and checked the resulting state | `face_up` returned to 4 cards (pulled from the deck), the deck shrank by exactly 1, and the purchased card's id no longer appears in `face_up` |
| 5 | Reserve limit | Set a player's `reserved` to 3 cards, then read `legal_actions` | Zero `reserve_card` actions offered; calling `_apply_reserve` directly for a 4th anyway raises `ValueError` rather than silently accepting it |
| 6 | Blind reserve from an empty deck | Emptied a tier's `deck` list, then called `_apply_reserve` with `location: "deck"` for that tier | Raises `ValueError` rather than reserving nothing or crashing on `.pop()` |
| 7 | Discard-phase loop | Gave a player 9 tokens, then applied a `take_tokens` action that pushed them to 11 | `phase` flips to `"discard"`, `current_player` stays the same player, `legal_actions` offers one `discard_token` per held color; discarding one token (down to 10) flips `phase` back to `"action"` **and** hands the turn to the opponent in the same step -- confirming the phase only fully resolves once back at the limit, not after a single discard if more were still owed |
| 8 | Noble auto-assign vs. choice | Crafted a state where a purchase's new bonus qualifies for exactly one noble -> assigned automatically, `phase` stays `"action"`, turn passes immediately. Separately, crafted a state where the same purchase qualifies for two nobles at once -> `phase` flips to `"noble_choice"` with both ids in `pending_noble_choices`, turn does **not** pass until `choose_noble` is submitted, and only the chosen noble is granted | Both paths behaved exactly as specified in BOT_SPEC.md -- the engine never silently auto-picks between two qualifying nobles |
| 9 | Final-round timing | Set a player to 12 points, gave them a purchase worth 4 (reaching 16) | `final_round_trigger` is set to that player, `done` stays `False`, turn passes to the opponent as normal; only after that opponent's own turn fully resolves does `done` flip to `True` -- reaching 15+ does not end the match on the spot |
| 10 | Winner tiebreak (points -> cards -> true draw) | Called `_determine_winner` on: equal points with unequal `owned` counts (fewer cards wins); equal points *and* equal card counts (returns `None`, a true draw) | Both resolved correctly -- no crash, no arbitrary default winner on a genuine tie |
| 11 | Terminal-state idempotency | Called `legal_actions` for both players and `step` again on an already-`done` state | `legal_actions` returns `[]` for both players; `step` returns the *same* state object unchanged, `done=True` |
| 12 | GUI renders every phase shape | Called `SplendorViewer.update_state` directly on hand-built `discard`, `noble_choice`, terminal-draw, and terminal-win (with nonzero `reserved` cards on both sides) states | Found and fixed a real bug (below); after the fix, all four render without exception |
| 13 | Player-count scaling (2/3/4) | Built `SplendorGame(num_players=n)` for `n` in `2, 3, 4` and read `create_initial_state`'s `bank`/`nobles` | `bank` per color is exactly 4/5/7 (gold always 5); `len(nobles)` is exactly 3/4/5 (`n + 1`), for every `n` |
| 14 | Invalid player counts rejected | Called `SplendorGame(num_players=1)` and `SplendorGame(num_players=5)` | Both raise `ValueError` at construction, not later at `create_initial_state` or mid-match |
| 15 | N-player turn rotation | Played 6 main actions from a fresh 4-player game, recording `current_player` before each | Exactly `player_1, player_2, player_3, player_4, player_1, player_2` -- cycles through every seat in order, wraps correctly |
| 16 | Full-game smoke, 3 and 4 players | Played 6 complete random-vs-random games at each of `num_players in (3, 4)` (same harness as case 1) | All finished (69-166 turns depending on player count), `legal_actions` never empty mid-game |
| 17 | Multi-way winner/reward split | Built a 4-player terminal state with points `[15, 15, 10, 15]` and `owned` card counts `[3, 2, 5, 2]` | `_winners` correctly narrows to the two players tied at 15 points *and* fewest cards (`player_2`, `player_4`) -- the 10-point and 5-card players are excluded, not included in an "everyone splits it" reward; `_determine_winner` returns `None` (still a real tie between those two); `_rewards` splits credit `0.5/0.5` between exactly those two, `0.0` for the other two |
| 18 | GUI renders 2/3/4-player boards, all action types | Drove full/partial games through `SplendorViewer.update_state` at each player count, deliberately forcing `purchase_card`/`reserve_card`/`take_tokens`/`discard_token` actions (not just whatever a random walk produces) | All render without exception; canvas sizes scale sensibly (508x1172 at 2p up to 1460x1172 at 4p) |
| 19 | Market-vs-blind reserved-card visibility split | Had `player_1` reserve one card from the market and one blind off a deck, then called `observe(state, player_2)` | `player_2` sees `reserved_count == 2` for `player_1` but `visible_reserved_cards` has exactly 1 entry (the market one, matching its id, no `source` key present in that view); `observe(state, player_1)`'s own `your_reserved_cards` shows both, correctly tagged `source: "market"` / `source: "deck"` |
| 20 | `source` stripped on purchase | Reserved a card from the market, gave the player exactly enough tokens, then purchased it from `location: "reserved"` | The resulting `owned` entry has no `source` key -- confirms a card's provenance tag only persists while it's actually reserved, not forever after, keeping the owned/market `CardView` shape consistent everywhere else it appears |
| 21 | Invariants hold across full random games | Played 8 complete random-vs-random games at each of `num_players in (2, 3, 4)` (24 games total), asserting after each: every reserved card everywhere carries `source` in `{"market", "deck"}`; no owned card anywhere carries a `source` key; and for every player's `observe()`, every opponent's `len(visible_reserved_cards) <= reserved_count` | All 24 games held every invariant with no exceptions |
| 22 | GUI renders both reserved-card origins | Drove games through `SplendorViewer.update_state` at 2/3/4 players while deliberately alternating market and blind reserves | Both render without exception; blind-origin mini-cards show the `(blind)` tag, market-origin ones don't |

## A note on why this matters (a real bug this process caught)

`gui.py`'s `_draw_players` originally read `player["reserved_count"]` -- a field that
only exists in the *observation* view built by `_player_public_view` for bots, not in
the raw internal `state` the GUI actually receives (`step_observer` in `core/match.py`
passes `event["state"]`, the engine's own state dict, straight to `viewer.update_state`
-- the same thing `battleship/gui.py` reads `state["fleets"]` from directly, not
`observe()`'s output). The raw state's player dict has `"reserved"` (a list of full card
dicts, since it's the engine's own bookkeeping), not a precomputed count.

A quick headless smoke match never would have caught this -- `run-game --mode headless`
never touches `gui.py` at all. It only surfaced because case 12 above deliberately drove
`update_state` with a real state dict, which raised `KeyError: 'reserved_count'`
immediately. The fix: `len(player["reserved"])` instead of the (observation-only) field
name. This is the same category of lesson `battleship/EDGE_CASES.md` and
`connect_four/EDGE_CASES.md` both record: a check has to actually exercise the code path
in question (here: rendering off the *raw engine state's* actual shape) rather than a
shape that merely looks similar.

## A second bug this process caught (multi-player GUI rework)

`gui.py`'s `status_text`/`_describe` originally read `action["points"]` and
`action["bonus"]` off the raw `action` parameter for a `purchase_card` description --
fields that only exist in `StepResult.events` (the *enriched* per-turn event log), not
in the raw action a bot returned. `core/match.py`'s `step_observer` (and therefore
`run-game`'s `_run_gui_game`) passes `event["action"]` -- the plain action dict, e.g.
`{"type": "purchase_card", "location": "market", "tier": 1, "card_id": "t1-02"}` -- to
`viewer.update_state`, never the enriched event.

This one slipped through the *original* GUI verification (case 12, and the "full
played-out game" smoke test before it) because both of those happened to only ever pass
`action=legal_actions[0]`, which is always a `take_tokens` action by construction (see
`_legal_main_actions`'s ordering) -- the `purchase_card` branch of `_describe` was never
actually exercised. It surfaced during the multi-player rework's case 18 stress test,
which deliberately forced `purchase_card` actions through `update_state` and hit
`KeyError: 'points'` immediately. The fix follows the exact precedent already set by
Battleship's `gui.py`: derive the missing detail from the *resulting* `state` instead
(the just-purchased card is always `state["players"][acting_player]["owned"][-1]`) --
`status_text`/`_describe` now take `state` and `acting_player` as extra parameters for
exactly this. The broader lesson, on top of the first bug's: a green smoke test only
proves the *paths it happened to take* are correct -- deliberately exercising every
action type (not just whatever the first legal action or a random walk produces) is
what actually validates a rendering function's full input space.

## Reproducing

These are simple inline scripts against the public `GameProtocol` surface
(`create_initial_state`, `step`, `legal_actions`, `observe`) plus direct calls to a few
internal helpers (`_affordable`, `_apply_reserve`, `_determine_winner`) for the cases
that need to set up a specific mid-game shape faster than playing there through
`step`. For example, case 7 (discard-phase loop):

```bash
uv run python3 -c "
from gamenight.games.splendor.game import SplendorGame
g = SplendorGame()
p1, p2 = g.player_ids
s = g.create_initial_state(seed=6)
s['players'][p1]['tokens'] = {'white':3,'blue':3,'green':3,'red':0,'black':0,'gold':0}
result = g.step(s, {'type': 'take_tokens', 'colors': ['red', 'black']})
print(result.next_state['phase'])  # 'discard'
"
```
