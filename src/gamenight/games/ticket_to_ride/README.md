# Ticket to Ride: A Graph, Two Hidden Hands, and a Turn That Isn't One Move

Ticket to Ride is the biggest game in this framework by a wide margin: the official
USA map (36 cities, 100 routes, 30 Destination Tickets), 2-5 players, two
independent kinds of hidden information per player instead of one, a turn that's a
small state machine rather than a single action, and end-game scoring that runs
actual graph algorithms (connectivity checks, a longest-path search) instead of
simple counting. Every other game here is either a grid or a flat card market; this
is the first one that's a real graph.

## Research (per `docs/how_to_add_game.md`)

**Is Ticket to Ride "solved"?** No — and not close. Unlike Tic-Tac-Toe (forced draw)
or Connect Four (forced first-player win, Allis 1988), Ticket to Ride is an active AI
research target *because* it resists exactly the techniques that solved those games:
imperfect information (opponents' hands and tickets are hidden), a large
state-action space, and delayed rewards (a ticket's payoff isn't known until the
whole game ends). Researchers have applied both Proximal Policy Optimization and
Monte Carlo Tree Search to it directly — see [Roberts & Chen, "Reinforcement
Learning Agents Playing Ticket to Ride — a Complex Imperfect Information Board Game
with Delayed
Rewards"](https://www.researchgate.net/publication/371649650_Reinforcement_Learning_Agents_Playing_Ticket_to_Ride_--_a_Complex_Imperfect_Information_Board_Game_with_Delayed_Rewards)
and [Huchler, "An MCTS Agent for Ticket to Ride" (Maastricht University master's
thesis)](https://project.dke.maastrichtuniversity.nl/games/files/msc/Huchler_thesis.pdf).
There's also a genuine complexity-theory result underneath the strategy: picking the
best subset of destination tickets to pursue reduces to the Traveling Salesperson
Problem, which is NP-hard — see [Bahna, "Ticket to Ride and the Traveling Salesperson
Problem"](https://theboardgamescholar.com/2021/02/27/ticket-to-ride-the-traveling-salesperson-problem/)
and the graph-theoretic treatment in [Michael & Zaman, "Applications of Graph Theory
and Probability in the Board Game Ticket to Ride" (FDG
2020)](https://dl.acm.org/doi/10.1145/3402942.3402963). This bot framework's own
`GreedyBot` (see `prompts/greedy_bot_prompt.md`) deliberately doesn't attempt any of
that — a real route-planning bot is a research project, not a 30-minute one.

**Existing open-source implementations.** Full rules engines exist —
[`fernandomsilva/Ticket-to-Ride-Engine`](https://github.com/fernandomsilva/Ticket-to-Ride-Engine)
(Python, multiple maps),
[`CodeProgress/TicketToRide`](https://github.com/CodeProgress/TicketToRide) (Python),
[`willdzeng/ticket_to_ride`](https://github.com/willdzeng/ticket_to_ride) (engine plus
several AI implementations) — but none speak this repo's
`GameProtocol`/`StepResult`/replay/`GameViewerProtocol` contracts, and this game's
turn-phase state machine and dual hidden-info shape (see BOT_SPEC.md) don't map onto
any of their APIs cleanly. **Decision: build from scratch**, the same call every
other game here has made.

**Board data.** Rather than hand-transcribe the map from a photo of the board (error
prone at this scale — 100 routes, 36 cities), the city coordinates, route list
(city pairs, lengths, colors), and full 30-card Destination Ticket list were sourced
from [`Rob217/TicketToRideAnalysis`](https://github.com/Rob217/TicketToRideAnalysis),
a project that did exactly this transcription for its own statistical analysis of
the map. Every number was independently re-verified after import: exactly 100
routes, 36 cities, 30 tickets, 22 double-route pairs, and a color distribution
matching the known official composition (each of the 8 colors appears on exactly 7
routes; see `data.py`'s derivation code).

**Rules verification.** The less-obvious rules below were each independently
confirmed against multiple sources before being encoded, not assumed from memory:
[UltraBoardGames' official rules
reference](https://www.ultraboardgames.com/ticket-to-ride/game-rules.php),
[officialgamerules.org](https://officialgamerules.org/game-rules/ticket-to-ride/), and
[Geeky Hobbies' rules
writeup](https://www.geekyhobbies.com/ticket-to-ride-board-game-rules-and-instructions-for-how-to-play/).

## Why This Is Great For Game Night

- It's the game most people at a table have actually played before — no rules
  explanation needed for the humans, just for their bots.
- The turn-phase structure (draw two cards, or draw-then-choose-tickets) is a real
  step up in bot-writing difficulty from every earlier game here, without needing a
  new *kind* of code — it's still one `choose_action` method, branching on `phase`
  the same way Battleship bots already branch on `"placement"`/`"battle"` (see
  BOT_SPEC.md's "Turn Structure").
- Real strategic tension shows up fast: hoard cards for a big route vs. claim
  something now before an opponent takes it; chase more tickets vs. protect the ones
  you already hold, since an unconnected ticket costs you points instead of just
  being worth zero.
- The GUI shows the entire map at once (see below) — a natural thing for a room full
  of people to watch and argue over.

## The Game In One Minute

- 2-5 players, 45 train pieces each, official USA map (36 cities, 100 routes).
- Each turn: draw 2 train cards (from a 5-card face-up market or blind from the
  deck — taking a face-up locomotive as your *first* draw ends your turn
  immediately), **or** draw 3 Destination Tickets and keep at least 1, **or** claim
  one route by discarding cards matching its color and length (locomotives
  substitute for any color).
- **Double routes**: 22 city pairs have two parallel routes. At 2-3 players, claiming
  either one removes *both* from play. At 4-5 players, both are claimable
  independently — just never by the same player.
- Claiming a route scores points by length: 1->1, 2->2, 3->4, 4->7, 5->10, 6->15 (long
  routes are worth disproportionately more per segment).
- The instant any player's trains drop to 2 or fewer, the final round begins: every
  other player gets one more turn, **and so does the triggering player** once the
  rotation comes back around to them — then the game ends.
- Final scoring adds: each held Destination Ticket's points if its two cities end up
  connected through your own claimed routes (checked via union-find over just your
  routes), or *minus* its points if not; plus a +10 bonus to whoever holds the single
  longest unbroken chain of their own claimed routes (a real longest-trail search, no
  repeated route). Overall tie-break: total score, then most completed tickets, then
  longest path.

## What Data Your Bot Gets

- `public_state`: `phase`, whose turn, the face-up market, deck/discard/ticket-deck
  *sizes* (never their order), a 100-entry `route_owner` list, every player's hand
  *size*/ticket *count*/trains-left/score, and `final_scores` once the match ends.
- `private_state`: your own hand contents, your own ticket contents, and (only during
  your own ticket-choosing phases) the tickets you just drew and the minimum you must
  keep.
- `context`: the full city/route/ticket data plus fixed constants (`route_points`,
  `train_colors`, `trains_per_player`, `longest_path_bonus`).

Full field-by-field spec: `BOT_SPEC.md`. Worked example: `EXAMPLES.md`.

## Information Policy

Two independent things are private per player here — your hand and your tickets —
which is new for this framework (every earlier game has at most one secret).
Opponents' hand *size* and ticket *count* are public (mirrors Splendor's
`reserved_count`-is-public-but-contents-aren't pattern, applied twice over); their
actual contents never appear anywhere in your `observation`. The train and ticket
deck *order* is never exposed to anyone, bots included, matching
`docs/ARCHITECTURE.md`'s general Information Policy on undealt deck order.

## A Note On Turn Budget

Ticket to Ride's turns can span 2-3 `step()` calls (this framework counts a "turn"
per `step()`, not per logical player turn), so it needs a much bigger turn ceiling
than earlier games to reliably finish rather than get cut off mid-game — see
EDGE_CASES.md for the measurement. This is handled automatically:
`TicketToRideGame.RECOMMENDED_MAX_TURNS` is picked up by `core/match.py` for every
run mode without you needing to pass anything.

## Run It Live

```bash
uv run gamenight run-game --game ticket_to_ride --mode headless --bot-1 greedy --bot-2 random --replay-file artifacts/ttr.json
```

```bash
uv run gamenight run-game --game ticket_to_ride --mode gui --bots greedy,random,greedy,random --gui-delay 0.1
```

```bash
uv run gamenight run-series --game ticket_to_ride --bot-a greedy --bot-b random --games 50 --starting-policy alternate --summary-file artifacts/ttr_series.json
```

Add your own bot the same way as any other game here:

```bash
mkdir -p src/gamenight/games/ticket_to_ride/bots/players/<your_name>
cp src/gamenight/games/ticket_to_ride/bots/baselines/random_bot.py src/gamenight/games/ticket_to_ride/bots/players/<your_name>/bot.py
uv run gamenight run-game --game ticket_to_ride --mode headless --bots player:<your_name>,greedy
```

## Learn More

- `BOT_SPEC.md` — full observation/action schema, including the turn-phase state machine
- `EXAMPLES.md` — a complete worked mid-game observation, plus a real finished game's `final_scores`
- `EDGE_CASES.md` — verification checklist, including two real bugs the testing caught
  (a final-round off-by-one, and 4-5 player games silently truncating)
- `prompts/greedy_bot_prompt.md` — hand this to an LLM to generate a heuristic bot from scratch
- `bots/players/README.md` — how to add your own bot
- `data.py` — the board data itself, plus where it came from
