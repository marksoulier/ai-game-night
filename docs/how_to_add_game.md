# How To Add A Game

1. Create a new directory under `src/gamenight/games/<game_name>`.
2. Implement a game class that follows the shared `GameProtocol`:
   - `game_id: str`
   - `player_ids: list[str]` — e.g. `["player_x", "player_o"]` or
     `["player_red", "player_yellow"]`. The CLI and tournament runner use this (instead
     of hardcoded literals) to discover identities generically, so order matters: index
     `0` is "the first player" / `--bot-1`, index `1` is "the second player" / `--bot-2`.
   - `create_initial_state`
   - `current_player`
   - `legal_actions`
   - `observe`
   - `step`
   - `render_text`
   - `build_baseline_bot(self, name: str, bot_id: str) -> BotProtocol` — resolves names
     like `"random"` / `"greedy"` / `"human"` to *this game's own* bot classes under
     `bots/baselines/`, raising `ValueError` for unknown names. This keeps game-specific
     baseline choices inside the game module rather than the CLI importing each game's
     bots directly (see `infrastructure.agent.md`'s "keep game-specific rules inside game
     modules" guardrail).
3. Add game-specific bot docs:
   - `BOT_SPEC.md`
   - `EXAMPLES.md`
   - `prompts/greedy_bot_prompt.md`
4. Register the game in `src/gamenight/games/__init__.py`.
5. (Optional, only if you ship a GUI) Add a `gui.py` viewer implementing
   `GameViewerProtocol` (`update_state`, `wait_until_closed`, `close` — see
   `core/protocols.py` and either existing `gui.py` for the exact shape), then register
   it in `_build_viewer` in `src/gamenight/cli/main.py` so `--mode gui` can find it. GUI
   imports must stay lazy (import inside the branch) so `tkinter` remains an optional
   dependency for headless-only games.

## Game Folder Template

```
src/gamenight/games/<game_name>/
  game.py
  gui.py              # optional — only if the game ships a GUI viewer
  BOT_SPEC.md
  EXAMPLES.md
  prompts/
    greedy_bot_prompt.md
  bots/
    baselines/
    players/
  assets/
    gui_preview.svg   # optional — only if the game ships a GUI viewer
```

## Verifying A New Game Engine

Headless smoke matches (`run-game`, `run-series`) only exercise whatever moves the bots
you happen to pick make — they're necessary but not sufficient. Rules engines reliably
hide bugs in the corners that ordinary play rarely reaches: a direction that was never
tested, the very last cell on the board, calling a method one time too many. Before
considering a new (or modified) `game.py` done, write a small, throwaway script that
calls `create_initial_state` / `step` / `legal_actions` directly and walks it through the
edge cases that matter for *that* game's rules — at minimum:

- **Every win condition / direction** the rules define (e.g. all four "in a row"
  orientations for a connection game). It's common to implement one orientation and
  silently miss its mirror.
- **Boundary and "board full" conditions** — the action space shrinking correctly as the
  board fills, and the engine handling the very last legal move without surprises.
- **Terminal-state precedence** — when a final move could simultaneously trigger two
  outcomes (e.g. a win *and* a full board), confirm the engine resolves it the way your
  rules intend, not by accident of check ordering.
- **Terminal-state idempotency** — calling `step` again after `done=True` should be a
  safe no-op, not a crash or silent corruption, so a runner that calls it once too many
  times can't break the result.
- **Don't trust hand-built fixtures blindly.** A "this board has no winner" fixture you
  construct by eye can easily contain an accidental win you didn't notice (diagonals are
  the classic culprit on larger boards) — verify the fixture against the engine itself
  (e.g. assert your win-checker returns `None` on it) before relying on it as a
  regression test. `games/connect_four/EDGE_CASES.md` walks through a real instance of
  this happening during that game's development, including how it was caught and fixed.

Once you've found a set of cases and fixtures that pass, write them down in the game's own
docs (see `games/connect_four/BOT_SPEC.md`'s "Verifying A New Implementation" section and
`games/connect_four/EDGE_CASES.md` for the pattern to follow) — that record is what lets a
future change to the engine be checked against the same bar.
