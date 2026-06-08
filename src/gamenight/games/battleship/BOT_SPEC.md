# Battleship Bot Spec

This document defines the exact bot interface for Battleship.

## Bot Class Contract

Implement class `PlayerBot` with methods:

- `reset(context)`
- `choose_action(observation, context)`

## Observation Object

Battleship has **two phases** (`"placement"` then `"battle"`) and **hidden information**
— `observation` always has the same top-level shape, but some fields are only meaningful
in one phase or the other (noted below).

`public_state` — true for everyone, never redacted:

- `phase`: `"placement"` or `"battle"`
- `current_player`: `"player_blue"` or `"player_orange"` — whose turn it is right now
- `turn_index`: integer turn count, incremented every move in either phase
- `done`: bool
- `winner`: `"player_blue"`, `"player_orange"`, or `null`

`private_state` — only what *you* would know, the redacted half:

- `your_fleet`: list of your own ships, each `{"name": ..., "length": ..., "cells":
  [[r, c], ...], "hits": [[r, c], ...], "sunk": bool}` — fully known to you, never
  redacted, and updated live as the opponent lands hits on you
- `your_board`: a 10x10 grid (`list[list[str]]`, row 0 = top) of your own waters — your
  ships plus every shot the opponent has fired at you. Symbols: `~` empty water, `S`
  your ship undamaged, `H` your ship hit (not yet sunk), `X` your ship hit and sunk,
  `M` opponent fired here and missed
- `your_shots`: the exact list of shots *you* have fired at the opponent, in order —
  each `{"row": r, "col": c, "result": "miss"|"hit"|"sunk", "ship": name|null}`. `ship`
  is `null` for `"miss"` and `"hit"` results — it's filled in with the opponent's ship
  name *only* once that ship sinks, at which point every earlier shot of yours that
  contributed to it is retroactively relabeled `"sunk"` with that name too (mirrors the
  real game's "you sank my Battleship!" reveal — a plain `"hit"` never tells you which
  ship you found)
- `tracking_grid`: the same shot history as a 10x10 grid (row 0 = top) for quick `(r,
  c)` lookups. Symbols: `?` you haven't fired here, `M` miss, `H` hit (ship not yet
  identified), `X` hit and sunk

`context` — fixed facts about the match:

- `opponent_id`: the other player's id
- `board_size`: `10`
- `ships`: the fixed fleet every player places, in order — `[{"name": "carrier",
  "length": 5}, {"name": "battleship", "length": 4}, {"name": "cruiser", "length": 3},
  {"name": "submarine", "length": 3}, {"name": "destroyer", "length": 2}]`
- `next_ship_to_place`: the ship name you must place next (set only during *your*
  placement turns; `null` the rest of the time, including during your opponent's
  placement turns and throughout the battle phase)

`legal_actions`: every legal action for the current phase — see Action Schema.

## Action Schema

**Placement phase** — one ship at a time, in fixed fleet order (carrier first,
destroyer last):

```json
{"type": "place_ship", "ship": "carrier", "row": 4, "col": 2, "orientation": "horizontal"}
```

`ship` must match `context.next_ship_to_place`. `(row, col)` is the ship's *first* cell —
`"horizontal"` extends rightward from there (same row, increasing column),
`"vertical"` extends downward (same column, increasing row). `legal_actions` enumerates
every placement that's fully in-bounds and doesn't overlap a ship you've already placed —
illegal placements (off the board, overlapping) simply never appear in the list.

**Battle phase** — one shot per turn, no bonus turn for a hit:

```json
{"type": "fire", "row": 3, "col": 7}
```

`row` and `col` are integers `0`-`9`. `legal_actions` enumerates every cell on the
opponent's board you haven't already targeted — a cell you've already fired at is
removed from the list and re-submitting it raises `ValueError` (see Edge Cases below).

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

- Read hidden/off-spec information — in particular, there is no field anywhere in your
  `observation` that reveals the opponent's ship positions before your own shots have
  confirmed them. Looking for one is a sign something's gone wrong with your bot, not a
  sign the engine forgot to redact.
- Edit baseline bots or other players' folders.
- Change shared core infrastructure for player-bot tasks.

## FAQ

### Can I create more than one bot?

Yes. One folder equals one bot identity.

For example:

- `players/alex/bot.py` -> `player:alex`
- `players/alex_v2/bot.py` -> `player:alex_v2`

### How do I run my bot?

```bash
uv run gamenight run-game --game battleship --mode headless --bot-1 player:<your_bot_name> --bot-2 random
```

## Verifying A New Implementation (For Game Authors)

If you're modifying `game.py` (not just writing a player bot), don't rely on a handful of
headless matches to convince yourself the rules are right — and Battleship's hidden
information makes this *more* true than for a perfect-information game like Connect Four,
not less: a leak in `observe()` won't show up in `render_text` or a casual playthrough at
all, only in a deliberate "does this redact correctly" check. Before calling an
implementation done, exercise these directly against the engine (`create_initial_state`
/ `step` / `legal_actions` / `observe`):

- **Placement order, hand-off, and phase flip**: a player must place all 5 ships in
  fixed fleet order (carrier through destroyer) before play passes to the opponent, and
  the phase must flip from `"placement"` to `"battle"` only once *both* fleets are
  down — with `player_blue` firing first.
- **Out-of-bounds and overlap rejection**: a placement that would run off the board, or
  overlap a ship already placed, must never appear in `legal_actions` — not be silently
  accepted and corrupt the fleet.
- **Hidden-information leakage**: this is the corner the engine can least afford to get
  wrong. Confirm `observe(state, "player_blue")["private_state"]` never contains any
  cell of `player_orange`'s fleet (and vice versa) — not in `tracking_grid` (must show
  `"?"` everywhere you haven't fired), not anywhere in the JSON. The opponent's id itself
  shouldn't even need to appear in your `private_state`.
- **Re-firing an already-targeted cell is illegal**: the cell must disappear from
  `legal_actions` after you fire there, and resubmitting it must raise — not silently
  double-record the shot and corrupt `state["shots"]` (double damage, wrong turn count,
  broken redaction grids).
- **Hit -> sunk -> retroactive reveal -> all-sunk win precedence**: sinking a ship must
  retroactively relabel every one of your shots that contributed to it as `"sunk"` with
  that ship's name — and sinking the *opponent's last unsunk ship* must end the game
  (`done=True`, `winner=<you>`) in that same step, with no ambiguity about whose turn
  comes next.
- **Terminal-state idempotency**: calling `step` again on an already-`done` state must
  be a safe no-op (`legal_actions` empty for both players, `step` returns the same
  state unchanged).

These exact checks (with passing fixtures, including a real bug this process caught) are
recorded in `EDGE_CASES.md`.
