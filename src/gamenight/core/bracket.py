from __future__ import annotations

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


def bracket_to_dict(bracket: BracketResult) -> dict[str, Any]:
    return {
        "game_id": bracket.game_id,
        "games_per_match": bracket.games_per_match,
        "entrants": bracket.entrants,
        "champion": bracket.champion,
        "rounds": [
            [
                {
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
                for series in round_results
            ]
            for round_results in bracket.rounds
        ],
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
