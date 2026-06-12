from __future__ import annotations

import glob
import hashlib
import py_compile
import re
import secrets
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import typer

from gamenight.core.bots import build_bot
from gamenight.core.bracket import (
    bracket_to_dict,
    bracket_to_text,
    run_bracket,
    run_tournament,
    tournament_to_dict,
    tournament_to_text,
)
from gamenight.core.match import (
    MatchResult,
    load_replay_file,
    run_match,
    run_match_with_observer,
    save_replay_file,
)
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
        first_id: build_bot(game_impl, bot_1, first_id, game),
        second_id: build_bot(game_impl, bot_2, second_id, game),
    }

    if mode not in {"headless", "gui"}:
        raise typer.BadParameter("mode must be 'headless' or 'gui'")

    if mode == "gui":
        matchup_label = None if game == "battleship" else f"{first_id} ({bot_1})  vs  {second_id} ({bot_2})"
        viewer = _build_viewer(game, matchup_label)
        if hasattr(viewer, "set_names"):
            viewer.set_names({first_id: bot_1, second_id: bot_2})
        try:
            result = _run_gui_game(game_impl, bots, gui_delay, viewer)
            if hasattr(viewer, "set_records"):
                viewer.set_records(_single_game_records(result, first_id, second_id))
            typer.echo("GUI match complete. Close the game window when finished viewing.")
            viewer.wait_until_closed()
        finally:
            viewer.close()
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
    mode: str = typer.Option(
        "headless", help="Runtime mode: headless or gui. GUI mode replays each game live; best for small --games counts."
    ),
    gui_delay: float = typer.Option(0.5, help="Delay (seconds) between GUI turns (gui mode only)."),
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

    if mode not in {"headless", "gui"}:
        raise typer.BadParameter("mode must be 'headless' or 'gui'")

    wins = {"bot_a": 0, "bot_b": 0}
    losses = {"bot_a": 0, "bot_b": 0}
    first_player_counts = {"bot_a": 0, "bot_b": 0}
    draws = 0

    viewer: GameViewerProtocol | None = None
    if mode == "gui":
        viewer = _build_viewer(game, f"{bot_a} vs {bot_b}  (best of {games})")

    try:
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
                first_id: build_bot(game_impl, first_bot_name, first_id, game),
                second_id: build_bot(game_impl, second_bot_name, second_id, game),
            }
            match_seed = None if match_seed_base is None else match_seed_base + game_index

            if viewer is not None:
                if hasattr(viewer, "set_names"):
                    viewer.set_names({first_id: first_bot_name, second_id: second_bot_name})
                result = _run_gui_game(game_impl, bots, gui_delay, viewer, seed=match_seed)
            else:
                result = run_match(game_impl, bots, seed=match_seed)

            if result.winner is None:
                draws += 1
            else:
                winner_name = first_name if result.winner == first_id else second_name
                loser_name = "bot_b" if winner_name == "bot_a" else "bot_a"
                wins[winner_name] += 1
                losses[loser_name] += 1

            if viewer is not None and hasattr(viewer, "set_records"):
                viewer.set_records(
                    {
                        first_id: (wins[first_name], losses[first_name]),
                        second_id: (wins[second_name], losses[second_name]),
                    }
                )
    finally:
        if viewer is not None:
            typer.echo("GUI series complete. Close the game window when finished viewing.")
            viewer.wait_until_closed()
            viewer.close()

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


@app.command("run-bracket")
def run_bracket_cmd(
    game: str = typer.Option("battleship", help="Game id to run."),
    bots: str = typer.Option(
        ...,
        help="Comma-separated list of competing bots, in seed order, e.g. "
        "'greedy,random,player:mark,player:example_player'.",
    ),
    games_per_match: int = typer.Option(
        3, min=1, help="Number of games each matchup plays (alternating who goes first)."
    ),
    seed: int | None = typer.Option(
        None, help="Optional base seed for reproducible matches."
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/bracket"), help="Directory for per-game replay files and the bracket summary."
    ),
) -> None:
    registry = build_registry()
    game_impl = registry.get(game)

    entrants = [name.strip() for name in bots.split(",") if name.strip()]

    bracket = run_bracket(
        game_id=game,
        game_impl=game_impl,
        entrants=entrants,
        games_per_match=games_per_match,
        output_dir=output_dir,
        seed_base=seed,
    )

    typer.echo(bracket_to_text(bracket))

    summary_file = output_dir / "bracket_summary.json"
    summary_file.write_text(_to_pretty_json(bracket_to_dict(bracket)), encoding="utf-8")
    typer.echo(f"\nsummary={summary_file}")


@app.command("run-tournament")
def run_tournament_cmd(
    game: str = typer.Option("battleship", help="Game id to run."),
    bots: str = typer.Option(
        ...,
        help="Comma-separated list of competing bots, e.g. "
        "'greedy,random,player:mark,player:example_player'. The order is shuffled "
        "before play (see --shuffle-seed).",
    ),
    bracket_games: int = typer.Option(
        3, min=1, help="Number of games each bracket matchup plays (alternating who goes first)."
    ),
    round_robin_games: int = typer.Option(
        1, min=1, help="Number of games each round-robin matchup plays (alternating who goes first)."
    ),
    shuffle_seed: int | None = typer.Option(
        None, help="Optional seed for shuffling entrant order before the round robin."
    ),
    seed: int | None = typer.Option(
        None, help="Optional base seed for reproducible matches."
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/tournament"), help="Directory for per-game replay files and the tournament summary."
    ),
) -> None:
    """Run a full tournament: shuffle the entrants, play a round robin, seed a
    single-elimination bracket from the round robin standings, then run the bracket.
    """
    registry = build_registry()
    game_impl = registry.get(game)

    entrants = [name.strip() for name in bots.split(",") if name.strip()]

    tournament = run_tournament(
        game_id=game,
        game_impl=game_impl,
        entrants=entrants,
        bracket_games_per_match=bracket_games,
        round_robin_games_per_match=round_robin_games,
        output_dir=output_dir,
        seed_base=seed,
        shuffle_seed=shuffle_seed,
    )

    typer.echo(tournament_to_text(tournament))

    summary_file = output_dir / "tournament_summary.json"
    summary_file.write_text(_to_pretty_json(tournament_to_dict(tournament)), encoding="utf-8")
    typer.echo(f"\nsummary={summary_file}")


@app.command("replay")
def replay(
    replay_file: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False),
    rows: int = typer.Option(30, help="Maximum rows to print."),
) -> None:
    replay_events = load_replay_file(replay_file)
    typer.echo(replay_to_text(replay_events, max_rows=rows))


@app.command("replay-bracket-gui")
def replay_bracket_gui(
    bracket_dir: Path = typer.Option(
        Path("artifacts/bracket"),
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Directory containing tournament_summary.json or bracket_summary.json and the "
        "per-game replay files they reference (produced by `run-tournament` or `run-bracket`).",
    ),
    first_game_delay: float = typer.Option(
        0.5, help="Delay (seconds) between turns for each match's first game."
    ),
    rest_delay: float = typer.Option(
        0.05, help="Delay (seconds) between turns for every game after a match's first."
    ),
    final: bool = typer.Option(
        False,
        "--final",
        help="Skip the reveal animation and immediately show the completed bracket "
        "(all winners/scores filled in, final standings, champion) plus the final "
        "board state of the championship match.",
    ),
) -> None:
    """Open a bracket "reveal" GUI: shows the full bracket with later rounds blank,
    and a "Play Next Match" button that replays each match's saved games (first game
    slow, the rest fast) on an embedded board, then fills in the winner -- propagating
    it into the next round -- until the champion is revealed.

    If a `tournament_summary.json` is present (from `run-tournament`), the round robin
    standings, round robin results, and live overall standings are also displayed.
    """
    import json

    summary_file = bracket_dir / "tournament_summary.json"
    if not summary_file.exists():
        summary_file = bracket_dir / "bracket_summary.json"
    if not summary_file.exists():
        raise typer.BadParameter(f"No tournament_summary.json or bracket_summary.json found in {bracket_dir}")

    summary = json.loads(summary_file.read_text(encoding="utf-8"))

    if summary["game_id"] != "battleship":
        raise typer.BadParameter(
            f"replay-bracket-gui currently only supports battleship brackets (got '{summary['game_id']}')."
        )

    from gamenight.games.battleship.bracket_gui import BracketRevealViewer

    viewer = BracketRevealViewer(
        summary, bracket_dir, first_game_delay=first_game_delay, rest_delay=rest_delay, show_final=final
    )
    try:
        viewer.run()
    finally:
        viewer.close()


_GAME_NUMBER_RE = re.compile(r"_game(\d+)\.json$")


@app.command("replay-series-gui")
def replay_series_gui(
    game: str = typer.Option("battleship", help="Game id (selects the GUI viewer)."),
    replay_glob: str = typer.Option(
        ...,
        help="Glob pattern matching saved replay JSON files for one series, e.g. "
        "'artifacts/bracket/round2_match1_random_vs_player-mark_game*.json'. "
        "Files are played in order of their trailing _gameN number.",
    ),
    first_game_delay: float = typer.Option(
        0.5, help="Delay (seconds) between turns for the first replay file."
    ),
    rest_delay: float = typer.Option(
        0.05, help="Delay (seconds) between turns for every replay file after the first."
    ),
) -> None:
    """Replay a saved series of games live in the GUI.

    The first replay file plays slowly (so you can follow placement and early shots),
    then every remaining file plays fast. This re-renders saved state snapshots only --
    no bots run and nothing is recomputed, so it's an exact replay of what happened.
    """
    paths = [Path(p) for p in glob.glob(replay_glob)]
    if not paths:
        raise typer.BadParameter(f"No replay files matched: {replay_glob}")

    def sort_key(path: Path) -> tuple[int, str]:
        match = _GAME_NUMBER_RE.search(path.name)
        return (int(match.group(1)) if match else 1 << 30, path.name)

    paths.sort(key=sort_key)

    matchup_label = paths[0].stem.rsplit("_game", 1)[0].replace("_", " ")
    viewer = _build_viewer(game, matchup_label)

    try:
        for index, path in enumerate(paths):
            delay = first_game_delay if index == 0 else rest_delay
            replay_events = load_replay_file(path)
            typer.echo(f"Replaying {path} ({len(replay_events)} turns, delay={delay}s)")
            for event in replay_events:
                if viewer.closed:
                    break
                viewer.update_state(
                    state=event["state"],
                    turn=event["turn"],
                    acting_player=event["player_id"],
                    action=event["action"],
                )
                if delay > 0:
                    time.sleep(delay)
            if viewer.closed:
                break

        typer.echo("Replay complete. Close the game window when finished viewing.")
        viewer.wait_until_closed()
    finally:
        viewer.close()


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


def _build_viewer(game_id: str, matchup_label: str | None) -> GameViewerProtocol:
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


def _run_gui_game(
    game_impl: GameProtocol,
    bots: dict[str, BotProtocol],
    gui_delay: float,
    viewer: GameViewerProtocol,
    seed: int | None = None,
):
    """Run a single game against a live viewer. Caller owns the viewer's lifecycle
    (set_names/set_records before and after, wait_until_closed/close when fully done) --
    this just plays one game and updates the board as it goes."""

    def step_observer(event: dict) -> None:
        viewer.update_state(
            state=event["state"],
            turn=event["turn"],
            acting_player=event["player_id"],
            action=event["action"],
        )

    return run_match_with_observer(
        game=game_impl,
        bots=bots,
        seed=seed,
        step_observer=step_observer,
        turn_delay_s=max(0.0, gui_delay),
    )


def _single_game_records(result: MatchResult, first_id: str, second_id: str) -> dict[str, tuple[int, int]]:
    if result.winner == first_id:
        return {first_id: (1, 0), second_id: (0, 1)}
    if result.winner == second_id:
        return {first_id: (0, 1), second_id: (1, 0)}
    return {first_id: (0, 0), second_id: (0, 0)}


if __name__ == "__main__":
    app()
