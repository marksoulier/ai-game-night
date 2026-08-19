from __future__ import annotations

import math
import statistics

from gamenight.core.types import Action, MatchContext, Observation


class GreedyBot:
    """Three independent, deliberately simple heuristics -- one per phase. Nowhere
    near optimal (that would mean route-planning toward specific tickets, which needs
    real pathfinding -- see README.md's "Is Ticket to Ride Solved?" section on why
    that's a research-grade problem, not a 30-minute one), but each rule is a clear
    step up from picking randomly:

    - **Ticket selection** (`initial_tickets`/`choose_tickets`): keep whichever
      tickets have the best points-per-distance ratio, using each ticket's two
      cities' straight-line distance as a cheap stand-in for "how expensive this is
      to actually complete." Every legal `choose_tickets` action is already a
      combination that satisfies the minimum-keep rule, so scoring by the *average*
      ratio of the kept set (not the total) naturally favors dropping bad tickets
      without being biased toward keeping fewer.
    - **Claiming a route** (`action`): always claim if anything is affordable --
      claiming almost always beats drawing on points alone -- preferring whichever
      claimable route is worth the most points (the official length->points table
      rewards long routes disproportionately).
    - **Drawing a card** (`action`/`draw_second_card`, when nothing's claimable):
      take a face-up locomotive on sight (always useful, substitutes for anything),
      otherwise pile onto whichever face-up color you already hold the most of.
    """

    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        legal_actions = observation["legal_actions"]
        phase = observation["public_state"]["phase"]

        if phase in ("initial_tickets", "choose_tickets"):
            return self._choose_tickets(observation, legal_actions)

        claim_actions = [a for a in legal_actions if a["type"] == "claim_route"]
        if claim_actions:
            return self._best_claim(observation, claim_actions)

        return self._best_draw(observation, legal_actions)

    def _choose_tickets(self, observation: Observation, legal_actions: list[Action]) -> Action:
        cities = observation["context"]["cities"]
        pending_by_id = {t["ticket_id"]: t for t in observation["private_state"]["pending_ticket_choice"]}

        def worth(ticket_id: int) -> float:
            ticket = pending_by_id[ticket_id]
            ax, ay = cities[ticket["city_a"]]
            bx, by = cities[ticket["city_b"]]
            distance = math.hypot(ax - bx, ay - by)
            return ticket["points"] / max(distance, 0.05)

        def score(action: Action) -> float:
            return statistics.mean(worth(t) for t in action["keep"])

        return max(legal_actions, key=score)

    def _best_claim(self, observation: Observation, claim_actions: list[Action]) -> Action:
        route_points = observation["context"]["route_points"]
        routes_by_id = {r["route_id"]: r for r in observation["context"]["routes"]}

        def score(action: Action) -> int:
            length = routes_by_id[action["route_id"]]["length"]
            return route_points[length]

        return max(claim_actions, key=score)

    def _best_draw(self, observation: Observation, legal_actions: list[Action]) -> Action:
        hand = observation["private_state"]["your_hand"]
        face_up = observation["public_state"]["face_up"]
        draw_actions = [a for a in legal_actions if a["type"] == "draw_card"]

        def score(action: Action) -> float:
            if action["source"] == "deck":
                return -1.0
            color = face_up[action["index"]]
            if color == "wild":
                return 100.0
            return float(hand.get(color, 0))

        return max(draw_actions, key=score)
