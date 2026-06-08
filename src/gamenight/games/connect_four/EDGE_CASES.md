# Connect Four Edge-Case Verification

`render_text`/`observe`/headless matches are good smoke tests, but they mostly exercise
the "happy path" — a handful of opening moves on an empty board. Rules engines like this
hide bugs in rarely-hit corners (the far diagonal direction, the last cell on the board,
calling `step` one turn too many). Before trusting `game.py`, the following scenarios were
run directly against `ConnectFourGame` (via `create_initial_state` / `step` /
`legal_actions` / the internal `_winner` helper) and confirmed correct:

| # | Edge case | How it was exercised | Result |
|---|---|---|---|
| 1 | Horizontal win | Played `[0,0,1,1,2,2,3]` (red fills bottom row cols 0-3) | `done=True, winner=player_red` |
| 2 | Vertical win | Played `[0,1,0,1,0,1,0]` (red stacks col 0 four times) | `done=True, winner=player_red` |
| 3 | Diagonal "\\" win (down-right) | Hand-built board with `R` at `(2,0),(3,1),(4,2),(5,3)` | `_winner` returns `"R"` |
| 4 | Diagonal "/" win (down-left) | Hand-built board with `R` at `(2,3),(3,2),(4,1),(5,0)` | `_winner` returns `"R"` |
| 5 | Draw detection | Full 42-cell board (21 R / 21 Y) with **no** four-in-a-row in any row, column, or diagonal | `_winner` returns `None` |
| 6 | Column-full legality | Dropped into column 2 six times via natural turn alternation; checked `legal_actions` before/after | Column 2 present in `legal_actions` while open, absent once full; game never ends mid-fill |
| 7 | Gravity / stacking | Two consecutive drops into column 3 | First lands on row 5 (`R`), second stacks on row 4 (`Y`) |
| 8 | Win-on-final-cell precedence | Board one disc from full where the winning drop also fills the last empty cell | `winner=player_red` **and** board reported full — win takes precedence over simultaneous draw |
| 9 | Terminal-state idempotency | Called `step` again on an already-`done` state | Returns the *same* state object unchanged, `done=True` (safe no-op) |
| 10 | Illegal drop into a full column | Called `step` targeting a full column | Raises `ValueError` (documents the contract: callers must only pass `legal_actions`) |

## A note on why this matters (a real near-miss from this verification pass)

While building case 5 (draw detection), a hand-rolled "no winner" board was constructed by
eye and fed to `_winner`. It came back with a winner — `_winner` had correctly spotted an
*accidental* diagonal four-in-a-row that the fixture's author (a human reviewing a 6x7
grid of letters) missed. The fixture was wrong, not the engine. The corrected approach
was to randomly shuffle a valid 21-R/21-Y board until `_winner` confirmed `None`, then use
*that* verified board as the regression fixture.

The lesson generalizes: **don't trust a hand-built "this should have no winner" board
until the engine itself confirms it** — diagonals in particular are easy for a human eye
to miss across a non-trivial grid. This is exactly the kind of trap that case-by-case
edge-case testing (rather than just "play a few games and eyeball the result") catches.

## Reproducing

These checks are simple inline scripts against the public `GameProtocol` surface
(`create_initial_state`, `step`, `legal_actions`) plus the game's own `_winner` helper —
no test framework wiring required:

```bash
uv run python3 -c "
from gamenight.games.connect_four.game import ConnectFourGame
g = ConnectFourGame()
s = g.create_initial_state()
for col in [0, 0, 1, 1, 2, 2, 3]:
    s = g.step(s, {'type': 'drop', 'column': col}).next_state
print(s['done'], s['winner'])  # -> True player_red
"
```
