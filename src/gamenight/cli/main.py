from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import py_compile
import random
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import typer

from gamenight.core.match import load_replay_file, run_match, run_match_with_observer, save_replay_file
from gamenight.core.protocols import BotProtocol, GameProtocol, GameViewerProtocol
from gamenight.core.replay import replay_to_text
from gamenight.games import build_registry

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
    bot_1: str = typer.Option(
        "greedy",
        help="Bot for the first player (game.player_ids[0]): greedy, random, human, or player:<folder_name>.",
    ),
    bot_2: str = typer.Option(
        "random",
        help="Bot for the second player (game.player_ids[1]): greedy, random, human, or player:<folder_name>.",
    ),
    gui_delay: float = typer.Option(0.5, help="Delay (seconds) between GUI turns."),
    replay_file: Path = typer.Option(Path("artifacts/latest_replay.json"), help="Replay output path."),
) -> None:
    registry = build_registry()
    game_impl = registry.get(game)
    first_id, second_id = game_impl.player_ids[0], game_impl.player_ids[1]

    bots = {
        first_id: _build_bot(game_impl, bot_1, first_id, game),
        second_id: _build_bot(game_impl, bot_2, second_id, game),
    }

    if mode not in {"headless", "gui"}:
        raise typer.BadParameter("mode must be 'headless' or 'gui'")

    if mode == "gui":
        matchup_label = f"{first_id} ({bot_1})  vs  {second_id} ({bot_2})"
        viewer = _build_viewer(game, matchup_label)
        result = _run_gui_match(game_impl, bots, gui_delay, viewer)
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
    first_id, second_id = game_impl.player_ids[0], game_impl.player_ids[1]

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
            first_name, second_name = "bot_a", "bot_b"
            first_bot_name, second_bot_name = bot_a, bot_b
        else:
            first_name, second_name = "bot_b", "bot_a"
            first_bot_name, second_bot_name = bot_b, bot_a

        bots = {
            first_id: _build_bot(game_impl, first_bot_name, first_id, game),
            second_id: _build_bot(game_impl, second_bot_name, second_id, game),
        }
        match_seed = None if match_seed_base is None else match_seed_base + game_index
        result = run_match(game_impl, bots, seed=match_seed)

        if result.winner is None:
            draws += 1
            continue

        winner_name = first_name if result.winner == first_id else second_name
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


@app.command("encode-bot")
def encode_bot(
    game: str = typer.Option(..., help="Game id the bot belongs to."),
    player: str = typer.Option(..., help="Player folder name under bots/players/."),
) -> None:
    """Compile bot.py to bot.pyc so it can be shared and run without exposing source.

    Useful for "submit blind, then play everyone's bot" formats: commit bot.pyc instead
    of bot.py, and opponents can run `player:<name>` exactly as before — the loader picks
    up the compiled file automatically — without reading your strategy first. This is
    obscurity, not security: bytecode can be decompiled by someone who goes looking for
    it, so it only helps with "don't spoil the reveal," not with hiding from a determined
    reader. It is also tied to the Python version that compiled it (this project pins
    Python 3.13 via uv, so it travels fine between participants who run it the normal
    `uv run gamenight ...` way).
    """
    bot_dir = Path(__file__).resolve().parent.parent / "games" / game / "bots" / "players" / player
    source_file = bot_dir / "bot.py"
    encoded_file = bot_dir / "bot.pyc"

    if not source_file.exists():
        raise typer.BadParameter(f"No bot.py found at {source_file}")

    py_compile.compile(str(source_file), cfile=str(encoded_file), doraise=True)

    typer.echo(f"encoded {source_file} -> {encoded_file}")
    typer.echo("Commit bot.pyc (the loader prefers bot.py over bot.pyc when both are")
    typer.echo("present, so remove or .gitignore bot.py once you're ready to go blind).")


def _build_bot(game_impl: GameProtocol, bot_name: str, bot_id: str, game_id: str) -> BotProtocol:
    name = bot_name.lower().strip()
    if name.startswith("player:"):
        player_name = name.split(":", maxsplit=1)[1].strip()
        return _load_player_bot(game_id=game_id, player_name=player_name, bot_id=bot_id)
    return game_impl.build_baseline_bot(name, bot_id)


def _load_player_bot(game_id: str, player_name: str, bot_id: str) -> BotProtocol:
    if not player_name:
        raise ValueError("Player bot name cannot be empty. Use player:<folder_name>.")

    bot_dir = Path(__file__).resolve().parent.parent / "games" / game_id / "bots" / "players" / player_name
    source_file = bot_dir / "bot.py"
    encoded_file = bot_dir / "bot.pyc"
    module_name = f"gamenight_{game_id}_player_{player_name}"

    if source_file.exists():
        bot_file: Path = source_file
        spec = importlib.util.spec_from_file_location(module_name, bot_file)
    elif encoded_file.exists():
        # No source present — this is a "blind" submission shared via `encode-bot`.
        # SourcelessFileLoader runs compiled bytecode directly, with no .py needed.
        bot_file = encoded_file
        loader = importlib.machinery.SourcelessFileLoader(module_name, str(bot_file))
        spec = importlib.util.spec_from_file_location(module_name, bot_file, loader=loader)
    else:
        raise FileNotFoundError(f"Neither bot.py nor bot.pyc found in {bot_dir}")

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


def _build_viewer(game_id: str, matchup_label: str) -> GameViewerProtocol:
    if game_id == "tictactoe":
        from gamenight.games.tictactoe.gui import TicTacToeViewer

        return TicTacToeViewer(matchup_label=matchup_label)
    if game_id == "connect_four":
        from gamenight.games.connect_four.gui import ConnectFourViewer

        return ConnectFourViewer(matchup_label=matchup_label)
    if game_id == "battleship":
        from gamenight.games.battleship.gui import BattleshipViewer

        return BattleshipViewer(matchup_label=matchup_label)
    raise typer.BadParameter(f"GUI mode is not yet implemented for game '{game_id}'.")


def _run_gui_match(
    game_impl: GameProtocol,
    bots: dict[str, BotProtocol],
    gui_delay: float,
    viewer: GameViewerProtocol,
):
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
