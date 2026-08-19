# Mine Duel Examples

One complete worked example, captured directly from the engine (seed `3`, on the
18x14/40-mine "Medium" board) after three reveals: `player_ember` opened `(0,0)` — a
big flood-fill cascade, worth 35 points in one action — then `player_frost` opened
`(13,17)` (a lone `1` in the far corner), then `player_ember` opened `(6,6)`, a lone
`1` sitting just outside the cascade region (not connected to it — that's why it
needed its own separate reveal instead of coming along for free). It's
`player_frost`'s turn next.

```json
{
  "public_state": {
    "current_player": "player_frost",
    "turn_index": 3,
    "done": false,
    "winner": null,
    "scores": {"player_ember": 36, "player_frost": 1},
    "safe_cells_remaining": 174,
    "board": [
      ["0","0","1","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?"],
      ["0","1","2","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?"],
      ["0","1","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?"],
      ["0","1","1","1","?","?","?","?","?","?","?","?","?","?","?","?","?","?"],
      ["0","0","0","1","?","?","?","?","?","?","?","?","?","?","?","?","?","?"],
      ["0","0","0","1","?","?","?","?","?","?","?","?","?","?","?","?","?","?"],
      ["0","0","0","1","1","?","1","?","?","?","?","?","?","?","?","?","?","?"],
      ["0","0","0","0","1","?","?","?","?","1","?","?","?","?","?","?","?","?"],
      ["1","2","2","1","1","?","?","?","?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?"],
      ["?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","?","1"]
    ],
    "owner_grid": [
      ["player_ember","player_ember","player_ember",null,null,null,null,null,null,null,null,null,null,null,null,null,null,null],
      ["player_ember","player_ember","player_ember",null,null,null,null,null,null,null,null,null,null,null,null,null,null,null],
      ["player_ember","player_ember",null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null],
      ["player_ember","player_ember","player_ember","player_ember",null,null,null,null,null,null,null,null,null,null,null,null,null,null],
      ["player_ember","player_ember","player_ember","player_ember",null,null,null,null,null,null,null,null,null,null,null,null,null,null],
      ["player_ember","player_ember","player_ember","player_ember",null,null,null,null,null,null,null,null,null,null,null,null,null,null],
      ["player_ember","player_ember","player_ember","player_ember","player_ember",null,"player_ember",null,null,null,null,null,null,null,null,null,null,null],
      ["player_ember","player_ember","player_ember","player_ember","player_ember",null,null,null,null,null,null,null,null,null,null,null,null,null],
      ["player_ember","player_ember","player_ember","player_ember","player_ember",null,null,null,null,null,null,null,null,null,null,null,null,null],
      [null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null],
      [null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null],
      [null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null],
      [null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null],
      [null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,"player_frost"]
    ]
  },
  "private_state": {},
  "context": {
    "opponent_id": "player_ember",
    "rows": 14,
    "cols": 18,
    "mine_count": 40,
    "total_safe_cells": 212,
    "mine_penalty": 1
  }
}
```

Reading this:

- `player_ember`'s score is `36`: the `(0,0)` cascade alone opened 35 connected cells
  (everything from row 0 down through row 8, cols 0-4ish — every `0` and its
  numbered border, all revealed and scored in that one action), plus `+1` for the
  separate lone `1` at `(6,6)`. `player_frost`'s score is `1`, from their single `(13,17)`
  reveal clear across the board.
- Notice `(6,6)` is a `"1"` sitting right next to the cascade (row 6) but separated
  from it by a still-hidden `"?"` at `(6,5)` — it wasn't swept up by the `(0,0)`
  cascade because it isn't *connected* through any `0`-value cell, so it needed its
  own separate turn to reveal even though it's spatially close.
- `owner_grid` shows every one of those 36 revealed-and-scored cells tracing back to
  `player_ember`, and the single `(13,17)` cell tracing to `player_frost` — spectator
  color-coding only, never a hint about where a still-hidden mine is.
- There's a 38th revealed cell neither score accounts for: `(7,9)`, the `"1"` at the
  center of the board (`ROWS//2, COLS//2` for this 14x18 board). Its `owner_grid`
  entry is `null` even though `board[7][9] != "?"` — that combination (revealed, but
  `null` owner) is exactly how you tell "the free neutral opening" apart from "still
  hidden" (which is also `null`, but shows `"?"` on `board`). See `BOT_SPEC.md`'s note
  on `owner_grid` and `README.md`'s "Game In One Minute" for why this cell opens for
  free before anyone's first turn.
- No mine has been triggered yet in this example, so `board` has no `"M"` cells.
  `legal_actions` (appended by the match runner, not shown above — 214 entries here:
  252 cells minus the 38 already revealed) is just every remaining
  `{"type": "reveal", "row": r, "col": c}`.

Sample legal action from this position: `{"type": "reveal", "row": 0, "col": 3}`.
