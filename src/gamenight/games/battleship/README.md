# Battleship: Hidden Information, Two Phases, One Open Contest

Battleship is the first game in this framework with **hidden information** — each side
secretly places a fleet, then takes turns guessing where the other one's ships are.
That single twist changes everything: bots must reason under uncertainty, the engine
must be careful never to leak what a player shouldn't know, and the spectator view gets
to do something neither player can — see the whole board.

![Battleship GUI Preview](assets/gui_preview.svg)

## Research (per `docs/how_to_add_game.md`)

**Is Battleship "solved"?** No. Unlike Tic-Tac-Toe (forced draw under perfect play),
Connect Four (forced first-player win, proven by Allis in 1988), or Checkers (forced
draw, Schaeffer/Chinook 2007), the full two-player adversarial game of Battleship —
secret fleet placement *plus* targeting — has **no proven optimal strategy or known Nash
equilibrium**. What *is* well studied is the single-player search sub-problem: given an
opponent's hidden grid, probabilistic targeting heuristics like "hunt-and-target" and
probability-density-function targeting are well-known to outperform random firing by a
wide margin (this is exactly what `GreedyBot` demonstrates below). That makes Battleship
a genuine **open contest** — there's no fixed, known perfect-vs-perfect outcome ceiling
the way there is for Connect Four, so bot-vs-bot matches stay interesting over time.

**Existing open-source GUI implementations.** A search for `python tkinter battleship
game GUI` turned up roughly eight small candidates — student exercises and weekend hobby
clones, the most-starred at 4 stars, mostly unlicensed or GPL, last touched anywhere from
2016 to 2024, each by a single author. None speak this repo's `GameProtocol` /
`StepResult` / replay / `GameViewerProtocol` contracts, and all of them couple game logic
tightly to bespoke models that would need a full rewrite to slot in here — the same
situation Connect Four's research found. **Decision: build the viewer from scratch**,
following the established `TicTacToeViewer` / `ConnectFourViewer` pattern
(`update_state` / `wait_until_closed` / `close`, lazy `tkinter` import in
`_build_viewer`), investing the extra polish into ship silhouettes and a broadcast-style
"TV view" rather than adapting any of the candidates found.

## Why This Is Great For Game Night

- The placement phase adds real strategy *before* a single shot is fired — cluster your
  fleet for mutual cover, or spread it out so one lucky streak can't reveal everything?
- Hidden information means watching is genuinely suspenseful — the spectator GUI shows
  you both fleets and every shot landing, so you see the near-misses neither bot does.
- "Hunt-and-target" is a clean, well-studied AI idea that's satisfying to implement and
  immediately visible in how much better it plays than firing at random.
- No solved ceiling (see Research above) — bot-vs-bot matchups stay an open contest.

## The Game In One Minute

- Each side secretly places a fleet of 5 ships on a 10x10 grid: carrier (5), battleship
  (4), cruiser (3), submarine (3), destroyer (2) — largest to smallest, one at a time,
  each placed horizontally or vertically with no overlaps and no hanging off the edge.
- `player_blue` places their whole fleet first, then `player_orange` places theirs; once
  both fleets are down, the battle phase begins and `player_blue` fires first.
- Players alternate firing one shot per turn at a cell on the opponent's board — no bonus
  turn for a hit, just like the physical game.
- A shot is a **miss** (open water), a **hit** (lands on an unsunk ship), or a **sunk**
  (the hit was that ship's last unhit cell — and every earlier shot that contributed to
  it is retroactively relabeled with that ship's name, the "you sank my Battleship!"
  reveal moment).
- First player to sink every one of the opponent's 5 ships wins. There are no draws —
  somebody's fleet always eventually goes under.

## What Data Your Bot Gets

Your bot receives an `observation` and a `context` object on every turn. Battleship has
**two phases** and **hidden information**, so the shape is bigger than Connect Four's —
but it always splits cleanly into `public_state` (true for everyone), `private_state`
(only what *you* would know), and `context` (fixed facts about the match).

### Observation — common to both phases

- `public_state.phase`: `"placement"` or `"battle"`
- `public_state.current_player`: whose turn it is right now
- `public_state.turn_index`: turn number (increments every move, either phase)
- `public_state.done` / `public_state.winner`: match status
- `private_state.your_fleet`: your own ships — `name`, `length`, `cells`, `hits`, `sunk`
  — fully known to you, never redacted
- `private_state.your_board`: a 10x10 view of *your own* waters — your ships plus every
  shot the opponent has fired at you (`~`/`S`/`H`/`X`/`M`)
- `private_state.your_shots`: the exact list of shots *you've* fired at the opponent, in
  order, each with a `result` (`"miss"` / `"hit"` / `"sunk"`) and a `ship` name that's
  `null` until the moment you sink that ship — only then does its name appear, and every
  earlier shot that hit it gets retroactively relabeled `"sunk"` too
- `private_state.tracking_grid`: the same shot history as a 10x10 grid for quick lookups
  (`?`/`M`/`H`/`X`)
- `context.opponent_id`, `context.board_size` (`10`), `context.ships` (the fixed fleet,
  name + length, in placement order), `context.next_ship_to_place` (set during your
  placement turns, `null` otherwise)
- `legal_actions`: every legal action for the current phase (see below)

### Action Format

**Placement phase:**

```json
{"type": "place_ship", "ship": "carrier", "row": 4, "col": 2, "orientation": "horizontal"}
```

`legal_actions` enumerates every in-bounds, non-overlapping placement for whichever ship
is next in your fleet order (`context.next_ship_to_place`) — you place ships one at a
time, carrier (5) down to destroyer (2). `(row, col)` is the ship's first cell;
`"horizontal"` extends rightward (same row, increasing column), `"vertical"` extends
downward (same column, increasing row).

**Battle phase:**

```json
{"type": "fire", "row": 3, "col": 7}
```

`legal_actions` enumerates every cell on the opponent's board you haven't already fired
at — `row` and `col` are integers `0`-`9`.

Either way, return exactly one of the dicts already sitting in
`observation["legal_actions"]`.

## Information Policy

This is Battleship's defining feature: **hidden information**. Each side's
`observe(state, player_id)` redacts everything about the *opponent's* fleet that hasn't
been revealed through that player's own confirmed hits — `private_state.your_fleet`
always shows your own ships in full, but the opponent's ship cells never appear anywhere
in your observation, sunk or not. All you ever see of the opponent's board is what your
own `tracking_grid` has discovered, cell by cell, shot by shot.

The spectator GUI is the one place this flips: it's a "TV broadcast" view that shows
*both* fleets fully revealed side by side, plus every shot either side has landed —
the same way a poker broadcast shows the audience both hands face-up while the players
at the table see only their own. Neither bot ever gets that view; only you, watching,
do. (See `gui.py`'s `BattleshipViewer` docstring for more on this design choice — and
note it renders one full board per side rather than the four-grid layout floated during
planning, since a player's fleet and the opponent's incoming shots against it are exactly
what a single board needs to show; doubling that across a separate "tracking" canvas per
side would just repeat the same fleet data from a second angle.)

## Run It Live

Headless quick match:

```bash
uv run gamenight run-game --game battleship --mode headless --bot-1 greedy --bot-2 random --replay-file artifacts/battleship_greedy_vs_random.json
```

GUI match (the "TV view" — open this to actually watch the fleets get revealed and sunk):

```bash
uv run gamenight run-game --game battleship --mode gui --bot-1 greedy --bot-2 random --gui-delay 0.2 --replay-file artifacts/battleship_gui_smoke.json
```

Replay a saved match:

```bash
uv run gamenight replay --replay-file artifacts/battleship_greedy_vs_random.json
```

Large series:

```bash
uv run gamenight run-series --game battleship --bot-a greedy --bot-b random --games 10 --summary-file artifacts/battleship_series_smoke.json
```

## Learn More

- Bot contract: see `BOT_SPEC.md`
- Example inputs/outputs: see `EXAMPLES.md`
- Engine verification: see `EDGE_CASES.md`
- Baseline bots: see `bots/baselines/`
