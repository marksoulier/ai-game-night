# Battleship Edge-Case Verification

`render_text` / `observe` / headless matches are good smoke tests, but Battleship raises
the stakes on "good smoke tests aren't enough": it's the first game in this framework
with **hidden information**, and a redaction bug won't show up in a casual playthrough at
all — `render_text` shows the full omniscient state on purpose, so a leak in `observe()`
would sail straight through it unnoticed. Before trusting `game.py`, the following
scenarios were run directly against `BattleshipGame` (via `create_initial_state` /
`step` / `legal_actions` / `observe` / `render_text`) and confirmed correct:

| # | Edge case | How it was exercised | Result |
|---|---|---|---|
| 1 | Placement order, hand-off, phase flip | Placed all 5 ships for `player_blue` (horizontal, spread across rows 0-4), confirmed `current_player` flips to `player_orange`; placed all 5 for `player_orange` (vertical, spread across cols 0-4), confirmed `phase` flips `"placement"` -> `"battle"` with `player_blue` firing first | All three transitions correct: mid-fleet turn stays put, hand-off after 5th ship, phase flip only after *both* fleets complete |
| 2 | Out-of-bounds & overlap rejection | Checked that a carrier (length 5) at `row=0, col=6` horizontal (would run to col 10) and at `row=9, col=0` vertical (would run to row 13) never appear in `legal_actions`; placed a carrier at `(0,0)` horizontal, then confirmed a battleship at `(0,2)` horizontal (would overlap cols 2-4) is absent from the next `legal_actions` | Neither illegal placement ever appears — `legal_actions` only ever enumerates placements that are simultaneously in-bounds *and* non-overlapping |
| 3 | Hidden-information leakage | Took a state with both fleets fully placed (battle about to start) and called `observe(state, "player_blue")`; asserted `tracking_grid` is all `"?"` (no shots fired yet, so zero opponent info should be visible), `private_state["your_fleet"]` contains only `player_blue`'s own ships, and serialized the entire `private_state` to JSON to confirm `"player_orange"` (the opponent's id) doesn't appear anywhere inside it | Zero leakage: no orange ship cell, no orange fleet data, not even the opponent's id string, appears anywhere in blue's `private_state` |
| 4a | Re-firing an already-targeted cell is illegal | Fired `{"row": 0, "col": 0}`, let the opponent reply, then confirmed that exact action is no longer in `legal_actions`, and that calling `step` with it again raises | `legal_actions` correctly excludes it; `step` raises `ValueError` rather than silently double-recording the shot (see "near-miss" below — this guard didn't exist on the first pass) |
| 4 | Hit -> sunk -> retroactive reveal -> all-sunk win precedence | Sank `player_orange`'s vertical carrier (col 0, rows 0-4) cell by cell, checking each `step`'s event: `"hit"` for shots 1-4, `"sunk"` with `"ship": "carrier"` for shot 5; then confirmed all 5 of blue's shots at those cells now read `result="sunk", ship="carrier"` in `observe`. Continued the match to completion (sinking all 5 orange ships) | Retroactive relabeling confirmed exact — all 5 contributing shots flip to `"sunk"`/`"carrier"` simultaneously; match ends with `done=True, winner=player_blue`, all 5 orange ships `sunk=True`, in 23 battle turns |
| 6 | Terminal-state idempotency | Called `step` again on the finished (`done=True`) state from case 4 with an arbitrary action | Returns the *same* state object unchanged, `done=True`; `legal_actions` returns `[]` for both players |
| 7 | `render_text` across every state shape | Called `render_text` on a fresh placement-phase state, a mid-battle state, and the finished state from case 4 | Renders cleanly end-to-end for all three shapes — placement (empty boards + status line), mid-battle (ships + hit/miss marks both sides), and finished (winner line + final boards) |

## A note on why this matters (a real near-miss from this verification pass)

Case 4a started life as a much weaker check: "fire at an already-targeted cell on a
*finished* (`done=True`) state and confirm `legal_actions` is empty." That passed —
trivially, because `legal_actions` returns `[]` for *any* action on a terminal state,
regardless of shot history. It was testing the terminal-state guard, not the
duplicate-shot guard, and would have stayed green even if duplicate shots were silently
accepted mid-game.

Rewriting it as a *mid-game* check — fire at a cell, let the opponent reply, then try
firing at that same cell again — immediately surfaced a real bug: `_apply_shot` had **no
validation against duplicate shots**. It would silently append a second shot record to
`state["shots"][player_id]`, double-counting damage against the target ship (potentially
sinking it early on a phantom second hit), incrementing `turn_index` an extra time, and
corrupting the redaction grids (`tracking_grid` would show whichever record happened to
be scanned last). None of that would be visible in a casual headless playthrough — bots
only ever submit actions from `legal_actions`, which already excludes the cell, so the
bug could only be triggered by a malformed or malicious action, exactly the kind of input
`step` should reject rather than silently corrupt state over.

The fix mirrors a precedent already established in `connect_four/game.py`'s
`_landing_row` (documented in `connect_four/EDGE_CASES.md` case 10: "Illegal drop into a
full column... raises `ValueError`... documents the contract: callers must only pass
`legal_actions`") — `_apply_shot` now raises `ValueError` on a duplicate target, with the
same message shape, before it touches any state.

The lesson generalizes from Connect Four's "don't trust a hand-built fixture" finding to
something a step earlier: **don't trust a weak assertion just because it passes** — if a
check would also pass against a deliberately-broken implementation (here: "duplicate
shots silently accepted"), it isn't actually checking the thing you think it is. Rewrite
it until it's capable of failing against the bug you're worried about, *then* trust a
green result.

## Reproducing

These checks are simple inline scripts against the public `GameProtocol` surface
(`create_initial_state`, `step`, `legal_actions`, `observe`, `render_text`) — no test
framework wiring required:

```bash
uv run python3 -c "
from gamenight.games.battleship.game import BattleshipGame
g = BattleshipGame()
s = g.create_initial_state()
first_id, second_id = g.player_ids

# Fire blue's first shot, let orange reply, then try to re-fire the same cell.
shot = {'type': 'fire', 'row': 0, 'col': 0}
# (after both fleets are placed and battle phase has begun)
print('legal before:', shot in g.legal_actions(s, first_id))
"
```

(The full placement-through-battle walkthrough used to produce the table above is ~150
lines — see the case-by-case structure described in the table; each row corresponds to
one assertion block run directly against a fresh `create_initial_state()`.)
