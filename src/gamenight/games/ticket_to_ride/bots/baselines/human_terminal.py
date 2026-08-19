from __future__ import annotations

from gamenight.core.types import Action, MatchContext, Observation


class HumanTerminalBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        """Show the human everything the AI sees, then return their chosen move.

        Ticket to Ride's `observation` is bigger than most games here because a turn
        is a small state machine, not one action -- see BOT_SPEC.md's "Turn
        Structure" section for the full picture. The short version:

            observation = {
                "public_state": {
                    "phase": "...",   # "initial_tickets" | "action" | "draw_second_card" | "choose_tickets"
                    "current_player": "...", "turn_index": 0, "done": False, "winner": None,
                    "final_round_trigger": "..." | None,
                    "face_up": ["red", "wild", ...],           # 5 visible train cards
                    "train_deck_count": 76, "train_discard_count": 0, "ticket_deck_count": 26,
                    "route_owner": [None, "player_2", ...],     # index = route_id, 100 entries
                    "players": {pid: {"hand_size", "ticket_count", "trains_remaining",
                                       "claimed_routes", "route_score"}, ...},
                    "final_scores": {...} | None,               # populated once done
                },
                "private_state": {
                    "your_hand": {"red": 2, "wild": 1, ...},        # every color, incl. 0s
                    "your_tickets": [{"ticket_id", "city_a", "city_b", "points"}, ...],
                    "pending_ticket_choice": [...] | None,          # only set during your own ticket phases
                    "pending_ticket_min_keep": int | None,
                },
                "context": {
                    "cities": {"Seattle": [x, y], ...}, "routes": [{"route_id", "city_a",
                    "city_b", "length", "color", "twin_id"}, ...], "route_points": {1: 1, ..., 6: 15},
                    "train_colors": [...], "num_players": 4, "trains_per_player": 45,
                    "longest_path_bonus": 10,
                },
            }

        Actions, one per phase:
            {"type": "draw_card", "source": "faceup", "index": 2}   # or "source": "deck"
            {"type": "draw_tickets"}
            {"type": "claim_route", "route_id": 17, "color": "black", "wild_count": 1}
            {"type": "choose_tickets", "keep": [4, 11]}

        Whatever the phase, return exactly one of `observation["legal_actions"]`.
        """
        public_state = observation["public_state"]
        private_state = observation["private_state"]
        legal_actions = observation["legal_actions"]
        phase = public_state["phase"]

        print(f"\n=== {self.bot_id} -- phase: {phase} ===")
        print(f"Hand: {private_state['your_hand']}")
        print(f"Tickets held: {len(private_state['your_tickets'])}  |  Trains remaining varies by player")
        print(f"Face-up cards: {public_state['face_up']}")
        print(f"Deck: {public_state['train_deck_count']} train cards, {public_state['ticket_deck_count']} tickets")

        if phase in ("initial_tickets", "choose_tickets"):
            return self._choose_tickets(private_state, legal_actions)
        if phase in ("action", "draw_second_card"):
            return self._choose_main_action(observation, legal_actions)

        return legal_actions[0]

    def _choose_tickets(self, private_state: Observation, legal_actions: list[Action]) -> Action:
        pending = private_state["pending_ticket_choice"]
        min_keep = private_state["pending_ticket_min_keep"]
        print(f"Choose which tickets to keep (at least {min_keep}):")
        for t in pending:
            print(f"  id={t['ticket_id']}: {t['city_a']} <-> {t['city_b']}  ({t['points']} pts)")
        while True:
            raw = input("Enter ticket ids to KEEP, space-separated (e.g. '4 11'): ").strip().split()
            try:
                keep = sorted(int(x) for x in raw)
            except ValueError:
                print("Couldn't parse that as ids -- try again.")
                continue
            candidate = {"type": "choose_tickets", "keep": keep}
            if candidate in legal_actions:
                return candidate
            print("That combination isn't legal (too few kept, or an id wasn't offered) -- try again.")

    def _choose_main_action(self, observation: Observation, legal_actions: list[Action]) -> Action:
        draw_actions = [a for a in legal_actions if a["type"] == "draw_card"]
        ticket_actions = [a for a in legal_actions if a["type"] == "draw_tickets"]
        claim_actions = [a for a in legal_actions if a["type"] == "claim_route"]

        print("Options:")
        print("  d <index>  -- draw the face-up card at that index (0-4)")
        print("  d deck     -- draw blind from the deck")
        if ticket_actions:
            print("  t          -- draw 3 destination tickets")
        if claim_actions:
            routes_by_id = {r["route_id"]: r for r in observation["context"]["routes"]}
            print("  c <route_id> <color> <wild_count>  -- claim a route. Claimable routes:")
            for a in claim_actions[:20]:
                r = routes_by_id[a["route_id"]]
                print(f"    route_id={a['route_id']}: {r['city_a']} <-> {r['city_b']} "
                      f"len={r['length']} color={r['color']}  (pay color={a['color']} wild={a['wild_count']})")
            if len(claim_actions) > 20:
                print(f"    ... and {len(claim_actions) - 20} more legal claim combinations")

        while True:
            raw = input("Your move: ").strip().split()
            if not raw:
                continue
            candidate = self._parse_main_action(raw)
            if candidate is not None and candidate in legal_actions:
                return candidate
            print("Not a legal move -- try again.")

    def _parse_main_action(self, raw: list[str]) -> Action | None:
        try:
            if raw[0] == "d" and raw[1] == "deck":
                return {"type": "draw_card", "source": "deck"}
            if raw[0] == "d":
                return {"type": "draw_card", "source": "faceup", "index": int(raw[1])}
            if raw[0] == "t":
                return {"type": "draw_tickets"}
            if raw[0] == "c":
                color = None if raw[2] == "none" else raw[2]
                return {"type": "claim_route", "route_id": int(raw[1]), "color": color, "wild_count": int(raw[3])}
        except (IndexError, ValueError):
            return None
        return None
