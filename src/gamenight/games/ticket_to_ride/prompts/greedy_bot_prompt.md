# Prompt: Generate Ticket to Ride Greedy Bot

You are writing a Python class for this repository.

Task:

- Create class `PlayerBot` in `bot.py`.
- The class must expose:
  - `__init__(self, bot_id: str)`
  - `reset(self, context)`
  - `choose_action(self, observation, context)`

Rules:

1. Read only from the provided `observation` and `context`.
2. Return one action from `observation["legal_actions"]`.
3. If your preferred action is not legal, fall back to a legal action.
4. Never use hidden information — `observation["private_state"]["your_hand"]` and
   `["your_tickets"]` are the only things you know that your opponents don't; there's
   no field anywhere that reveals *their* hand contents or ticket contents, only
   sizes/counts (`observation["public_state"]["players"][pid]["hand_size"]` etc.).

## Ticket to Ride has a multi-step turn — still one function

Check `observation["public_state"]["phase"]` at the top of `choose_action` and branch:

- `"initial_tickets"` or `"choose_tickets"`: you must pick which destination tickets
  to keep, from `observation["private_state"]["pending_ticket_choice"]`.
- `"action"`: your main decision — draw a card, draw destination tickets, or claim a
  route.
- `"draw_second_card"`: you already drew one card this turn (unless it was a
  face-up locomotive, which ends turns immediately and skips this phase) and now
  choose a second.

The framework calls `choose_action` again for each phase — you don't need a separate
method per phase, just an `if`/`elif` on `phase` inside the one function.

## Three simple heuristics, one per decision

**Choosing tickets to keep** (`initial_tickets`/`choose_tickets`): for each candidate
ticket in `pending_ticket_choice`, estimate how expensive it looks using the two
cities' straight-line distance from `observation["context"]["cities"]`
(`{"CityName": [x, y], ...}`, both in `[0, 1]`):

```python
import math
def ticket_worth(ticket, cities):
    ax, ay = cities[ticket["city_a"]]
    bx, by = cities[ticket["city_b"]]
    distance = math.hypot(ax - bx, ay - by)
    return ticket["points"] / max(distance, 0.05)
```

Every legal `choose_tickets` action is already a *valid-sized* combination (respects
the minimum-keep rule) — score each candidate action by the **average** `ticket_worth`
of the tickets in its `keep` list, and pick the highest. Averaging (not summing)
naturally favors dropping low-value tickets without being biased toward keeping fewer
than necessary.

**Claiming a route** (`"action"` phase, when `observation["legal_actions"]` contains
any `claim_route` actions): claiming is almost always worth it over drawing, on raw
points. Prefer the claimable route worth the most points, using
`observation["context"]["route_points"][length]` (the official
`{1: 1, 2: 2, 3: 4, 4: 7, 5: 10, 6: 15}` table — longer routes are worth
disproportionately more per segment).

**Drawing a card** (`"action"`/`"draw_second_card"`, when nothing's claimable): a
face-up locomotive (`"wild"`) is always worth taking on sight — it substitutes for
any color. Otherwise, pile onto whichever face-up color you already hold the most
of, using `observation["private_state"]["your_hand"]` — this builds toward being able
to afford a big single-color route later, rather than spreading your hand thin across
colors you'll never use together.

## Why this is "greedy," not optimal

None of this does actual route-planning toward your specific tickets — that would
require real pathfinding (shortest path to connect two cities, then working backward
to which routes to claim), which is a much bigger undertaking (see `../../README.md`'s
"Is Ticket to Ride Solved?" section on why finding the best subset of tickets to
pursue is NP-hard in general). This bot never even looks at *which* tickets it holds
when deciding what to claim — it just grabs the biggest point value available. That's
intentional: a "clearly better than random" bot for a 30-minute window, not a
tournament-winning one.
