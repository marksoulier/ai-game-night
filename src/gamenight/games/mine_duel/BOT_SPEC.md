# Mine Duel Bot Spec

This document defines the exact bot interface for Mine Duel.

## Bot Class Contract

Implement class `PlayerBot` with methods:

- `reset(context)`
- `choose_action(observation, context)`

## The Game In Short

A shared 18x14 Minesweeper board (Google Minesweeper's "Medium" size), 40 hidden
mines. Two players alternate revealing one cell at a time. A safe reveal scores you 1 point per cell it uncovers (a `0`-value
cell cascades outward like classic Minesweeper, so one action can uncover — and
score — many cells at once). A mine costs you 1 point and ends your turn immediately.
The match ends the instant every safe cell has been found; whoever has the higher
score wins (equal scores is a draw). See `../../README.md` for the full ruleset,
including why the board opens with one cell already revealed for free.

## Information Policy

**Mine Duel has no hidden information relative to your opponent.** Unlike Battleship
(each player has a private fleet) there is nothing here that's "yours" and not
"theirs" — the mine layout is unknown to both of you equally, and it's random world
state, not a secret either side holds. `observation["private_state"]` is always `{}`
for exactly this reason; everything you need lives in `public_state` and `context`.

## Observation Object

`public_state` — true for everyone, never redacted:

- `current_player`: `"player_ember"` or `"player_frost"` — whose turn it is right now
- `turn_index`: integer turn count, incremented every reveal
- `done`: bool
- `winner`: `"player_ember"`, `"player_frost"`, or `null` (`null` covers both "still
  playing" and "ended in a tied score")
- `scores`: `{"player_ember": int, "player_frost": int}` — can go negative (mine
  penalties)
- `safe_cells_remaining`: how many safe cells nobody has found yet (game ends at 0)
- `board`: a `rows` x `cols` grid (`list[list[str]]`, row 0 = top) of what's been
  found so far. Symbols: `"?"` still hidden, `"0"`-`"8"` a revealed safe cell (its
  value = how many of its 8 neighbors are mines), `"M"` a revealed mine
- `owner_grid`: a grid of the same shape as `board`, of which player revealed each cell —
  `"player_ember"`, `"player_frost"`, or `null`. `null` means either "still hidden" or
  "revealed by the neutral opening" — check `board`'s symbol at that cell to tell
  which (if `board[r][c] != "?"` and `owner_grid[r][c]` is `null`, it's the free
  opening cell, not a hidden one). Purely cosmetic/spectator information — it never
  tells you where a *hidden* mine is, so reading it is not an information leak.

`private_state` — always `{}`. See "Information Policy" above.

`context` — fixed facts about the match:

- `opponent_id`: the other player's id
- `rows`, `cols`: `14`, `18` — Google Minesweeper's "Medium" board size
- `mine_count`: `40`
- `total_safe_cells`: `212`
- `mine_penalty`: `1` — points lost for revealing a mine

## Legal Actions

Every still-hidden cell is a legal action:

```json
{"type": "reveal", "row": 3, "col": 7}
```

`row` is `0`-`13`, `col` is `0`-`17` (always `0` to `context["rows"]-1` /
`context["cols"]-1` — read those rather than hardcoding, in case the board size ever
changes again). `legal_actions` shrinks by at least one cell every turn (a flood-fill
reveal removes several at once) and is empty once the match is `done` or when it
isn't your turn.

## What You Must Return

Exactly one of the dicts already sitting in `observation["legal_actions"]`. If your
preferred action isn't legal, fall back to any legal action — never construct one by
hand from `row`/`col` you computed yourself, since it must match an entry in that list.

## Verifying A New Implementation

Before trusting a change to `game.py`, walk it through (at minimum) the cases in
`EDGE_CASES.md`: mine-hit scoring and turn-passing, flood-fill cascade correctness
(scores exactly the number of cells it reveals, never auto-reveals a mine), terminal
precedence (`safe_cells_remaining` hitting 0 ends the match immediately, even
mid-cascade), and `step`/`legal_actions` idempotency once `done`.
