from __future__ import annotations

from gamenight.core.types import MatchContext
from gamenight.games.splendor.types import SplendorAction, SplendorObservation

# ---------------------------------------------------------------------------------
# Explicit typing for `observation` and the action you return
#
# `SplendorObservation` and `SplendorAction` (imported above, from
# ../../../types.py) are `TypedDict`s describing the exact same plain dict your
# `choose_action` already receives -- not a wrapper object, not a conversion step.
# Just write `observation: SplendorObservation` on your method signature (already
# done below) and your editor/type checker understands every field's shape from
# there on: `observation["public_state"]["bank"]["white"]` is known to be an `int`,
# `action["type"]` is known to be one of exactly 6 literal strings, and checking
# `if action["type"] == "purchase_card":` narrows which other fields are valid to
# read on `action` from that point on, the same as narrowing any tagged union.
#
# Nothing about *using* the dict changes -- this only changes what your editor and
# a type checker (or an LLM reading your code) can tell you about its shape while
# you're writing it. See ../../../types.py for every field's type, and
# ../../../BOT_SPEC.md / ../../../EXAMPLES.md for the prose reference and worked
# examples of the same shapes.
# ---------------------------------------------------------------------------------


class PlayerBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: SplendorObservation, context: MatchContext) -> SplendorAction:
        """Decide what to do this step -- replace this with your own strategy.

        Splendor supports **2-4 players**, has **three phases**, and is **almost
        perfect information**: everything is public except each opponent's
        *blind*-reserved cards (cards reserved straight off a face-down deck, which
        genuinely nobody but the owner has ever seen). Cards reserved from the
        face-up *market*, by contrast, are shown to you too -- everyone watched them
        leave the market the instant before they were reserved, so hiding that again
        would just be modeling human memory, not real secrecy. Concretely (shown
        here for a 3-player match):

            observation = {
                "public_state": {
                    "phase": "action",      # "action" | "discard" | "noble_choice" -- see below
                    "current_player": "...", "turn_index": 0, "done": False, "winner": None,
                    "final_round_trigger": None,  # set once someone hits 15+ points
                    "bank": {"white": 5, "blue": 5, "green": 5, "red": 5, "black": 5, "gold": 5},
                    "nobles": [{"id": "n01", "points": 3, "requirement": {"white": 3, "blue": 3}}, ...],
                    "market": {
                        3: {"face_up": [ {"id": "t3-02", "tier": 3, "bonus": "blue",
                                          "points": 4, "cost": {"white": 7}}, ... ],
                            "remaining_in_deck": 16},
                        2: {...}, 1: {...},
                    },
                    "players": {
                        # One entry per seat -- 2 to 4 of them, all public, including yours.
                        "player_1": {
                            "points": 4, "bonuses": {"white": 1, ...}, "tokens": {"white": 0, ..., "gold": 1},
                            "reserved_count": 2, "owned_count": 3, "nobles": [],
                            # The market-origin subset of THEIR reserved cards, shown in full --
                            # reserved_count - len(visible_reserved_cards) is how many of theirs
                            # are blind-origin and stay genuinely unknown to you.
                            "visible_reserved_cards": [
                                {"id": "t1-07", "tier": 1, "bonus": "red", "points": 0, "cost": {"blue": 3}},
                            ],
                        },
                        "player_2": {...},
                        "player_3": {...},
                    },
                },
                "private_state": {
                    # Your own reserved cards, ALWAYS in full (market- and blind-origin
                    # alike -- you always know your own). "source" tells you which:
                    "your_reserved_cards": [
                        {"id": "t2-05", "tier": 2, "bonus": "red", "points": 1,
                         "cost": {"green": 4, "black": 2}, "source": "market"},
                        {"id": "t3-11", "tier": 3, "bonus": "white", "points": 4,
                         "cost": {"blue": 7}, "source": "deck"},
                    ],
                },
                "context": {
                    "opponent_ids": ["player_2", "player_3"],  # every other seat, in turn order
                    "colors": ["white", "blue", "green", "red", "black"],
                    "reserve_limit": 3, "token_limit": 10, "win_threshold": 15,
                    "pending_noble_choices": [],  # only non-empty when phase == "noble_choice"
                },
                "legal_actions": [...],  # shape depends on phase, see below
            }

        **Splendor's turn has up to three phases**, and the engine walks you through
        them automatically -- you never choose which phase you're in, only what to do
        within whichever one `observation["public_state"]["phase"]` says you're in:

        1. `"action"` -- your main move, exactly one of:
           `{"type": "take_tokens", "colors": ["blue", "green", "red"]}` (3 different
           colors, or `["blue", "blue"]` for 2 of the same -- only ever colors from
           `context.colors`, never `"gold"`)
           `{"type": "reserve_card", "location": "market", "tier": 2, "card_id": "t2-05"}`
           (or `"location": "deck"` with no `card_id` -- reserving blind means you don't
           know the card until it lands in your `private_state.your_reserved_cards` on
           your NEXT observation, tagged `"source": "deck"`; up to 3 reserved at once,
           +1 gold if the bank has any)
           `{"type": "purchase_card", "location": "market", "tier": 2, "card_id": "t2-05"}`
           (or `"location": "reserved"` to buy from your own reserve)
           `{"type": "pass"}` (only ever offered if truly nothing else is legal)
        2. `"discard"` -- only reached if your action pushed you over 10 tokens total;
           `legal_actions` is one `{"type": "discard_token", "color": "blue"}` per color
           you're holding, repeated (still your turn) until you're back to 10 or fewer.
        3. `"noble_choice"` -- only reached if your new bonuses qualify for 2+ nobles at
           once (a single qualifying noble is assigned automatically, no decision
           needed); `legal_actions` is one `{"type": "choose_noble", "noble_id": "n03"}`
           per qualifying noble in `context.pending_noble_choices`.

        What you must return: exactly one of the dicts already sitting in
        `observation["legal_actions"]`. Anything else (wrong phase's action shape, a
        card that's no longer there, an unaffordable purchase) is rejected by the
        engine.

        A reasonable first upgrade from "always play legal_actions[0]" (which spends
        most turns just taking tokens and rarely buys anything): once
        `observation["public_state"]["phase"] == "action"`, check
        `observation["legal_actions"]` for any `"purchase_card"` entries first --
        buying a card is almost always better than sitting on tokens. See
        `bots/baselines/greedy_bot.py` for a fuller purchase > reserve > take-tokens
        priority order.
        """
        return observation["legal_actions"][0]
