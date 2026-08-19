from __future__ import annotations

import random
from copy import deepcopy
from itertools import combinations

from gamenight.core.protocols import BotProtocol
from gamenight.core.types import Action, Observation, StepResult
from gamenight.games.ticket_to_ride.bots.baselines.greedy_bot import GreedyBot
from gamenight.games.ticket_to_ride.bots.baselines.human_terminal import HumanTerminalBot
from gamenight.games.ticket_to_ride.bots.baselines.random_bot import RandomBot
from gamenight.games.ticket_to_ride.data import (
    CITIES,
    FACE_UP_DISPLAY_SIZE,
    GRAY,
    INITIAL_HAND_SIZE,
    INITIAL_TICKET_MIN_KEEP,
    LONGEST_PATH_BONUS,
    ROUTE_POINTS,
    ROUTES,
    ROUTES_BY_ID,
    TICKET_DRAW_COUNT,
    TICKET_DRAW_MIN_KEEP,
    TICKETS,
    TICKETS_BY_ID,
    TRAIN_CARDS_PER_COLOR,
    TRAIN_COLORS,
    TRAINS_PER_PLAYER,
    WILD,
    WILD_CARDS_IN_DECK,
    Route,
)


class TicketToRideGame:
    """The official USA map: 36 cities, 100 routes (22 of them "double routes" --
    see `_route_claimable`), 30 Destination Tickets. See `data.py` for the board data
    itself and `README.md` for how it was sourced/verified.

    A turn is a small state machine, not a single step -- see BOT_SPEC.md's
    "Turn Structure" section and `docs/ARCHITECTURE.md`. `current_player` only changes
    once a full logical turn resolves; every phase in between just calls the same
    bot's `choose_action` again with a fresh observation.
    """

    game_id = "ticket_to_ride"
    MIN_PLAYERS = 2
    MAX_PLAYERS = 5
    # A logical turn here can span 2+ step() calls (draw two cards, or draw-then-
    # choose tickets), unlike this framework's other games. The default 200-step
    # budget (see core/match.py's DEFAULT_MAX_TURNS) is tuned for one-step turns and
    # measurably cuts 4-5 player games off before they reach a real conclusion --
    # see EDGE_CASES.md for the measurement. 1200 comfortably covers the worst
    # observed (a 5-player, random-vs-random game needing ~385 steps).
    RECOMMENDED_MAX_TURNS = 1200

    def __init__(self, num_players: int = 2) -> None:
        # 2 (not TTR's more common table size) matches every other variable-player-
        # count game's convention here (see SplendorGame) -- commands like
        # `run-series`/`run-bracket` are inherently 2-competitor and build the game
        # via the registry's bare default with no num_players override, so that
        # default has to be exactly what those commands can actually field bots for.
        # `run-game --bots a,b,c,d` still reaches 3-5 players via `_build_game`.
        if not (self.MIN_PLAYERS <= num_players <= self.MAX_PLAYERS):
            raise ValueError(f"Ticket to Ride supports {self.MIN_PLAYERS}-{self.MAX_PLAYERS} players, got {num_players}")
        self.num_players = num_players
        self.player_ids = [f"player_{i + 1}" for i in range(num_players)]

    def build_baseline_bot(self, name: str, bot_id: str) -> BotProtocol:
        baseline = name.lower().strip()
        if baseline == "random":
            return RandomBot(bot_id=bot_id)
        if baseline == "human":
            return HumanTerminalBot(bot_id=bot_id)
        if baseline == "greedy":
            return GreedyBot(bot_id=bot_id)
        raise ValueError(f"Unknown bot name: {name}")

    # -- setup --------------------------------------------------------------------------

    def create_initial_state(self, seed: int | None = None) -> dict:
        effective_seed = seed if seed is not None else random.Random().getrandbits(32)
        rng = random.Random(effective_seed)

        train_deck = [color for color in TRAIN_COLORS for _ in range(TRAIN_CARDS_PER_COLOR)]
        train_deck += [WILD] * WILD_CARDS_IN_DECK
        rng.shuffle(train_deck)

        ticket_deck = [ticket.ticket_id for ticket in TICKETS]
        rng.shuffle(ticket_deck)

        players = {}
        for pid in self.player_ids:
            hand = {color: 0 for color in TRAIN_COLORS}
            hand[WILD] = 0
            for _ in range(INITIAL_HAND_SIZE):
                hand[train_deck.pop()] += 1
            players[pid] = {
                "hand": hand,
                "tickets": [],
                "trains_remaining": TRAINS_PER_PLAYER,
                "claimed_routes": [],
                "route_score": 0,
            }

        state = {
            "phase": "initial_tickets",
            "current_player": self.player_ids[0],
            "initial_tickets_index": 0,
            "turn_index": 0,
            "done": False,
            "winner": None,
            "final_round_trigger": None,
            "final_round_turns_left": None,
            "train_deck": train_deck,
            "train_discard": [],
            "face_up": [],
            "ticket_deck": ticket_deck,
            "route_owner": [None] * len(ROUTES),
            "players": players,
            "pending_ticket_choice": None,
            "pending_ticket_min_keep": None,
            "final_scores": None,
            "_rng_seed": effective_seed,
            "_shuffle_count": 0,
        }

        self._refill_face_up(state)
        state["pending_ticket_choice"] = self._draw_tickets(state, TICKET_DRAW_COUNT)
        state["pending_ticket_min_keep"] = min(INITIAL_TICKET_MIN_KEEP, len(state["pending_ticket_choice"]))
        return state

    def current_player(self, state: dict) -> str:
        return state["current_player"]

    # -- legal actions ------------------------------------------------------------------

    def legal_actions(self, state: dict, player_id: str) -> list[Action]:
        if state["done"] or player_id != state["current_player"]:
            return []

        if state["phase"] in ("initial_tickets", "choose_tickets"):
            return self._legal_choose_tickets(state)
        if state["phase"] == "draw_second_card":
            return self._legal_draw_card(state)

        # "action" phase
        actions = self._legal_draw_card(state)
        if state["ticket_deck"]:
            actions.append({"type": "draw_tickets"})
        actions += self._legal_claim_route(state, player_id)
        return actions

    def _legal_choose_tickets(self, state: dict) -> list[Action]:
        pending = state["pending_ticket_choice"]
        min_keep = state["pending_ticket_min_keep"]
        actions = []
        for keep_size in range(min_keep, len(pending) + 1):
            for combo in combinations(sorted(pending), keep_size):
                actions.append({"type": "choose_tickets", "keep": list(combo)})
        return actions

    def _legal_draw_card(self, state: dict) -> list[Action]:
        # A face-up locomotive is always a legal pick on either draw of the turn --
        # taking one as your *first* draw just ends your turn immediately afterward
        # (see `_apply_draw_card`); that's a consequence, not a legality restriction.
        actions = []
        for index, color in enumerate(state["face_up"]):
            actions.append({"type": "draw_card", "source": "faceup", "index": index})
        if state["train_deck"] or state["train_discard"]:
            actions.append({"type": "draw_card", "source": "deck"})
        return actions

    def _legal_claim_route(self, state: dict, player_id: str) -> list[Action]:
        player = state["players"][player_id]
        hand = player["hand"]
        actions = []
        for route in ROUTES:
            if not self._route_claimable(state, route, player_id):
                continue
            length = route.length
            candidate_colors = [route.color] if route.color != GRAY else list(TRAIN_COLORS)
            for color in candidate_colors:
                for wild_count in range(0, length + 1):
                    colored_needed = length - wild_count
                    if hand.get(color, 0) < colored_needed or hand[WILD] < wild_count:
                        continue
                    if route.color == GRAY and wild_count == length:
                        # Paying entirely in wilds on a gray route doesn't actually use
                        # `color` at all -- emit exactly one canonical action instead of
                        # one identical-effect action per candidate color.
                        color_field = None
                    else:
                        color_field = color
                    action = {
                        "type": "claim_route",
                        "route_id": route.route_id,
                        "color": color_field,
                        "wild_count": wild_count,
                    }
                    if action not in actions:
                        actions.append(action)
        return actions

    def _route_claimable(self, state: dict, route: Route, player_id: str) -> bool:
        if state["route_owner"][route.route_id] is not None:
            return False
        if route.length > state["players"][player_id]["trains_remaining"]:
            return False
        if route.twin_id is not None:
            twin_owner = state["route_owner"][route.twin_id]
            if self.num_players <= 3:
                if twin_owner is not None:
                    return False
            else:
                if twin_owner == player_id:
                    return False
        return True

    # -- observation ----------------------------------------------------------------------

    def observe(self, state: dict, player_id: str) -> Observation:
        player = state["players"][player_id]
        pending_tickets = None
        pending_min_keep = None
        if state["current_player"] == player_id and state["pending_ticket_choice"] is not None:
            pending_tickets = [
                {"ticket_id": t, "city_a": TICKETS_BY_ID[t].city_a, "city_b": TICKETS_BY_ID[t].city_b, "points": TICKETS_BY_ID[t].points}
                for t in state["pending_ticket_choice"]
            ]
            pending_min_keep = state["pending_ticket_min_keep"]

        return {
            "public_state": {
                "phase": state["phase"],
                "current_player": state["current_player"],
                "turn_index": state["turn_index"],
                "done": state["done"],
                "winner": state["winner"],
                "final_round_trigger": state["final_round_trigger"],
                "face_up": list(state["face_up"]),
                "train_deck_count": len(state["train_deck"]),
                "train_discard_count": len(state["train_discard"]),
                "ticket_deck_count": len(state["ticket_deck"]),
                "route_owner": list(state["route_owner"]),
                "players": {
                    pid: {
                        "hand_size": sum(p["hand"].values()),
                        "ticket_count": len(p["tickets"]),
                        "trains_remaining": p["trains_remaining"],
                        "claimed_routes": list(p["claimed_routes"]),
                        "route_score": p["route_score"],
                    }
                    for pid, p in state["players"].items()
                },
                "final_scores": deepcopy(state["final_scores"]) if state["final_scores"] else None,
            },
            "private_state": {
                "your_hand": dict(player["hand"]),
                "your_tickets": [
                    {"ticket_id": t, "city_a": TICKETS_BY_ID[t].city_a, "city_b": TICKETS_BY_ID[t].city_b, "points": TICKETS_BY_ID[t].points}
                    for t in player["tickets"]
                ],
                "pending_ticket_choice": pending_tickets,
                "pending_ticket_min_keep": pending_min_keep,
            },
            "context": {
                "cities": dict(CITIES),
                "routes": [
                    {"route_id": r.route_id, "city_a": r.city_a, "city_b": r.city_b, "length": r.length, "color": r.color, "twin_id": r.twin_id}
                    for r in ROUTES
                ],
                "route_points": dict(ROUTE_POINTS),
                "train_colors": list(TRAIN_COLORS),
                "num_players": self.num_players,
                "trains_per_player": TRAINS_PER_PLAYER,
                "longest_path_bonus": LONGEST_PATH_BONUS,
            },
        }

    # -- step -------------------------------------------------------------------------------

    def step(self, state: dict, action: Action) -> StepResult:
        if state["done"]:
            return StepResult(next_state=state, rewards=self._rewards(state), done=True)

        next_state = deepcopy(state)
        actor = next_state["current_player"]
        events: list[dict] = []

        if next_state["phase"] in ("initial_tickets", "choose_tickets"):
            events = self._apply_choose_tickets(next_state, actor, action)
        elif next_state["phase"] == "draw_second_card":
            events = self._apply_draw_card(next_state, actor, action, is_first_draw=False)
        elif action["type"] == "draw_card":
            events = self._apply_draw_card(next_state, actor, action, is_first_draw=True)
        elif action["type"] == "draw_tickets":
            events = self._apply_draw_tickets_request(next_state, actor)
        else:
            events = self._apply_claim_route(next_state, actor, action)

        next_state["turn_index"] += 1
        rewards = self._rewards(next_state)
        return StepResult(next_state=next_state, rewards=rewards, done=next_state["done"], events=events)

    # -- draw-card handling -----------------------------------------------------------------

    def _apply_draw_card(self, state: dict, actor: str, action: Action, is_first_draw: bool) -> list[dict]:
        hand = state["players"][actor]["hand"]
        if action["source"] == "faceup":
            index = action["index"]
            color = state["face_up"][index]
            hand[color] += 1
            self._refill_face_up_slot(state, index)
            event = {"type": "draw_card", "player": actor, "source": "faceup", "color": color}
            if is_first_draw and color == WILD:
                self._end_turn(state, actor)
                return [event]
        else:
            color = self._draw_from_deck(state)
            hand[color] += 1
            event = {"type": "draw_card", "player": actor, "source": "deck", "color": color}

        if is_first_draw:
            state["phase"] = "draw_second_card"
        else:
            self._end_turn(state, actor)
        return [event]

    def _draw_from_deck(self, state: dict) -> str:
        if not state["train_deck"]:
            self._reshuffle_discard_into_deck(state)
        return state["train_deck"].pop()

    def _reshuffle_discard_into_deck(self, state: dict) -> None:
        rng = self._step_rng(state)
        state["train_deck"] = list(state["train_discard"])
        state["train_discard"] = []
        rng.shuffle(state["train_deck"])

    def _refill_face_up(self, state: dict) -> None:
        while len(state["face_up"]) < FACE_UP_DISPLAY_SIZE and (state["train_deck"] or state["train_discard"]):
            state["face_up"].append(self._draw_from_deck(state))
        self._purge_face_up_if_too_wild(state)

    def _refill_face_up_slot(self, state: dict, index: int) -> None:
        del state["face_up"][index]
        if state["train_deck"] or state["train_discard"]:
            state["face_up"].insert(index, self._draw_from_deck(state))
        self._purge_face_up_if_too_wild(state)

    def _purge_face_up_if_too_wild(self, state: dict) -> None:
        # Official rule: if 3+ of the 5 face-up cards are locomotives at once, discard
        # the whole display and refill from scratch. Bounded: each purge permanently
        # moves cards to the discard pile, and the deck+discard total is fixed at 110,
        # so this cannot loop forever even under repeated bad luck.
        while state["face_up"].count(WILD) >= 3 and (state["train_deck"] or state["train_discard"]):
            state["train_discard"].extend(state["face_up"])
            state["face_up"] = []
            while len(state["face_up"]) < FACE_UP_DISPLAY_SIZE and (state["train_deck"] or state["train_discard"]):
                state["face_up"].append(self._draw_from_deck(state))

    def _step_rng(self, state: dict) -> random.Random:
        # Deterministic per-reshuffle RNG derived from the game's own seed plus a
        # monotonically increasing counter -- reproducible across runs without relying
        # on Python's hash() (which tuple-seeding would), and without needing `step()`
        # to take a seed/context parameter (it doesn't, per `GameProtocol`).
        combined = state["_rng_seed"] * 1_000_003 + state["_shuffle_count"]
        state["_shuffle_count"] += 1
        return random.Random(combined)

    # -- destination tickets ------------------------------------------------------------------

    def _draw_tickets(self, state: dict, count: int) -> list[int]:
        drawn = []
        for _ in range(min(count, len(state["ticket_deck"]))):
            drawn.append(state["ticket_deck"].pop())
        return drawn

    def _apply_draw_tickets_request(self, state: dict, actor: str) -> list[dict]:
        state["pending_ticket_choice"] = self._draw_tickets(state, TICKET_DRAW_COUNT)
        state["pending_ticket_min_keep"] = min(TICKET_DRAW_MIN_KEEP, len(state["pending_ticket_choice"]))
        state["phase"] = "choose_tickets"
        return [{"type": "draw_tickets", "player": actor, "count": len(state["pending_ticket_choice"])}]

    def _apply_choose_tickets(self, state: dict, actor: str, action: Action) -> list[dict]:
        keep = list(action["keep"])
        discarded = [t for t in state["pending_ticket_choice"] if t not in keep]
        state["players"][actor]["tickets"].extend(keep)
        state["ticket_deck"] = discarded + state["ticket_deck"]  # discarded tickets go to the bottom of the deck
        state["pending_ticket_choice"] = None
        state["pending_ticket_min_keep"] = None
        event = {"type": "choose_tickets", "player": actor, "kept": keep, "discarded": discarded}

        if state["phase"] == "initial_tickets":
            state["phase"] = "action"
            self._advance_initial_tickets(state)
        else:
            self._end_turn(state, actor)
        return [event]

    def _advance_initial_tickets(self, state: dict) -> None:
        state["initial_tickets_index"] += 1
        if state["initial_tickets_index"] >= len(self.player_ids):
            state["phase"] = "action"
            state["current_player"] = self.player_ids[0]
            return
        next_pid = self.player_ids[state["initial_tickets_index"]]
        state["current_player"] = next_pid
        state["phase"] = "initial_tickets"
        state["pending_ticket_choice"] = self._draw_tickets(state, TICKET_DRAW_COUNT)
        state["pending_ticket_min_keep"] = min(INITIAL_TICKET_MIN_KEEP, len(state["pending_ticket_choice"]))

    # -- claiming a route -----------------------------------------------------------------------

    def _apply_claim_route(self, state: dict, actor: str, action: Action) -> list[dict]:
        route = ROUTES_BY_ID[action["route_id"]]
        wild_count = action["wild_count"]
        colored_needed = route.length - wild_count
        color = action["color"]

        player = state["players"][actor]
        if colored_needed > 0:
            player["hand"][color] -= colored_needed
            state["train_discard"].extend([color] * colored_needed)
        if wild_count > 0:
            player["hand"][WILD] -= wild_count
            state["train_discard"].extend([WILD] * wild_count)

        state["route_owner"][route.route_id] = actor
        player["claimed_routes"].append(route.route_id)
        player["trains_remaining"] -= route.length
        player["route_score"] += ROUTE_POINTS[route.length]

        event = {
            "type": "claim_route",
            "player": actor,
            "route_id": route.route_id,
            "city_a": route.city_a,
            "city_b": route.city_b,
            "length": route.length,
            "color": color,
            "wild_count": wild_count,
        }

        if state["final_round_trigger"] is None and player["trains_remaining"] <= 2:
            # Official rule: "each player, including the one who triggered it, gets
            # one final turn." This turn -- the one that just caused the trigger --
            # is NOT one of those N final turns; it already happened. Advance to the
            # next player normally, without counting this turn against the new
            # countdown (that countdown covers turns from here forward).
            state["final_round_trigger"] = actor
            state["final_round_turns_left"] = len(self.player_ids)
            state["current_player"] = self._next_player(actor)
            state["phase"] = "action"
        else:
            self._end_turn(state, actor)
        return [event]

    # -- turn advancement -----------------------------------------------------------------------

    def _end_turn(self, state: dict, actor: str) -> None:
        if state["final_round_trigger"] is not None:
            state["final_round_turns_left"] -= 1
            if state["final_round_turns_left"] <= 0:
                self._finish_game(state)
                return
        state["current_player"] = self._next_player(actor)
        state["phase"] = "action"

    def _next_player(self, actor: str) -> str:
        idx = self.player_ids.index(actor)
        return self.player_ids[(idx + 1) % len(self.player_ids)]

    # -- scoring ----------------------------------------------------------------------------------

    def _finish_game(self, state: dict) -> None:
        breakdown: dict[str, dict] = {}
        longest_paths: dict[str, int] = {}

        for pid, player in state["players"].items():
            connected, ticket_score = self._score_tickets(player)
            longest_paths[pid] = self._longest_path(player["claimed_routes"])
            breakdown[pid] = {
                "route_score": player["route_score"],
                "ticket_score": ticket_score,
                "tickets_completed": connected,
                "tickets_total": len(player["tickets"]),
                "longest_path_length": longest_paths[pid],
                "longest_path_bonus": 0,
                "total": player["route_score"] + ticket_score,
            }

        max_path = max(longest_paths.values(), default=0)
        if max_path > 0:
            for pid, length in longest_paths.items():
                if length == max_path:
                    breakdown[pid]["longest_path_bonus"] = LONGEST_PATH_BONUS
                    breakdown[pid]["total"] += LONGEST_PATH_BONUS

        state["final_scores"] = breakdown
        state["done"] = True
        state["phase"] = "done"
        state["winner"] = self._decide_winner(breakdown)

    def _score_tickets(self, player: dict) -> tuple[int, int]:
        parent = {city: city for city in CITIES}

        def find(city: str) -> str:
            while parent[city] != city:
                parent[city] = parent[parent[city]]
                city = parent[city]
            return city

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for route_id in player["claimed_routes"]:
            route = ROUTES_BY_ID[route_id]
            union(route.city_a, route.city_b)

        connected = 0
        score = 0
        for ticket_id in player["tickets"]:
            ticket = TICKETS_BY_ID[ticket_id]
            if find(ticket.city_a) == find(ticket.city_b):
                connected += 1
                score += ticket.points
            else:
                score -= ticket.points
        return connected, score

    def _longest_path(self, claimed_route_ids: list[int]) -> int:
        """Longest trail (no repeated edges, nodes may repeat) by total route length,
        over the subgraph formed by just this player's claimed routes. Small graph in
        practice (well under a few dozen edges even in a long game), so exhaustive
        DFS from every node is fast and, unlike a heuristic, always exactly correct."""
        if not claimed_route_ids:
            return 0

        adjacency: dict[str, list[tuple[str, int, int]]] = {}  # city -> [(other_city, length, route_id)]
        for route_id in claimed_route_ids:
            route = ROUTES_BY_ID[route_id]
            adjacency.setdefault(route.city_a, []).append((route.city_b, route.length, route_id))
            adjacency.setdefault(route.city_b, []).append((route.city_a, route.length, route_id))

        best = 0

        def dfs(city: str, used_edges: set[int], total: int) -> None:
            nonlocal best
            best = max(best, total)
            for other_city, length, route_id in adjacency.get(city, []):
                if route_id in used_edges:
                    continue
                used_edges.add(route_id)
                dfs(other_city, used_edges, total + length)
                used_edges.remove(route_id)

        for start_city in adjacency:
            dfs(start_city, set(), 0)
        return best

    def _decide_winner(self, breakdown: dict[str, dict]) -> str | None:
        def key(pid: str) -> tuple[int, int, int]:
            entry = breakdown[pid]
            return (entry["total"], entry["tickets_completed"], entry["longest_path_length"])

        ranked = sorted(self.player_ids, key=key, reverse=True)
        if len(ranked) > 1 and key(ranked[0]) == key(ranked[1]):
            return None
        return ranked[0]

    def _rewards(self, state: dict) -> dict[str, float]:
        if not state["done"]:
            return {pid: 0.0 for pid in self.player_ids}
        if state["winner"] is None:
            share = 1.0 / len(self.player_ids)
            return {pid: share for pid in self.player_ids}
        return {pid: (1.0 if pid == state["winner"] else 0.0) for pid in self.player_ids}

    # -- rendering --------------------------------------------------------------------------------

    def render_text(self, state: dict) -> str:
        lines = [
            f"Phase: {state['phase']}  |  Turn {state['turn_index']}  |  current_player: {state['current_player']}",
        ]
        if state["final_round_trigger"]:
            lines.append(
                f"Final round triggered by {state['final_round_trigger']} -- {state['final_round_turns_left']} turn(s) left"
            )
        if state["done"]:
            lines.append(f"Game over: winner is {state['winner']}")

        claimed = sum(1 for owner in state["route_owner"] if owner is not None)
        lines.append(f"Routes claimed: {claimed}/{len(ROUTES)}  |  Face-up: {state['face_up']}")

        for pid, player in state["players"].items():
            lines.append(
                f"{pid}: trains={player['trains_remaining']}  hand={sum(player['hand'].values())}  "
                f"tickets={len(player['tickets'])}  route_score={player['route_score']}"
            )

        if state["final_scores"]:
            lines.append("Final scores:")
            for pid, entry in state["final_scores"].items():
                lines.append(
                    f"  {pid}: route={entry['route_score']} ticket={entry['ticket_score']} "
                    f"(completed {entry['tickets_completed']}/{entry['tickets_total']}) "
                    f"longest_path={entry['longest_path_length']} bonus={entry['longest_path_bonus']} "
                    f"TOTAL={entry['total']}"
                )
        return "\n".join(lines)
