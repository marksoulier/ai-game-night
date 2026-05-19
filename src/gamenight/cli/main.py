from __future__ import annotations

import hashlib
import importlib.util
import random
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import typer

from gamenight.core.match import load_replay_file, run_match, run_match_with_observer, save_replay_file
from gamenight.core.replay import replay_to_text
from gamenight.games import build_registry
from gamenight.games.tictactoe.bots.baselines.greedy_bot import GreedyBot
from gamenight.games.tictactoe.bots.baselines.human_terminal import HumanTerminalBot
from gamenight.games.tictactoe.bots.baselines.random_bot import RandomBot

app = typer.Typer(no_args_is_help=True)


@dataclass(slots=True)
class SeriesSummary:
    game_id: str
    games: int
    bot_a: str
    bot_b: str
    starting_policy: str
    order_seed: int | None
    order_key: str
    first_player_counts: dict[str, int]
    wins: dict[str, int]
    draws: int


@app.command("list-games")
def list_games() -> None:
    registry = build_registry()
    for game_id in registry.list_game_ids():
        typer.echo(game_id)


@app.command("run-game")
def run_game(
    game: str = typer.Option("tictactoe", help="Game id to run."),
    mode: str = typer.Option("headless", help="Runtime mode: headless or gui."),
    bot_x: str = typer.Option(
        "greedy",
        help="Bot for player_x: greedy, random, human, or player:<folder_name>.",
    ),
    bot_o: str = typer.Option(
        "random",
        help="Bot for player_o: greedy, random, human, or player:<folder_name>.",
    ),
    gui_delay: float = typer.Option(0.5, help="Delay (seconds) between GUI turns."),
    replay_file: Path = typer.Option(Path("artifacts/latest_replay.json"), help="Replay output path."),
) -> None:
    registry = build_registry()
    game_impl = registry.get(game)

    bots = {
        "player_x": _build_bot(bot_x, "player_x"),
        "player_o": _build_bot(bot_o, "player_o"),
    }

    if mode not in {"headless", "gui"}:
        raise typer.BadParameter("mode must be 'headless' or 'gui'")

    if mode == "gui":
        if game != "tictactoe":
            raise typer.BadParameter("GUI mode is currently implemented for tictactoe only.")
        result = _run_tictactoe_gui_match(game_impl, bots, gui_delay)
    else:
        result = run_match(game_impl, bots)

    save_replay_file(result.replay, replay_file)

    typer.echo(f"winner={result.winner} turns={result.turns}")
    typer.echo(f"replay={replay_file}")


@app.command("run-series")
def run_series(
    game: str = typer.Option("tictactoe", help="Game id to run."),
    bot_a: str = typer.Option("greedy", help="Competitor A bot: greedy, random, human, or player:<folder_name>."),
    bot_b: str = typer.Option("random", help="Competitor B bot: greedy, random, human, or player:<folder_name>."),
    games: int = typer.Option(100, min=1, help="Number of games to run."),
    starting_policy: str = typer.Option(
        "random",
        help="Who starts each game: fixed-a, fixed-b, alternate, or random.",
    ),
    order_seed: int | None = typer.Option(
        None,
        help="Seed used for randomized start order when starting-policy=random.",
    ),
    order_key: str = typer.Option(
        "default",
        help="Extra namespace for unique randomized order configs.",
    ),
    match_seed_base: int | None = typer.Option(
        None,
        help="Optional base seed for game internals; each game uses match_seed_base + game_index.",
    ),
    summary_file: Path = typer.Option(
        Path("artifacts/series_summary.json"),
        help="Output JSON file for series summary.",
    ),
) -> None:
    registry = build_registry()
    game_impl = registry.get(game)

    policy = starting_policy.strip().lower()
    allowed_policies = {"fixed-a", "fixed-b", "alternate", "random"}
    if policy not in allowed_policies:
        raise typer.BadParameter("starting-policy must be one of: fixed-a, fixed-b, alternate, random")

    wins = {"bot_a": 0, "bot_b": 0}
    first_player_counts = {"bot_a": 0, "bot_b": 0}
    draws = 0

    for game_index in range(games):
        first = _series_first_player(
            policy=policy,
            game_index=game_index,
            order_seed=order_seed,
            order_key=order_key,
        )
        first_player_counts[first] += 1

        if first == "bot_a":
            x_name, o_name = "bot_a", "bot_b"
            x_bot_name, o_bot_name = bot_a, bot_b
        else:
            x_name, o_name = "bot_b", "bot_a"
            x_bot_name, o_bot_name = bot_b, bot_a

        bots = {
            "player_x": _build_bot(x_bot_name, "player_x"),
            "player_o": _build_bot(o_bot_name, "player_o"),
        }
        match_seed = None if match_seed_base is None else match_seed_base + game_index
        result = run_match(game_impl, bots, seed=match_seed)

        if result.winner is None:
            draws += 1
            continue

        winner_name = x_name if result.winner == "player_x" else o_name
        wins[winner_name] += 1

    summary = SeriesSummary(
        game_id=game,
        games=games,
        bot_a=bot_a,
        bot_b=bot_b,
        starting_policy=policy,
        order_seed=order_seed,
        order_key=order_key,
        first_player_counts=first_player_counts,
        wins=wins,
        draws=draws,
    )

    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(_to_pretty_json(asdict(summary)), encoding="utf-8")

    typer.echo(f"series_games={games} wins_bot_a={wins['bot_a']} wins_bot_b={wins['bot_b']} draws={draws}")
    typer.echo(f"first_player_bot_a={first_player_counts['bot_a']} first_player_bot_b={first_player_counts['bot_b']}")
    typer.echo(f"summary={summary_file}")


@app.command("replay")
def replay(
    replay_file: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False),
    rows: int = typer.Option(30, help="Maximum rows to print."),
) -> None:
    replay_events = load_replay_file(replay_file)
    typer.echo(replay_to_text(replay_events, max_rows=rows))


def _build_bot(bot_name: str, bot_id: str):
    name = bot_name.lower().strip()
    if name == "random":
        return RandomBot(bot_id=bot_id)
    if name == "human":
        return HumanTerminalBot(bot_id=bot_id)
    if name == "greedy":
        return GreedyBot(bot_id=bot_id)
    if name.startswith("player:"):
        player_name = name.split(":", maxsplit=1)[1].strip()
        return _load_player_bot(player_name=player_name, bot_id=bot_id)
    raise ValueError(f"Unknown bot name: {bot_name}")


def _load_player_bot(player_name: str, bot_id: str):
    if not player_name:
        raise ValueError("Player bot name cannot be empty. Use player:<folder_name>.")

    players_root = Path(__file__).resolve().parent.parent / "games" / "tictactoe" / "bots" / "players"
    bot_file = players_root / player_name / "bot.py"
    if not bot_file.exists():
        raise FileNotFoundError(f"Player bot file not found: {bot_file}")

    module_name = f"gamenight_tictactoe_player_{player_name}"
    spec = importlib.util.spec_from_file_location(module_name, bot_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec for {bot_file}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "PlayerBot"):
        raise AttributeError(f"Expected class 'PlayerBot' in {bot_file}")

    return module.PlayerBot(bot_id=bot_id)


def _series_first_player(
    policy: str,
    game_index: int,
    order_seed: int | None,
    order_key: str,
) -> str:
    if policy == "fixed-a":
        return "bot_a"
    if policy == "fixed-b":
        return "bot_b"
    if policy == "alternate":
        return "bot_a" if game_index % 2 == 0 else "bot_b"

    if order_seed is None:
        bit = secrets.randbits(1)
        return "bot_a" if bit == 0 else "bot_b"

    raw = f"{order_seed}:{order_key}:{game_index}".encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return "bot_a" if digest[0] % 2 == 0 else "bot_b"


def _to_pretty_json(data: Any) -> str:
    import json

    return json.dumps(data, indent=2)


def _run_tictactoe_gui_match(game_impl, bots, gui_delay: float):
    from gamenight.games.tictactoe.gui import TicTacToeViewer

    viewer = TicTacToeViewer()

    def step_observer(event: dict) -> None:
        viewer.update_state(
            state=event["state"],
            turn=event["turn"],
            acting_player=event["player_id"],
            action=event["action"],
        )

    try:
        result = run_match_with_observer(
            game=game_impl,
            bots=bots,
            step_observer=step_observer,
            turn_delay_s=max(0.0, gui_delay),
        )
        typer.echo("GUI match complete. Close the game window when finished viewing.")
        viewer.wait_until_closed()
        return result
    finally:
        viewer.close()


if __name__ == "__main__":
    app()
