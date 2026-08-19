# Mine Duel Edge-Case Verification

`render_text`/`observe`/headless matches are good smoke tests, but they mostly exercise
the "happy path." Before trusting `game.py`, the following scenarios were run directly
against `MineDuelGame` (via `create_initial_state`/`step`/`legal_actions`) and confirmed
correct. Reproduce all of them at once with the script at the bottom.

| # | Edge case | How it was exercised | Result |
|---|---|---|---|
| 1 | Exact mine count | Built initial state for 200 different seeds, counted `cell["mine"] == True` | Always exactly `MINE_COUNT` (40) |
| 2 | Center-cell safety guarantee | Same 200 seeds, checked the center cell (`ROWS//2, COLS//2`) | Never a mine, always pre-revealed by the neutral bootstrap |
| 3 | Adjacency counts | Brute-forced every non-mine cell's 8-neighbor mine count by hand for one seed, compared to `cell["adjacent"]` | Matched at every cell |
| 4 | Mine-hit scoring/turn-passing | Stepped into a known mine cell | Score drops by exactly `MINE_PENALTY` (1), `safe_remaining` unchanged, cell flips to revealed+public, turn passes to the opponent, the cell drops out of `legal_actions` |
| 5 | Illegal re-reveal | Called `step` again targeting an already-revealed cell | Raises `ValueError` (documents the contract: callers must only pass `legal_actions`) |
| 6 | Flood-fill cascade correctness | Found a `0`-value cell, revealed it | All connected `0`s plus their numbered border come back in one action; score gain and `safe_remaining` drop both equal exactly the number of cells revealed; no mine is ever auto-revealed by the cascade |
| 7 | Terminal precedence | Played a full random game to completion | Ends the instant `safe_remaining` hits 0 (mid-cascade counts), `winner` matches a direct score comparison |
| 8 | Terminal-state idempotency | Called `step` again on an already-`done` state | Returns the *same* state object unchanged, `done=True` (safe no-op) |
| 9 | Legal-action gating | Checked `legal_actions` for the non-current player, and for anyone once `done` | Empty in both cases |
| 10 | `max_turns` headroom at Medium size | `run_match`'s default cap is 200 turns (`core/match.py`), unconfigurable from the CLI. On the 18x14/40-mine board, a game where every reveal opened exactly 1 cell (no cascades ever) would need up to 252 turns -- over the cap. Ran 500 RandomBot-vs-RandomBot games (the least cascade-seeking, highest-variance pairing) uncapped and took the max | Worst of 500 was 171 turns -- safely under 200 in practice, since real play (random or otherwise) reliably triggers cascades on a ~16%-density board. Flagged here rather than silently trusted, since it's a real cap that a sufficiently unlucky/adversarial sequence could theoretically hit |

## The first-move bias this caught (worth understanding before you tune the rules)

Early builds of this engine let `player_ember` (seat 1) take the very first reveal on
a *completely* blank board. Measuring `RandomBot` vs `RandomBot` over 1,000 games
showed seat 1 winning ~57.5% of the time with an average score margin of **+8.2**
points — far too large to be first-move noise on a game whose final scores average
only ~30 points a side.

The cause: a reveal's expected value depends entirely on how much untouched board is
still available to cascade into, and the very first reveal of the game — by
construction, always seat 1's — happens when the *whole* 71-cell board is intact. Over
1,000 games, that one guaranteed turn averaged **13.5 points** by itself (vs. ~1.6-1.9
for every other turn in the game) — bigger than the entire final-score gap it caused.
This is a real, well-documented property of Minesweeper (the first click is usually
the biggest cascade of the game), but it's harmless in solitaire play and became a
structural, skill-independent seat advantage the moment the game went competitive.

**Fix**: `create_initial_state` now reserves the center cell so it can never be a
mine, and reveals it (with a flood cascade, same as any other reveal) *before* either
player's first turn, crediting the points to nobody (`revealed_by=None`). Both
players' actual first turns now start from a partially-opened board instead of one of
them getting the one guaranteed jackpot click.

Re-measuring after the fix (2,000 games at the time, on what was then a 9x9/10-mine
board — this section originally measured that size; see the "Resized to Google's
Medium" note below for why the numbers here now describe a board that no longer
exists):

| Matchup | Seat 1 wins | Seat 2 wins | Draws | Avg score margin (seat 1 − seat 2) |
|---|---|---|---|---|
| random vs random | 1095 (54.8%) | 864 | 41 | +4.71 |
| greedy vs random | 1433 (71.7%) | 547 | 20 | +14.53 |
| random vs greedy | 808 (40.4%) | 1174 (58.7%) | 18 | −3.66 |
| greedy vs greedy | 1284 (64.2%) | 665 | 51 | +11.19 |

A residual seat-1 edge remains (the first reveal *after* the neutral opening is still
statistically the most valuable turn left, just no longer an outlier) — comparable in
kind to Connect Four's proven first-player advantage, and exactly what
`core/bracket.py`'s `_FirstMoveBalancer` exists to neutralize across a series (see
`docs/ARCHITECTURE.md`'s "Tournament Fairness" section): it's a `run-series`/
`run-bracket` concern, not something a single game's rules need to fully erase. What
the fix actually needed to guarantee is the thing the "before" column shows missing:
**GreedyBot's real skill edge is now visible even from the disadvantaged seat** — as
seat 2 (`random vs greedy` above), GreedyBot still won the majority of the time
despite the structural seat-2 disadvantage. Before the fix, GreedyBot's mine-avoidance
skill (it hit mines roughly 10x less often than RandomBot in a direct comparison)
barely moved the win rate at all — the turn-1 jackpot noise was swamping the skill
signal completely.

## Resized to Google Minesweeper's "Medium" (18x14, 40 mines)

The board was later resized from the original custom 9x9/10-mine layout to match
Google's own Minesweeper at "Medium" difficulty (see `README.md`'s Research section).
Everything above (mine-count-exclusion of the center cell, the neutral bootstrap
opening, the fix itself) is size-agnostic in the implementation — `create_initial_state`
computes the center from `ROWS`/`COLS` rather than hardcoding `(4, 4)` — so no rule
changed, only the constants. Re-ran the same edge-case suite (all pass) and a fresh,
smaller-sample balance check to confirm the fix still holds at the new size (500
games/matchup, `random.seed(20260819)`):

| Matchup | Seat 1 wins | Seat 2 wins | Draws | Avg score margin (seat 1 − seat 2) |
|---|---|---|---|---|
| random vs random | 255 (51.0%) | 242 (48.4%) | 3 | +3.71 |
| greedy vs random | 369 (73.8%) | 127 (25.4%) | 4 | +45.36 |
| random vs greedy | 149 (29.8%) | 346 (69.2%) | 5 | −35.50 |
| greedy vs greedy | 295 (59.0%) | 203 (40.6%) | 2 | +11.12 |

Both findings hold at the new size: the seat-1 edge in a random-vs-random game stays
small (51.0% — essentially a coin flip, well within normal series-level variance), and
GreedyBot's skill edge is, if anything, even clearer than at the smaller size —
winning 69.2% of the time even from the structurally worse seat. A bigger board gives
its single-constraint deduction more numbered clues to reason from per game, which
tracks: more information to work with should make a deduction-based bot's advantage
*more* visible, not less.

## Reproducing

```bash
uv run python3 -c "
from gamenight.games.mine_duel.game import MineDuelGame, ROWS, COLS, MINE_COUNT

g = MineDuelGame()
p1, p2 = g.player_ids

# Case 4: mine-hit scoring/turn-passing
s = g.create_initial_state(seed=1)
mine_cell = next((r, c) for r in range(ROWS) for c in range(COLS) if s['cells'][r][c]['mine'])
before = s['scores'][p1]
s2 = g.step(s, {'type': 'reveal', 'row': mine_cell[0], 'col': mine_cell[1]}).next_state
print(s2['scores'][p1] == before - 1, s2['current_player'] == p2)  # -> True True

# Case 2: center is never a mine, and starts pre-revealed
print(not s['cells'][ROWS // 2][COLS // 2]['mine'])  # -> True
"
```

The full check suite (all nine cases above) lives as a throwaway script during
development — the table and the bias write-up here are the durable record, per
`docs/how_to_add_game.md`'s verification workflow.
