# Connect Four Examples

## Example Observation

```json
{
  "public_state": {
    "board": [
      " ", " ", " ", " ", " ", " ", " ",
      " ", " ", " ", " ", " ", " ", " ",
      " ", " ", " ", " ", " ", " ", " ",
      " ", " ", " ", "R", " ", " ", " ",
      " ", " ", " ", "Y", " ", " ", " ",
      " ", " ", "R", "R", "Y", " ", " "
    ],
    "current_player": "player_yellow",
    "turn_index": 5,
    "done": false,
    "winner": null
  },
  "private_state": {
    "marker": "Y"
  },
  "context": {
    "opponent_id": "player_red",
    "columns": 7,
    "rows": 6,
    "win_length": 4
  },
  "legal_actions": [
    {"type": "drop", "column": 0},
    {"type": "drop", "column": 1},
    {"type": "drop", "column": 2},
    {"type": "drop", "column": 3},
    {"type": "drop", "column": 4},
    {"type": "drop", "column": 5},
    {"type": "drop", "column": 6}
  ]
}
```

The `board` is flat and indexed `row * 7 + col`, with row `0` at the top and row `5` at
the bottom. In this example, five discs have landed in the bottom-center of the board:
red has built a small foothold at columns 2 and 3 (with one more red stacked above at
column 3), and yellow has answered by stacking on top in columns 3 and 4. Every column is
still open — gravity means a column only drops out of `legal_actions` once its top cell
(row `0`) is filled.

## Example Output Action

```json
{"type": "drop", "column": 3}
```

`column` must be one of the values present in `legal_actions` (an integer `0`-`6`). The
engine decides which row the disc lands on — you cannot pick a row directly.
