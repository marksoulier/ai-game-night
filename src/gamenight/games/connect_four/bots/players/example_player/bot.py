from __future__ import annotations

from gamenight.core.types import Action, MatchContext, Observation


class PlayerBot:
    def __init__(self, bot_id: str) -> None:
        self.bot_id = bot_id

    def reset(self, context: MatchContext) -> None:
        return None

    def choose_action(self, observation: Observation, context: MatchContext) -> Action:
        """Decide what to play this turn — replace this with your own strategy.

        `observation` is typed as a plain dict because every game has a different shape
        (that's all your editor can tell you). Here's exactly what's inside it for
        Connect Four, field by field, with the type and valid range/values of each one —
        the same shape is documented in ../../../BOT_SPEC.md (full spec) and
        ../../../EXAMPLES.md (a complete worked example), if you want a second look:

            observation = {
                "public_state": {
                    "board": [...],          # list[str], length 42 — each cell "R" / "Y" / " "
                                             #   flat grid, index = row * 7 + col
                                             #   row 0 = TOP of board, row 5 = BOTTOM
                    "current_player": "...", # "player_red" | "player_yellow" — whose turn
                    "turn_index": 0,         # int >= 0, +1 every move
                    "done": False,           # bool — True once the match has ended
                    "winner": None,          # "player_red" | "player_yellow" | None
                                             #   (None means "still going" OR "drawn" —
                                             #   check "done" to tell those apart)
                },
                "private_state": {
                    "marker": "R",           # "R" | "Y" — YOUR disc color (matches your player id)
                },
                "context": {
                    "opponent_id": "...",    # the other player's id, e.g. "player_yellow"
                    "columns": 7,            # board width  (constant for this game)
                    "rows": 6,               # board height (constant for this game)
                    "win_length": 4,         # discs in a row needed to win (constant)
                },
                "legal_actions": [           # list[dict] — only columns that AREN'T full appear
                    {"type": "drop", "column": 0},  # "column" is an int, 0 <= column <= 6
                    ...
                ],
            }

        What you must return: exactly one of the dicts already sitting in
        `observation["legal_actions"]` — e.g. `observation["legal_actions"][0]`, or a
        dict you build yourself as long as it matches one in that list. Anything else
        (wrong shape, an out-of-range column, a column that's already full) is rejected
        by the engine. The engine picks which row your disc lands in for you (gravity);
        you only ever choose a column.

        A reasonable first upgrade from "always play legal_actions[0]" (always column 0,
        which fills up fast and is easy to predict): scan `legal_actions` for a column
        that completes 4-in-a-row for your `marker` right now, and play that if you find
        one — see bots/baselines/greedy_bot.py for a fuller win/block/positional version
        of that idea.
        """
        return observation["legal_actions"][0]
