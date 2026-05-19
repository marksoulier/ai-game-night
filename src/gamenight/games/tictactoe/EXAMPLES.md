# Tic-Tac-Toe Examples

## Example Observation

```json
{
  "public_state": {
    "board": ["X", "O", " ", " ", "X", " ", " ", " ", "O"],
    "current_player": "player_x",
    "turn_index": 5,
    "done": false,
    "winner": null
  },
  "private_state": {
    "marker": "X"
  },
  "context": {
    "opponent_id": "player_o",
    "board_size": 3,
    "win_length": 3
  },
  "legal_actions": [
    {"type": "place", "index": 2},
    {"type": "place", "index": 3},
    {"type": "place", "index": 5},
    {"type": "place", "index": 6},
    {"type": "place", "index": 7}
  ]
}
```

## Example Output Action

```json
{"type": "place", "index": 2}
```
