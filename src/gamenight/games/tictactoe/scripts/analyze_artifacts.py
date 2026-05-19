from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer

app = typer.Typer(no_args_is_help=True)


@dataclass(slots=True)
class ReplayGameStats:
    turns: int
    winner: str | None
    opening_index: int | None
    x_moves: list[int]
    o_moves: list[int]
    final_board: str


@app.command("analyze")
def analyze(
    artifacts_dir: Path = typer.Option(Path("artifacts"), help="Directory with artifact JSON files."),
    pattern: str = typer.Option("*.json", help="Glob pattern inside artifacts directory."),
    output_file: Path | None = typer.Option(None, help="Optional output file for computed statistics JSON."),
    top_n: int = typer.Option(10, min=1, max=50, help="How many top entries to show for ranked stats."),
) -> None:
    files = sorted(artifacts_dir.glob(pattern))
    if not files:
        raise typer.BadParameter(f"No files matched pattern '{pattern}' in {artifacts_dir}")

    replay_games: list[ReplayGameStats] = []
    series_docs: list[dict[str, Any]] = []
    unknown_files: list[str] = []
    parse_errors: dict[str, str] = {}

    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            parse_errors[str(path)] = str(exc)
            continue

        if _looks_like_replay(payload):
            stats = _replay_stats(payload)
            if stats is None:
                unknown_files.append(str(path))
            else:
                replay_games.append(stats)
            continue

        if _looks_like_series_summary(payload):
            series_docs.append(payload)
            continue

        unknown_files.append(str(path))

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "input": {
            "artifacts_dir": str(artifacts_dir),
            "pattern": pattern,
            "files_scanned": len(files),
        },
        "file_kinds": {
            "replay_files": len(replay_games),
            "series_summary_files": len(series_docs),
            "unknown_files": len(unknown_files),
            "parse_errors": len(parse_errors),
        },
        "replay_stats": _aggregate_replay_stats(replay_games, top_n=top_n),
        "series_stats": _aggregate_series_stats(series_docs),
        "unknown_files": unknown_files,
        "parse_errors": parse_errors,
    }

    pretty = json.dumps(report, indent=2)
    typer.echo(pretty)

    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(pretty, encoding="utf-8")
        typer.echo(f"saved={output_file}")


def _looks_like_replay(payload: Any) -> bool:
    return isinstance(payload, list) and all(isinstance(item, dict) for item in payload)


def _looks_like_series_summary(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return all(key in payload for key in ("games", "wins", "draws"))


def _replay_stats(events: list[dict[str, Any]]) -> ReplayGameStats | None:
    if not events:
        return None

    last = events[-1]
    state = last.get("state", {})
    turns = int(state.get("turn_index", len(events)))
    winner = state.get("winner")

    opening_index = None
    first_action = events[0].get("action", {}) if events else {}
    if isinstance(first_action, dict) and "index" in first_action:
        opening_index = int(first_action["index"])

    x_moves: list[int] = []
    o_moves: list[int] = []

    for event in events:
        player_id = event.get("player_id")
        action = event.get("action", {})
        if not isinstance(action, dict) or "index" not in action:
            continue

        index = int(action["index"])
        if player_id == "player_x":
            x_moves.append(index)
        elif player_id == "player_o":
            o_moves.append(index)

    board = state.get("board", [" "] * 9)
    if not isinstance(board, list) or len(board) != 9:
        board = [" "] * 9
    final_board = "".join(str(cell) for cell in board)

    return ReplayGameStats(
        turns=turns,
        winner=winner,
        opening_index=opening_index,
        x_moves=x_moves,
        o_moves=o_moves,
        final_board=final_board,
    )


def _aggregate_replay_stats(games: list[ReplayGameStats], top_n: int) -> dict[str, Any]:
    if not games:
        return {"games": 0}

    games_count = len(games)
    outcomes = Counter(game.winner if game.winner is not None else "draw" for game in games)

    turns = [game.turns for game in games]
    turns_by_outcome: dict[str, list[int]] = defaultdict(list)
    for game in games:
        key = game.winner if game.winner is not None else "draw"
        turns_by_outcome[key].append(game.turns)

    opening_counts = Counter(
        game.opening_index for game in games if game.opening_index is not None
    )
    opening_win_counts = Counter(
        game.opening_index for game in games if game.opening_index is not None and game.winner == "player_x"
    )

    x_cell_usage = Counter()
    o_cell_usage = Counter()
    for game in games:
        x_cell_usage.update(game.x_moves)
        o_cell_usage.update(game.o_moves)

    all_cell_usage = x_cell_usage + o_cell_usage

    final_boards = Counter(game.final_board for game in games)

    x_first_wins = outcomes.get("player_x", 0)
    o_second_wins = outcomes.get("player_o", 0)
    draws = outcomes.get("draw", 0)

    decisive_games = x_first_wins + o_second_wins
    first_player_non_loss = (x_first_wins + draws) / games_count

    return {
        "games": games_count,
        "outcomes": {
            "player_x_wins": x_first_wins,
            "player_o_wins": o_second_wins,
            "draws": draws,
            "decisive_games": decisive_games,
        },
        "rates": {
            "player_x_win_rate": _ratio(x_first_wins, games_count),
            "player_o_win_rate": _ratio(o_second_wins, games_count),
            "draw_rate": _ratio(draws, games_count),
            "first_player_non_loss_rate": round(first_player_non_loss, 6),
            "first_player_advantage_delta": round(
                _ratio(x_first_wins, games_count) - _ratio(o_second_wins, games_count),
                6,
            ),
        },
        "turns": {
            "avg": round(statistics.mean(turns), 4),
            "median": float(statistics.median(turns)),
            "std_dev": round(statistics.pstdev(turns), 4),
            "min": min(turns),
            "max": max(turns),
            "distribution": dict(sorted(Counter(turns).items())),
            "avg_by_outcome": {
                key: round(statistics.mean(values), 4)
                for key, values in sorted(turns_by_outcome.items())
            },
        },
        "openings": {
            "counts": _sort_counter_dict(opening_counts),
            "x_win_rate_by_opening": {
                str(idx): _ratio(opening_win_counts.get(idx, 0), count)
                for idx, count in sorted(opening_counts.items())
            },
            "opening_entropy_bits": round(_entropy(opening_counts), 6),
        },
        "cell_usage": {
            "all_moves": _sort_counter_dict(all_cell_usage),
            "x_moves": _sort_counter_dict(x_cell_usage),
            "o_moves": _sort_counter_dict(o_cell_usage),
            "x_minus_o": {
                str(idx): x_cell_usage.get(idx, 0) - o_cell_usage.get(idx, 0)
                for idx in range(9)
            },
        },
        "final_boards": {
            "unique_count": len(final_boards),
            "top": [
                {"board": board, "count": count}
                for board, count in final_boards.most_common(top_n)
            ],
        },
    }


def _aggregate_series_stats(series_docs: list[dict[str, Any]]) -> dict[str, Any]:
    if not series_docs:
        return {"series_files": 0}

    total_games = 0
    total_draws = 0
    bot_wins = Counter()
    bot_first = Counter()
    starting_policy_counts = Counter()

    for doc in series_docs:
        games = int(doc.get("games", 0))
        total_games += games
        total_draws += int(doc.get("draws", 0))

        wins = doc.get("wins", {})
        if isinstance(wins, dict):
            bot_a = str(doc.get("bot_a", "bot_a"))
            bot_b = str(doc.get("bot_b", "bot_b"))
            bot_wins[bot_a] += int(wins.get("bot_a", 0))
            bot_wins[bot_b] += int(wins.get("bot_b", 0))

        first_counts = doc.get("first_player_counts", {})
        if isinstance(first_counts, dict):
            bot_a = str(doc.get("bot_a", "bot_a"))
            bot_b = str(doc.get("bot_b", "bot_b"))
            bot_first[bot_a] += int(first_counts.get("bot_a", 0))
            bot_first[bot_b] += int(first_counts.get("bot_b", 0))

        policy = str(doc.get("starting_policy", "unknown"))
        starting_policy_counts[policy] += 1

    total_decisive = max(0, total_games - total_draws)

    return {
        "series_files": len(series_docs),
        "games": total_games,
        "draws": total_draws,
        "decisive_games": total_decisive,
        "draw_rate": _ratio(total_draws, total_games),
        "wins_by_bot": _sort_counter_dict(bot_wins),
        "win_rate_by_bot": {
            bot: _ratio(wins, total_games)
            for bot, wins in sorted(bot_wins.items())
        },
        "first_player_counts_by_bot": _sort_counter_dict(bot_first),
        "first_player_rate_by_bot": {
            bot: _ratio(count, total_games)
            for bot, count in sorted(bot_first.items())
        },
        "starting_policy_counts": _sort_counter_dict(starting_policy_counts),
    }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def _entropy(counter: Counter) -> float:
    total = sum(counter.values())
    if total == 0:
        return 0.0

    value = 0.0
    for count in counter.values():
        p = count / total
        value -= p * math.log2(p)
    return value


def _sort_counter_dict(counter: Counter) -> dict[str, int]:
    return {str(key): int(value) for key, value in sorted(counter.items(), key=lambda item: (str(item[0])))}


if __name__ == "__main__":
    app()
