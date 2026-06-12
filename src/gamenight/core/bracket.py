from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gamenight.core.bots import build_bot
from gamenight.core.match import run_match, save_replay_file
from gamenight.core.protocols import GameProtocol


@dataclass(slots=True)
class GameRecord:
    game_index: int
    first_bot: str
    second_bot: str
    winner: str | None
    turns: int
    points: dict[str, int] | None
    replay_file: str


@dataclass(slots=True)
class SeriesResult:
    round_index: int
    match_index: int
    bot_a: str
    bot_b: str
    bye: bool
    games: list[GameRecord] = field(default_factory=list)
    wins: dict[str, int] = field(default_factory=dict)
    points: dict[str, int] = field(default_factory=dict)
    winner: str = ""
    tiebreak: str | None = None


@dataclass(slots=True)
class BracketResult:
    game_id: str
    games_per_match: int
    entrants: list[str]
    rounds: list[list[SeriesResult]]
    champion: str


@dataclass(slots=True)
class RoundRobinResult:
    game_id: str
    games_per_match: int
    entrants: list[str]
    matches: list[SeriesResult]
    standings: dict[str, dict[str, int]]


@dataclass(slots=True)
class TournamentResult:
    game_id: str
    entrants: list[str]
    shuffled_entrants: list[str]
    round_robin: RoundRobinResult
    seeded_entrants: list[str]
    bracket: BracketResult
    overall_standings: dict[str, dict[str, int]]
    champion: str


def run_bracket(
    game_id: str,
    game_impl: GameProtocol,
    entrants: list[str],
    games_per_match: int,
    output_dir: Path,
    seed_base: int | None = None,
) -> BracketResult:
    """Run a single-elimination bracket between `entrants`.

    Each matchup is a series of `games_per_match` games (alternating who goes first).
    The series winner is whoever wins more games; ties are broken by total points
    (battleship's "cells not yet hit" score, via GameProtocol.remaining_points if the
    game implements it) and finally by bracket order (bot_a). A replay file is written
    for every game played.
    """
    if len(entrants) < 2:
        raise ValueError("A bracket needs at least two entrants.")
    if len(set(entrants)) != len(entrants):
        raise ValueError("Entrant names must be unique.")

    output_dir.mkdir(parents=True, exist_ok=True)

    rounds: list[list[SeriesResult]] = []
    current = list(entrants)
    round_index = 0

    while len(current) > 1:
        round_index += 1
        next_round: list[str] = []
        round_results: list[SeriesResult] = []
        match_index = 0
        i = 0
        while i < len(current):
            if i + 1 == len(current):
                bye_bot = current[i]
                round_results.append(
                    SeriesResult(
                        round_index=round_index,
                        match_index=match_index + 1,
                        bot_a=bye_bot,
                        bot_b="",
                        bye=True,
                        winner=bye_bot,
                    )
                )
                next_round.append(bye_bot)
                i += 1
                continue

            match_index += 1
            bot_a, bot_b = current[i], current[i + 1]
            series_seed = None if seed_base is None else seed_base + (round_index * 1000) + match_index
            series = _run_series(
                game_id=game_id,
                game_impl=game_impl,
                bot_a=bot_a,
                bot_b=bot_b,
                games_per_match=games_per_match,
                round_index=round_index,
                match_index=match_index,
                output_dir=output_dir,
                seed_base=series_seed,
            )
            round_results.append(series)
            next_round.append(series.winner)
            i += 2

        rounds.append(round_results)
        current = next_round

    return BracketResult(
        game_id=game_id,
        games_per_match=games_per_match,
        entrants=list(entrants),
        rounds=rounds,
        champion=current[0],
    )


def run_round_robin(
    game_id: str,
    game_impl: GameProtocol,
    entrants: list[str],
    games_per_match: int,
    output_dir: Path,
    seed_base: int | None = None,
) -> RoundRobinResult:
    """Play every pair of `entrants` against each other once (a series of
    `games_per_match` games, alternating who goes first), recording a win/loss
    for each entrant per series. Replay files are written for every game played.
    """
    if len(entrants) < 2:
        raise ValueError("A round robin needs at least two entrants.")
    if len(set(entrants)) != len(entrants):
        raise ValueError("Entrant names must be unique.")

    output_dir.mkdir(parents=True, exist_ok=True)

    standings: dict[str, dict[str, int]] = {name: {"wins": 0, "losses": 0} for name in entrants}
    matches: list[SeriesResult] = []
    match_index = 0

    for i in range(len(entrants)):
        for j in range(i + 1, len(entrants)):
            bot_a, bot_b = entrants[i], entrants[j]
            match_index += 1
            series_seed = None if seed_base is None else seed_base + match_index
            series = _run_series(
                game_id=game_id,
                game_impl=game_impl,
                bot_a=bot_a,
                bot_b=bot_b,
                games_per_match=games_per_match,
                round_index=0,
                match_index=match_index,
                output_dir=output_dir,
                seed_base=series_seed,
            )
            matches.append(series)

            loser = bot_b if series.winner == bot_a else bot_a
            standings[series.winner]["wins"] += 1
            standings[loser]["losses"] += 1

    return RoundRobinResult(
        game_id=game_id,
        games_per_match=games_per_match,
        entrants=list(entrants),
        matches=matches,
        standings=standings,
    )


def _seed_order(ranked: list[str]) -> list[str]:
    """Cross/snake-pair a ranked list (best first) into bracket seed order, e.g.
    [1, 2, 3, 4] -> [1, 4, 2, 3] so the bracket pairs 1-vs-4 and 2-vs-3.
    """
    order: list[str] = []
    i, j = 0, len(ranked) - 1
    while i <= j:
        order.append(ranked[i])
        if i != j:
            order.append(ranked[j])
        i += 1
        j -= 1
    return order


def run_tournament(
    game_id: str,
    game_impl: GameProtocol,
    entrants: list[str],
    bracket_games_per_match: int,
    round_robin_games_per_match: int,
    output_dir: Path,
    seed_base: int | None = None,
    shuffle_seed: int | None = None,
) -> TournamentResult:
    """Run a full tournament: shuffle the entrants, play a round robin, seed a
    single-elimination bracket from the round robin standings (best vs worst,
    cross-paired), then run the bracket. `overall_standings` combines round
    robin and bracket wins/losses per entrant.
    """
    rng = random.Random(shuffle_seed)
    shuffled = list(entrants)
    rng.shuffle(shuffled)

    round_robin = run_round_robin(
        game_id=game_id,
        game_impl=game_impl,
        entrants=shuffled,
        games_per_match=round_robin_games_per_match,
        output_dir=output_dir / "round_robin",
        seed_base=seed_base,
    )

    ranked = sorted(
        shuffled,
        key=lambda name: (
            -round_robin.standings[name]["wins"],
            round_robin.standings[name]["losses"],
            shuffled.index(name),
        ),
    )
    seeded_entrants = _seed_order(ranked)

    bracket_seed_base = None if seed_base is None else seed_base + 500_000
    bracket = run_bracket(
        game_id=game_id,
        game_impl=game_impl,
        entrants=seeded_entrants,
        games_per_match=bracket_games_per_match,
        output_dir=output_dir / "bracket",
        seed_base=bracket_seed_base,
    )

    overall_standings: dict[str, dict[str, int]] = {
        name: dict(round_robin.standings[name]) for name in entrants
    }
    for round_results in bracket.rounds:
        for series in round_results:
            if series.bye:
                continue
            loser = series.bot_b if series.winner == series.bot_a else series.bot_a
            overall_standings[series.winner]["wins"] += 1
            overall_standings[loser]["losses"] += 1

    return TournamentResult(
        game_id=game_id,
        entrants=list(entrants),
        shuffled_entrants=shuffled,
        round_robin=round_robin,
        seeded_entrants=seeded_entrants,
        bracket=bracket,
        overall_standings=overall_standings,
        champion=bracket.champion,
    )


def _run_series(
    game_id: str,
    game_impl: GameProtocol,
    bot_a: str,
    bot_b: str,
    games_per_match: int,
    round_index: int,
    match_index: int,
    output_dir: Path,
    seed_base: int | None,
) -> SeriesResult:
    first_id, second_id = game_impl.player_ids[0], game_impl.player_ids[1]
    has_points = hasattr(game_impl, "remaining_points")

    wins = {bot_a: 0, bot_b: 0}
    points = {bot_a: 0, bot_b: 0}
    games: list[GameRecord] = []

    for game_index in range(games_per_match):
        if game_index % 2 == 0:
            first_bot, second_bot = bot_a, bot_b
        else:
            first_bot, second_bot = bot_b, bot_a

        bots = {
            first_id: build_bot(game_impl, first_bot, first_id, game_id),
            second_id: build_bot(game_impl, second_bot, second_id, game_id),
        }
        match_seed = None if seed_base is None else seed_base * 100 + game_index
        result = run_match(game_impl, bots, seed=match_seed)

        if result.winner == first_id:
            winner_bot: str | None = first_bot
        elif result.winner == second_id:
            winner_bot = second_bot
        else:
            winner_bot = None

        if winner_bot is not None:
            wins[winner_bot] += 1

        game_points: dict[str, int] | None = None
        if has_points:
            final_state = result.replay[-1]["state"] if result.replay else None
            if final_state is not None:
                game_points = {
                    first_bot: game_impl.remaining_points(final_state, first_id),
                    second_bot: game_impl.remaining_points(final_state, second_id),
                }
                points[first_bot] += game_points[first_bot]
                points[second_bot] += game_points[second_bot]

        replay_file = (
            output_dir
            / f"round{round_index}_match{match_index}_{_safe_name(bot_a)}_vs_{_safe_name(bot_b)}"
            f"_game{game_index + 1}.json"
        )
        save_replay_file(result.replay, replay_file)

        games.append(
            GameRecord(
                game_index=game_index + 1,
                first_bot=first_bot,
                second_bot=second_bot,
                winner=winner_bot,
                turns=result.turns,
                points=game_points,
                replay_file=str(replay_file),
            )
        )

    winner, tiebreak = _series_winner(bot_a, bot_b, wins, points if has_points else None)

    return SeriesResult(
        round_index=round_index,
        match_index=match_index,
        bot_a=bot_a,
        bot_b=bot_b,
        bye=False,
        games=games,
        wins=wins,
        points=points if has_points else {},
        winner=winner,
        tiebreak=tiebreak,
    )


def _safe_name(name: str) -> str:
    return name.replace(":", "-")


def _series_winner(
    bot_a: str,
    bot_b: str,
    wins: dict[str, int],
    points: dict[str, int] | None,
) -> tuple[str, str | None]:
    if wins[bot_a] != wins[bot_b]:
        return (bot_a, None) if wins[bot_a] > wins[bot_b] else (bot_b, None)

    if points is not None and points[bot_a] != points[bot_b]:
        winner = bot_a if points[bot_a] > points[bot_b] else bot_b
        return winner, "points"

    return bot_a, "bracket-order"


def _series_to_dict(series: SeriesResult) -> dict[str, Any]:
    return {
        "round_index": series.round_index,
        "match_index": series.match_index,
        "bot_a": series.bot_a,
        "bot_b": series.bot_b,
        "bye": series.bye,
        "wins": series.wins,
        "points": series.points,
        "winner": series.winner,
        "tiebreak": series.tiebreak,
        "games": [
            {
                "game_index": game.game_index,
                "first_bot": game.first_bot,
                "second_bot": game.second_bot,
                "winner": game.winner,
                "turns": game.turns,
                "points": game.points,
                "replay_file": game.replay_file,
            }
            for game in series.games
        ],
    }


def bracket_to_dict(bracket: BracketResult) -> dict[str, Any]:
    return {
        "game_id": bracket.game_id,
        "games_per_match": bracket.games_per_match,
        "entrants": bracket.entrants,
        "champion": bracket.champion,
        "rounds": [
            [_series_to_dict(series) for series in round_results]
            for round_results in bracket.rounds
        ],
    }


def tournament_to_dict(tournament: TournamentResult) -> dict[str, Any]:
    return {
        "game_id": tournament.game_id,
        "entrants": tournament.entrants,
        "shuffled_entrants": tournament.shuffled_entrants,
        "seeded_entrants": tournament.seeded_entrants,
        "champion": tournament.champion,
        "overall_standings": tournament.overall_standings,
        "round_robin": {
            "games_per_match": tournament.round_robin.games_per_match,
            "entrants": tournament.round_robin.entrants,
            "standings": tournament.round_robin.standings,
            "matches": [_series_to_dict(series) for series in tournament.round_robin.matches],
        },
        "bracket": bracket_to_dict(tournament.bracket),
    }


def bracket_to_text(bracket: BracketResult) -> str:
    lines = [f"Bracket: {bracket.game_id}  |  games per match: {bracket.games_per_match}"]
    lines.append(f"Entrants: {', '.join(bracket.entrants)}")
    for round_results in bracket.rounds:
        lines.append(f"\n-- Round {round_results[0].round_index} --")
        for series in round_results:
            if series.bye:
                lines.append(f"  {series.bot_a} advances on a bye")
                continue
            score = f"{series.wins[series.bot_a]}-{series.wins[series.bot_b]}"
            line = f"  {series.bot_a} vs {series.bot_b}: {score} -> winner {series.winner}"
            if series.tiebreak:
                points_a, points_b = series.points[series.bot_a], series.points[series.bot_b]
                line += f" (tiebreak: {series.tiebreak}, points {points_a}-{points_b})"
            lines.append(line)
    lines.append(f"\nChampion: {bracket.champion}")
    return "\n".join(lines)


def tournament_to_text(tournament: TournamentResult) -> str:
    lines = [f"Tournament: {tournament.game_id}"]
    lines.append(f"Entrants (shuffled order): {', '.join(tournament.shuffled_entrants)}")

    lines.append("\n-- Round Robin --")
    for series in tournament.round_robin.matches:
        score = f"{series.wins[series.bot_a]}-{series.wins[series.bot_b]}"
        line = f"  {series.bot_a} vs {series.bot_b}: {score} -> winner {series.winner}"
        if series.tiebreak:
            points_a, points_b = series.points[series.bot_a], series.points[series.bot_b]
            line += f" (tiebreak: {series.tiebreak}, points {points_a}-{points_b})"
        lines.append(line)

    lines.append("\n-- Round Robin Standings --")
    standings = tournament.round_robin.standings
    ranked = sorted(
        tournament.shuffled_entrants,
        key=lambda name: (-standings[name]["wins"], standings[name]["losses"]),
    )
    for name in ranked:
        record = standings[name]
        lines.append(f"  {name}: {record['wins']}-{record['losses']}")

    lines.append(f"\nBracket seeding: {', '.join(tournament.seeded_entrants)}")
    lines.append("\n" + bracket_to_text(tournament.bracket))

    lines.append("\n-- Overall Standings --")
    overall = tournament.overall_standings
    ranked_overall = sorted(
        tournament.entrants,
        key=lambda name: (-overall[name]["wins"], overall[name]["losses"]),
    )
    for name in ranked_overall:
        record = overall[name]
        lines.append(f"  {name}: {record['wins']}-{record['losses']}")

    lines.append(f"\nChampion: {tournament.champion}")
    return "\n".join(lines)
