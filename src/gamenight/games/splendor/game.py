from __future__ import annotations

import random
from copy import deepcopy
from itertools import combinations

from gamenight.core.protocols import BotProtocol
from gamenight.core.types import Action, Observation, StepResult
from gamenight.games.splendor.bots.baselines.greedy_bot import GreedyBot
from gamenight.games.splendor.bots.baselines.human_terminal import HumanTerminalBot
from gamenight.games.splendor.bots.baselines.random_bot import RandomBot


COLORS = ["white", "blue", "green", "red", "black"]
ALL_TOKEN_TYPES = COLORS + ["gold"]

RESERVE_LIMIT = 3
TOKEN_LIMIT = 10
WIN_THRESHOLD = 15

# Real Splendor scales both the bank and the number of revealed nobles with player
# count -- more players means more total resources in circulation, and one extra
# noble in play than there are seats (so it's never a guaranteed "everyone gets one").
BANK_PER_COLOR_BY_PLAYERS = {2: 4, 3: 5, 4: 7}


def _color_at(offset: int) -> str:
    return COLORS[offset % len(COLORS)]


def _build_tier(tier: int, templates: list[tuple[int, dict[int, int]]]) -> list[dict]:
    """Builds one tier's fixed deck (40/30/20 cards for tiers 1/2/3).

    Card *content* here is procedurally generated from Splendor's well-documented tier
    structure (point/cost bands rising by tier, an even split across the 5 bonus colors)
    -- it is intentionally NOT a transcription of the retail card list. See README.md's
    "Card Data" note for why. `templates` express each card's cost as offsets *relative*
    to its own bonus color (offset 1 = "the next color after this card's bonus," offset 2
    = the one after that, ...), so the same handful of template shapes rotate around the
    5-color wheel as the bonus color cycles, giving every bonus color an identical spread
    of cost shapes rather than hand-duplicating each template 5 times.
    """
    cards = []
    for bonus_index, bonus in enumerate(COLORS):
        for card_index, (points, cost_offsets) in enumerate(templates):
            cost = {_color_at(bonus_index + offset): amount for offset, amount in cost_offsets.items()}
            cards.append(
                {
                    "id": f"t{tier}-{bonus_index * len(templates) + card_index + 1:02d}",
                    "tier": tier,
                    "bonus": bonus,
                    "points": points,
                    "cost": cost,
                }
            )
    return cards


# points, {color_offset_from_bonus: amount}
TIER_1_TEMPLATES = [
    (0, {1: 1, 2: 1}),
    (0, {1: 2}),
    (0, {1: 1, 2: 1, 3: 1}),
    (0, {2: 2, 3: 1}),
    (0, {1: 3}),
    (0, {1: 1, 3: 2}),
    (1, {2: 3, 4: 1}),
    (1, {1: 2, 2: 2}),
]
TIER_2_TEMPLATES = [
    (1, {1: 2, 2: 2, 3: 1}),
    (1, {1: 3, 4: 2}),
    (2, {2: 1, 3: 4}),
    (1, {1: 1, 2: 1, 3: 1, 4: 2}),
    (2, {3: 5}),
    (3, {2: 6}),
]
TIER_3_TEMPLATES = [
    (3, {1: 3, 2: 3, 3: 3}),
    (4, {2: 7}),
    (5, {1: 3, 3: 6}),
    (4, {1: 3, 2: 3, 3: 3, 4: 3}),
]

CARDS_BY_TIER = {
    1: _build_tier(1, TIER_1_TEMPLATES),
    2: _build_tier(2, TIER_2_TEMPLATES),
    3: _build_tier(3, TIER_3_TEMPLATES),
}

NOBLE_REQUIREMENTS = [
    {"white": 3, "blue": 3},
    {"blue": 3, "green": 3},
    {"green": 3, "red": 3},
    {"red": 3, "black": 3},
    {"black": 3, "white": 3},
    {"white": 4},
    {"blue": 4},
    {"green": 4},
    {"red": 4},
    {"black": 4},
]
NOBLES = [
    {"id": f"n{index + 1:02d}", "points": 3, "requirement": dict(requirement)}
    for index, requirement in enumerate(NOBLE_REQUIREMENTS)
]


def _new_player_state() -> dict:
    return {
        "tokens": {c: 0 for c in ALL_TOKEN_TYPES},
        "bonuses": {c: 0 for c in COLORS},
        "owned": [],
        "reserved": [],
        "points": 0,
        "nobles": [],
    }


class SplendorGame:
    game_id = "splendor"
    MIN_PLAYERS = 2
    MAX_PLAYERS = 4  # matches the real game; NOBLES has 10 entries, plenty for max_players + 1 = 5 revealed

    def __init__(self, num_players: int = 2) -> None:
        if not (self.MIN_PLAYERS <= num_players <= self.MAX_PLAYERS):
            raise ValueError(
                f"Splendor supports {self.MIN_PLAYERS}-{self.MAX_PLAYERS} players, got {num_players}"
            )
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

    def create_initial_state(self, seed: int | None = None) -> dict:
        rng = random.Random(seed)

        tiers: dict[str, dict] = {}
        for tier, cards in CARDS_BY_TIER.items():
            deck = [dict(card) for card in cards]
            rng.shuffle(deck)
            tiers[str(tier)] = {"face_up": deck[:4], "deck": deck[4:]}

        nobles = [dict(noble) for noble in NOBLES]
        rng.shuffle(nobles)

        bank_per_color = BANK_PER_COLOR_BY_PLAYERS[self.num_players]
        nobles_revealed = self.num_players + 1
        return {
            "phase": "action",  # "action" | "discard" | "noble_choice"
            "current_player": self.player_ids[0],
            "turn_index": 0,
            "done": False,
            "winner": None,
            "final_round_trigger": None,
            "bank": {color: bank_per_color for color in COLORS} | {"gold": 5},
            "tiers": tiers,
            "nobles": nobles[:nobles_revealed],
            "pending_noble_choices": [],
            "players": {pid: _new_player_state() for pid in self.player_ids},
        }

    def current_player(self, state: dict) -> str:
        return state["current_player"]

    def legal_actions(self, state: dict, player_id: str) -> list[Action]:
        if state["done"] or player_id != state["current_player"]:
            return []
        if state["phase"] == "discard":
            return self._legal_discards(state, player_id)
        if state["phase"] == "noble_choice":
            return self._legal_noble_choices(state)
        return self._legal_main_actions(state, player_id)

    def observe(self, state: dict, player_id: str) -> Observation:
        opponent_ids = [pid for pid in self.player_ids if pid != player_id]
        player = state["players"][player_id]

        market = {
            int(tier_key): {
                "face_up": [dict(card) for card in tier["face_up"]],
                "remaining_in_deck": len(tier["deck"]),
            }
            for tier_key, tier in state["tiers"].items()
        }

        return {
            "public_state": {
                "phase": state["phase"],
                "current_player": state["current_player"],
                "turn_index": state["turn_index"],
                "done": state["done"],
                "winner": state["winner"],
                "final_round_trigger": state["final_round_trigger"],
                "bank": dict(state["bank"]),
                "nobles": [dict(noble) for noble in state["nobles"]],
                "market": market,
                "players": {pid: self._player_public_view(state, pid) for pid in self.player_ids},
            },
            "private_state": {
                # Your own reserved cards, always in full regardless of how you got
                # them (market or blind) -- "source" tells you which.
                "your_reserved_cards": [self._reserved_card_view(card) for card in player["reserved"]],
            },
            "context": {
                "opponent_ids": opponent_ids,
                "colors": list(COLORS),
                "reserve_limit": RESERVE_LIMIT,
                "token_limit": TOKEN_LIMIT,
                "win_threshold": WIN_THRESHOLD,
                "pending_noble_choices": (
                    list(state["pending_noble_choices"]) if state["phase"] == "noble_choice" else []
                ),
            },
        }

    def step(self, state: dict, action: Action) -> StepResult:
        if state["done"]:
            return StepResult(next_state=state, rewards=self._rewards(state), done=True)

        next_state = deepcopy(state)
        actor = next_state["current_player"]

        if next_state["phase"] == "discard":
            events = self._apply_discard(next_state, actor, action)
        elif next_state["phase"] == "noble_choice":
            events = self._apply_noble_choice(next_state, actor, action)
        else:
            events = self._apply_main_action(next_state, actor, action)

        next_state["turn_index"] += 1
        rewards = self._rewards(next_state)
        return StepResult(next_state=next_state, rewards=rewards, done=next_state["done"], events=events)

    def remaining_points(self, state: dict, player_id: str) -> int:
        """Prestige points -- consumed by core/bracket.py's series tiebreaker exactly
        the way BattleshipGame.remaining_points is (see run-bracket's --games-per-match
        docs): if a series ties on wins, whoever scored more total points across the
        series wins the tiebreak."""
        return state["players"][player_id]["points"]

    def render_text(self, state: dict) -> str:
        lines = [
            f"Phase: {state['phase']}  |  Turn {state['turn_index']}  |  current_player: {state['current_player']}"
        ]
        if state["done"]:
            lines.append(f"Game over: winner is {state['winner']}")

        bank = state["bank"]
        lines.append("Bank: " + "  ".join(f"{c}={bank[c]}" for c in ALL_TOKEN_TYPES))

        if state["nobles"]:
            lines.append("Nobles: " + ", ".join(self._noble_text(noble) for noble in state["nobles"]))

        for tier_key in ("3", "2", "1"):
            tier = state["tiers"][tier_key]
            lines.append(f"Tier {tier_key} ({len(tier['deck'])} left in deck):")
            for card in tier["face_up"]:
                lines.append("  " + self._card_text(card))

        for player_id in self.player_ids:
            player = state["players"][player_id]
            bonuses = "  ".join(f"{c}={player['bonuses'][c]}" for c in COLORS if player["bonuses"][c])
            tokens = "  ".join(f"{c}={player['tokens'][c]}" for c in ALL_TOKEN_TYPES if player["tokens"][c])
            lines.append(
                f"{player_id}: {player['points']} pts | bonuses: {bonuses or 'none'} | "
                f"tokens: {tokens or 'none'} | reserved: {len(player['reserved'])} | "
                f"nobles: {len(player['nobles'])}"
            )
        return "\n".join(lines)

    # -- action phase: legal actions ------------------------------------------------

    def _legal_main_actions(self, state: dict, player_id: str) -> list[Action]:
        actions: list[Action] = []
        bank = state["bank"]

        available = [color for color in COLORS if bank[color] > 0]
        if len(available) >= 3:
            for combo in combinations(available, 3):
                actions.append({"type": "take_tokens", "colors": sorted(combo)})
        elif available:
            actions.append({"type": "take_tokens", "colors": sorted(available)})
        for color in COLORS:
            if bank[color] >= 4:
                actions.append({"type": "take_tokens", "colors": [color, color]})

        player = state["players"][player_id]
        if len(player["reserved"]) < RESERVE_LIMIT:
            for tier_key, tier in state["tiers"].items():
                for card in tier["face_up"]:
                    actions.append(
                        {"type": "reserve_card", "location": "market", "tier": int(tier_key), "card_id": card["id"]}
                    )
                if tier["deck"]:
                    actions.append({"type": "reserve_card", "location": "deck", "tier": int(tier_key)})

        for tier in state["tiers"].values():
            for card in tier["face_up"]:
                if self._affordable(card, player):
                    actions.append(
                        {"type": "purchase_card", "location": "market", "tier": card["tier"], "card_id": card["id"]}
                    )
        for card in player["reserved"]:
            if self._affordable(card, player):
                actions.append(
                    {"type": "purchase_card", "location": "reserved", "tier": card["tier"], "card_id": card["id"]}
                )

        if not actions:
            # Deliberate safety valve for the (rare, late-game) case where a player can
            # neither take a token, reserve, nor afford anything -- matches the real
            # rulebook's "pass if truly no legal action" clause rather than deadlocking.
            actions.append({"type": "pass"})
        return actions

    def _legal_discards(self, state: dict, player_id: str) -> list[Action]:
        player = state["players"][player_id]
        return [{"type": "discard_token", "color": c} for c in ALL_TOKEN_TYPES if player["tokens"][c] > 0]

    def _legal_noble_choices(self, state: dict) -> list[Action]:
        return [{"type": "choose_noble", "noble_id": noble_id} for noble_id in state["pending_noble_choices"]]

    @staticmethod
    def _affordable(card: dict, player: dict) -> bool:
        gold_needed = 0
        for color, amount in card["cost"].items():
            effective = amount - player["bonuses"].get(color, 0)
            if effective > 0:
                shortfall = effective - player["tokens"].get(color, 0)
                if shortfall > 0:
                    gold_needed += shortfall
        return gold_needed <= player["tokens"].get("gold", 0)

    # -- applying actions -------------------------------------------------------------

    def _apply_main_action(self, state: dict, player_id: str, action: Action) -> list[dict]:
        action_type = action["type"]
        if action_type == "take_tokens":
            events = self._apply_take_tokens(state, player_id, action)
        elif action_type == "reserve_card":
            events = self._apply_reserve(state, player_id, action)
        elif action_type == "purchase_card":
            events = self._apply_purchase(state, player_id, action)
        elif action_type == "pass":
            events = [{"type": "pass", "player": player_id}]
        else:
            raise ValueError(f"Unknown action type: {action_type!r}")

        self._advance_after_main_action(state, player_id)
        return events

    def _apply_take_tokens(self, state: dict, player_id: str, action: Action) -> list[dict]:
        player = state["players"][player_id]
        bank = state["bank"]
        colors = list(action["colors"])

        if len(colors) == 2 and colors[0] == colors[1]:
            color = colors[0]
            if color not in COLORS or bank[color] < 4:
                raise ValueError(f"Cannot take 2 {color} tokens -- bank has fewer than 4 remaining")
            bank[color] -= 2
            player["tokens"][color] += 2
        elif 1 <= len(colors) <= 3 and len(set(colors)) == len(colors):
            for color in colors:
                if color not in COLORS or bank[color] < 1:
                    raise ValueError(f"Cannot take a {color} token -- bank is empty")
            for color in colors:
                bank[color] -= 1
                player["tokens"][color] += 1
        else:
            raise ValueError(f"Illegal take_tokens action: {action!r}")

        return [{"type": "take_tokens", "player": player_id, "colors": colors}]

    def _apply_reserve(self, state: dict, player_id: str, action: Action) -> list[dict]:
        player = state["players"][player_id]
        if len(player["reserved"]) >= RESERVE_LIMIT:
            raise ValueError(f"{player_id} already has {RESERVE_LIMIT} reserved cards")

        tier_key = str(action["tier"])
        tier = state["tiers"][tier_key]

        if action["location"] == "market":
            card_id = action["card_id"]
            card = next((c for c in tier["face_up"] if c["id"] == card_id), None)
            if card is None:
                raise ValueError(f"Card {card_id!r} is not currently face-up in tier {tier_key}")
            tier["face_up"].remove(card)
            self._refill_face_up(tier)
            card["source"] = "market"  # was face-up a moment ago -- everyone watched it leave, see observe()
        elif action["location"] == "deck":
            if not tier["deck"]:
                raise ValueError(f"Tier {tier_key} deck is empty -- cannot reserve blind")
            card = tier["deck"].pop()
            card["source"] = "deck"  # genuinely never seen by anyone but the reserving player
        else:
            raise ValueError(f"Unknown reserve location: {action['location']!r}")

        player["reserved"].append(card)
        gained_gold = False
        if state["bank"]["gold"] > 0:
            state["bank"]["gold"] -= 1
            player["tokens"]["gold"] += 1
            gained_gold = True

        return [
            {
                "type": "reserve_card",
                "player": player_id,
                "tier": int(tier_key),
                "card_id": card["id"],
                "gained_gold": gained_gold,
            }
        ]

    def _apply_purchase(self, state: dict, player_id: str, action: Action) -> list[dict]:
        player = state["players"][player_id]

        if action["location"] == "market":
            tier_key = str(action["tier"])
            tier = state["tiers"][tier_key]
            card = next((c for c in tier["face_up"] if c["id"] == action["card_id"]), None)
            if card is None:
                raise ValueError(f"Card {action['card_id']!r} is not currently face-up in tier {tier_key}")
            if not self._affordable(card, player):
                raise ValueError(f"{player_id} cannot afford card {card['id']!r}")
            tier["face_up"].remove(card)
            self._refill_face_up(tier)
        elif action["location"] == "reserved":
            card = next((c for c in player["reserved"] if c["id"] == action["card_id"]), None)
            if card is None:
                raise ValueError(f"{player_id} does not have card {action['card_id']!r} reserved")
            if not self._affordable(card, player):
                raise ValueError(f"{player_id} cannot afford card {card['id']!r}")
            player["reserved"].remove(card)
            card.pop("source", None)  # "source" only means something while a card is reserved
        else:
            raise ValueError(f"Unknown purchase location: {action['location']!r}")

        self._pay_for_card(player, state["bank"], card)
        player["owned"].append(card)
        player["bonuses"][card["bonus"]] += 1
        player["points"] += card["points"]

        return [
            {
                "type": "purchase_card",
                "player": player_id,
                "tier": card["tier"],
                "card_id": card["id"],
                "bonus": card["bonus"],
                "points": card["points"],
            }
        ]

    @staticmethod
    def _pay_for_card(player: dict, bank: dict, card: dict) -> None:
        for color, amount in card["cost"].items():
            effective = max(0, amount - player["bonuses"].get(color, 0))
            pay_from_tokens = min(effective, player["tokens"].get(color, 0))
            player["tokens"][color] -= pay_from_tokens
            bank[color] += pay_from_tokens
            remaining = effective - pay_from_tokens
            if remaining > 0:
                player["tokens"]["gold"] -= remaining
                bank["gold"] += remaining

    @staticmethod
    def _refill_face_up(tier: dict) -> None:
        while len(tier["face_up"]) < 4 and tier["deck"]:
            tier["face_up"].append(tier["deck"].pop())

    def _advance_after_main_action(self, state: dict, player_id: str) -> None:
        player = state["players"][player_id]
        if sum(player["tokens"].values()) > TOKEN_LIMIT:
            state["phase"] = "discard"
            return
        self._resolve_nobles_or_finish_turn(state, player_id)

    def _apply_discard(self, state: dict, player_id: str, action: Action) -> list[dict]:
        player = state["players"][player_id]
        color = action["color"]
        if player["tokens"].get(color, 0) <= 0:
            raise ValueError(f"{player_id} has no {color} tokens to discard")

        player["tokens"][color] -= 1
        state["bank"][color] += 1
        events = [{"type": "discard_token", "player": player_id, "color": color}]

        if sum(player["tokens"].values()) > TOKEN_LIMIT:
            return events  # still over the limit -- stay in "discard" phase for another step
        self._resolve_nobles_or_finish_turn(state, player_id)
        return events

    def _resolve_nobles_or_finish_turn(self, state: dict, player_id: str) -> None:
        player = state["players"][player_id]
        qualifying = [
            noble["id"]
            for noble in state["nobles"]
            if all(player["bonuses"].get(color, 0) >= amount for color, amount in noble["requirement"].items())
        ]

        if len(qualifying) > 1:
            state["phase"] = "noble_choice"
            state["pending_noble_choices"] = qualifying
            return

        state["phase"] = "action"
        state["pending_noble_choices"] = []
        if len(qualifying) == 1:
            self._assign_noble(state, player_id, qualifying[0])
        self._finish_turn(state, player_id)

    def _apply_noble_choice(self, state: dict, player_id: str, action: Action) -> list[dict]:
        noble_id = action["noble_id"]
        if noble_id not in state["pending_noble_choices"]:
            raise ValueError(f"Noble {noble_id!r} is not a pending choice for {player_id}")

        self._assign_noble(state, player_id, noble_id)
        state["phase"] = "action"
        state["pending_noble_choices"] = []
        events = [{"type": "choose_noble", "player": player_id, "noble_id": noble_id}]
        self._finish_turn(state, player_id)
        return events

    @staticmethod
    def _assign_noble(state: dict, player_id: str, noble_id: str) -> None:
        noble = next(noble for noble in state["nobles"] if noble["id"] == noble_id)
        state["nobles"].remove(noble)
        player = state["players"][player_id]
        player["nobles"].append(noble_id)
        player["points"] += noble["points"]

    def _finish_turn(self, state: dict, player_id: str) -> None:
        if state["final_round_trigger"] is None and state["players"][player_id]["points"] >= WIN_THRESHOLD:
            state["final_round_trigger"] = player_id

        next_player = self._next_player(player_id)
        state["current_player"] = next_player

        # This check is player-count-agnostic on purpose: `_next_player` cycles
        # through every seat in turn order, so "control is about to return to whoever
        # triggered the final round" is exactly "everyone has now had one equal turn
        # since the trigger fired," for 2 players or 4.
        if state["final_round_trigger"] is not None and next_player == state["final_round_trigger"]:
            state["done"] = True
            state["winner"] = self._determine_winner(state)

    def _determine_winner(self, state: dict) -> str | None:
        winners = self._winners(state)
        return winners[0] if len(winners) == 1 else None

    def _winners(self, state: dict) -> list[str]:
        """The player(s) still tied for best once every tiebreak is applied -- exactly
        one in the normal case, or more than one on a genuine draw. Shared by
        `_determine_winner` (which reports `None` for a multi-way tie) and `_rewards`
        (which splits credit only among these players, not everyone)."""
        players = state["players"]
        top_points = max(players[pid]["points"] for pid in self.player_ids)
        leaders = [pid for pid in self.player_ids if players[pid]["points"] == top_points]
        if len(leaders) == 1:
            return leaders

        # Tiebreak: fewer cards used to reach the same score is the stronger (more
        # efficient) engine -- the real rulebook's tiebreak, applied among however many
        # players are tied on points (not just two).
        fewest_cards = min(len(players[pid]["owned"]) for pid in leaders)
        return [pid for pid in leaders if len(players[pid]["owned"]) == fewest_cards]

    # -- shared helpers -----------------------------------------------------------------

    def _next_player(self, player_id: str) -> str:
        index = self.player_ids.index(player_id)
        return self.player_ids[(index + 1) % len(self.player_ids)]

    def _player_public_view(self, state: dict, player_id: str) -> dict:
        player = state["players"][player_id]
        return {
            "points": player["points"],
            "bonuses": dict(player["bonuses"]),
            "tokens": dict(player["tokens"]),
            "reserved_count": len(player["reserved"]),
            # A reserved card's identity is only genuinely secret if it was reserved
            # blind off a deck -- nobody but the owner ever saw one of those. A card
            # reserved from the face-up market was watched leaving the market by
            # everyone at the table the instant before it happened, so hiding it again
            # here would just be modeling imperfect human memory, not real hidden
            # information. `reserved_count - len(visible_reserved_cards)` is exactly
            # how many blind reserves this player is holding that stay genuinely
            # unknown to everyone else.
            "visible_reserved_cards": [
                self._card_view(card) for card in player["reserved"] if card["source"] == "market"
            ],
            "owned_count": len(player["owned"]),
            "nobles": list(player["nobles"]),
        }

    @staticmethod
    def _card_view(card: dict) -> dict:
        return {"id": card["id"], "tier": card["tier"], "bonus": card["bonus"], "points": card["points"], "cost": dict(card["cost"])}

    @classmethod
    def _reserved_card_view(cls, card: dict) -> dict:
        view = cls._card_view(card)
        view["source"] = card["source"]
        return view

    @staticmethod
    def _card_text(card: dict) -> str:
        cost = "  ".join(f"{c}{card['cost'][c]}" for c in COLORS if card["cost"].get(c))
        points = f"+{card['points']}pt " if card["points"] else ""
        return f"[{card['id']}] {points}bonus={card['bonus']} cost=({cost})"

    @staticmethod
    def _noble_text(noble: dict) -> str:
        requirement = "  ".join(f"{c}{amount}" for c, amount in noble["requirement"].items())
        return f"[{noble['id']}] +{noble['points']}pt requires ({requirement})"

    def _rewards(self, state: dict) -> dict[str, float]:
        if not state["done"]:
            return {pid: 0.0 for pid in self.player_ids}
        # Credit is split only among `_winners` -- a unique winner gets the whole 1.0,
        # a tied pair (or more) splits it evenly (the familiar 0.5/0.5 when exactly two
        # players tie), and anyone clearly behind gets 0.0 either way.
        winners = self._winners(state)
        share = 1.0 / len(winners)
        return {pid: (share if pid in winners else 0.0) for pid in self.player_ids}
