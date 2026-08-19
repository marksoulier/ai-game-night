# Mine Duel: Minesweeper, But Someone Else Is Also Clicking

Mine Duel takes classic solitaire Minesweeper and turns it into a head-to-head contest:
one shared 18x14 board (Google Minesweeper's "Medium" size), 40 hidden mines, two
players alternating single reveals. A safe click scores you a point for every cell it
uncovers — including the classic flood-fill cascade off a `0` — and a mine costs you
a point and hands the turn over.
Whoever has more points once the board is fully cleared wins. It's the first game in
this framework where **nothing is private to either player** — the uncertainty is
about the world (where the mines are), not about your opponent.

## Research (per `docs/how_to_add_game.md`)

**Is Mine Duel "solved"?** The ruleset here — shared-board, alternating-turn, scored
reveal with flood-fill — is a custom design built for this repo; nothing with this
exact rule set exists to be "solved" or not. What *is* a real, citable result is about
classic single-player Minesweeper's core sub-problem: Richard Kaye proved in 2000
("Minesweeper is NP-complete," *The Mathematical Intelligencer* 22(2), pp. 9-15) that
deciding whether a *given* partially-revealed Minesweeper board is logically
consistent (i.e., whether some valid mine arrangement matches every visible clue) is
NP-complete, by simulating logic-gate circuits out of mine configurations. That doesn't
mean every position requires guesswork — plenty of positions have provably-safe cells
(that's exactly what `GreedyBot`'s single-constraint deduction below finds) — but it
does mean no efficient algorithm is known to *always* find every deducible cell on an
arbitrary board, and some positions have no logically-forced safe cell at all: even
perfect deduction sometimes has to guess. That's the same flavor of result as Connect
Four being a *proven* forced win (a known ceiling) except in the opposite direction — it's
a proof that *no* ceiling on "how well can you always avoid guessing" exists, which
keeps bot-vs-bot play genuinely open rather than racing toward one known-perfect
strategy.

**Existing open-source implementations.** Solitaire Minesweeper clones are everywhere
on GitHub, but *competitive* two-player variants — the actual target here — are a much
smaller, more scattered field:
[`zelaznik/competitive_minesweeper`](https://github.com/zelaznik/competitive_minesweeper)
and [`mzhang28/battlesweeper`](https://github.com/mzhang28/battlesweeper) are both
real-time (not turn-based) head-to-head takes on the classic game;
[`EpxStudio/Minesweeper-Turn-Based-Multiplayer`](https://github.com/EpxStudio/Minesweeper-Turn-Based-Multiplayer)
and [`GeorgeChatzigiannis/minesweeper-multiplayer`](https://github.com/GeorgeChatzigiannis/minesweeper-multiplayer)
are turn-based, closer in spirit, but built as web apps around their own client/server
protocols — none of them speak this repo's `GameProtocol`/`StepResult`/replay/
`GameViewerProtocol` contracts, and none use a shared board scored the way Mine Duel is
(most turn-based variants penalize a wrong *flag* placement rather than scoring a
race to safely clear the most cells). **Decision: build from scratch**, the same call
every other game in this repo has made, and for the clearest reason yet — there's
nothing out there implementing this exact ruleset to adapt.

**Board size.** Rather than pick an arbitrary size, Mine Duel matches Google's own
Minesweeper (`google.com/fbx?fbx=minesweeper`, playable straight from search) at its
"Medium" difficulty: an 18x14 board with 40 mines (~15.9% mine density — between
Google's own Easy, 10x8 with 10 mines, and Hard, 24x20 with 99 mines, which happens to
land on the same 20.6% density as classic Minesweeper's "Expert"). A size everyone
already recognizes beats a size this repo invented from nothing.

## Why This Is Great For Game Night

- Everyone already knows how to play Minesweeper — the only new rule to explain is
  "you take turns, and points are how many safe cells your click uncovers."
- No hidden state to redact means the bot code is the simplest of any game here so
  far — `observation["private_state"]` is always `{}`. A 30-minute bot-writing window
  goes a long way.
- Real, checkable deduction: "if this `2`'s two mines are already accounted for, its
  other neighbors are safe" is a rule a beginner bot-writer can implement in a few
  lines and immediately see it outperform random play.
- Genuine risk/reward tension carries over from the original game — probing near a
  high number versus retreating to an unconstrained corner — but now it's a race
  against an opponent who might grab the next big cascade first.

## The Game In One Minute

- Shared 18x14 board, 40 mines, placed randomly (never on the center cell — see below).
- `player_ember` and `player_frost` alternate turns; each turn is exactly one reveal.
- Revealing a safe cell scores 1 point per cell it uncovers. A `0`-value cell cascades
  outward exactly like classic Minesweeper — reveals every connected `0` plus its
  numbered border in that single turn, all scored at once.
- Revealing a mine costs 1 point and ends your turn immediately (no cascade). The mine
  becomes permanently visible to both players from then on.
- The match ends the instant every safe cell has been found — remaining mines never
  need to be clicked. Higher score wins; a tied score is a draw.
- **The board doesn't start fully blank.** The center cell is guaranteed never to be a
  mine and is revealed (with its own flood cascade) before either player's first
  turn, crediting nobody. This exists specifically to remove a structural first-move
  advantage — see `EDGE_CASES.md` for the measurement that caught it.

## What Data Your Bot Gets

### Observation

- `public_state.board`: 18x14 grid, `"?"` hidden / `"0"`-`"8"` revealed safe cell /
  `"M"` revealed mine
- `public_state.owner_grid`: grid of the same shape, of which player revealed each
  cell (spectator info only)
- `public_state.scores`, `.safe_cells_remaining`, `.current_player`, `.turn_index`,
  `.done`, `.winner`
- `private_state`: always `{}` — see Information Policy below
- `context.opponent_id`, `.rows`, `.cols`, `.mine_count`, `.total_safe_cells`,
  `.mine_penalty`

Full field-by-field spec: `BOT_SPEC.md`. Worked example: `EXAMPLES.md`.

## Information Policy

Mine Duel is the first game in this framework with **no player-private information at
all**. Battleship redacts the opponent's fleet; Splendor redacts reserved cards; here
there is nothing to redact, because neither player has better information about the
mine layout than the other — it's shared uncertainty about the world, not one
player's secret. `observe()` returns the identical `public_state` to both players
every time; `private_state` exists in the shape only for consistency with the other
games' `GameProtocol` implementations.

## Run It Live

```bash
uv run gamenight run-game --game mine_duel --mode headless --bot-1 greedy --bot-2 random --replay-file artifacts/mine_duel.json
```

```bash
uv run gamenight run-game --game mine_duel --mode gui --bot-1 greedy --bot-2 random --gui-delay 0.3
```

```bash
uv run gamenight run-series --game mine_duel --bot-a greedy --bot-b random --games 100 --starting-policy alternate --summary-file artifacts/mine_duel_series.json
```

Add your own bot the same way as any other game here:

```bash
mkdir -p src/gamenight/games/mine_duel/bots/players/<your_name>
cp src/gamenight/games/mine_duel/bots/baselines/random_bot.py src/gamenight/games/mine_duel/bots/players/<your_name>/bot.py
uv run gamenight run-game --game mine_duel --mode headless --bot-1 player:<your_name> --bot-2 greedy
```

## Learn More

- `BOT_SPEC.md` — full observation/action schema
- `EXAMPLES.md` — a complete worked mid-game observation
- `EDGE_CASES.md` — verification checklist, plus the first-move-bias measurement that
  shaped the rules above
- `prompts/greedy_bot_prompt.md` — hand this to an LLM to generate a deduction-based
  bot from scratch
- `bots/players/README.md` — how to add your own bot
