from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from gamenight.core.match import MatchResult, run_match
from gamenight.core.protocols import BotProtocol, GameProtocol


@dataclass(slots=True)
class TournamentSummary:
    total_matches: int
    wins: dict[str, int]
    draws: int


def run_round_robin(
    game: GameProtocol,
    bots: dict[str, BotProtocol],
    rounds: int = 10,
    max_turns: int = 200,
) -> TournamentSummary:
    bot_ids = list(bots.keys())
    wins = {bot_id: 0 for bot_id in bot_ids}
    draws = 0
    total_matches = 0
    first_id, second_id = game.player_ids[0], game.player_ids[1]

    for _ in range(rounds):
        for p1, p2 in product(bot_ids, bot_ids):
            if p1 == p2:
                continue
            total_matches += 1
            match_bots = {first_id: bots[p1], second_id: bots[p2]}
            result: MatchResult = run_match(game=game, bots=match_bots, max_turns=max_turns)

            if result.winner is None:
                draws += 1
            elif result.winner == first_id:
                wins[p1] += 1
            else:
                wins[p2] += 1

    return TournamentSummary(total_matches=total_matches, wins=wins, draws=draws)
