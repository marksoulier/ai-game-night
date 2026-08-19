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

from gamenight.core.bots import GAMES_ROOT, build_bot, load_player_bot
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
from gamenight.core.registry import GameRegistry
from gamenight.core.replay import replay_to_text
from gamenight.core.types import MatchContext
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
        help="Bot for the first player (game.player_ids[0]): greedy, random, human, or player:<folder_name>. "
        "Ignored if --bots is given.",
    ),
    bot_2: str = typer.Option(
        "random",
        help="Bot for the second player (game.player_ids[1]): greedy, random, human, or player:<folder_name>. "
        "Ignored if --bots is given.",
    ),
    bots: str | None = typer.Option(
        None,
        help="Comma-separated bots in seat order for an N-player game, e.g. 'greedy,random,player:mark' -- "
        "overrides --bot-1/--bot-2. Player count must be within the game's supported range (see "
        "list-games / the game's own README for its MIN_PLAYERS-MAX_PLAYERS, e.g. Splendor is 2-4).",
    ),
    gui_delay: float = typer.Option(0.5, help="Delay (seconds) between GUI turns."),
    replay_file: Path = typer.Option(Path("artifacts/latest_replay.json"), help="Replay output path."),
) -> None:
    registry = build_registry()
    bot_names = [name.strip() for name in bots.split(",")] if bots else [bot_1, bot_2]
    game_impl = _build_game(registry, game, len(bot_names))
    player_ids = game_impl.player_ids
    if len(bot_names) != len(player_ids):
        raise typer.BadParameter(
            f"Game '{game}' has {len(player_ids)} players ({player_ids}) but {len(bot_names)} bots were given."
        )

    bot_map = {pid: build_bot(game_impl, name, pid, game) for pid, name in zip(player_ids, bot_names)}

    if mode not in {"headless", "gui"}:
        raise typer.BadParameter("mode must be 'headless' or 'gui'")

    if mode == "gui":
        matchup_label = (
            None
            if game == "battleship"
            else "  vs  ".join(f"{pid} ({name})" for pid, name in zip(player_ids, bot_names))
        )
        viewer = _build_viewer(game, matchup_label, player_ids=player_ids)
        if hasattr(viewer, "set_names"):
            viewer.set_names(dict(zip(player_ids, bot_names)))
        try:
            result = _run_gui_game(game_impl, bot_map, gui_delay, viewer)
            if hasattr(viewer, "set_records"):
                viewer.set_records(_single_game_records(result, player_ids))
            typer.echo("GUI match complete. Close the game window when finished viewing.")
            viewer.wait_until_closed()
        finally:
            viewer.close()
    else:
        result = run_match(game_impl, bot_map)

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
    viewer = _build_bracket_viewer(
        summary["game_id"], summary, bracket_dir, first_game_delay=first_game_delay, rest_delay=rest_delay,
        show_final=final,
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


@app.command("check-bot-speed")
def check_bot_speed(
    game: str = typer.Option("splendor", help="Game id whose player bots to check."),
    opponent: str = typer.Option(
        "random",
        help="Baseline bot filling every other seat while each bot is tested -- kept fast on "
        "purpose (greedy/human would add their own thinking time) so only the bot under "
        "test's timing is meaningful.",
    ),
    games: int = typer.Option(3, min=1, help="Headless games to play per bot (more games = more sampled actions)."),
    threshold: float = typer.Option(
        0.5, help="Warn on any single choose_action call slower than this many seconds."
    ),
    only: str | None = typer.Option(
        None, help="Comma-separated player folder names to check (default: everyone under bots/players/)."
    ),
    seed: int | None = typer.Option(None, help="Optional base seed for reproducible games."),
) -> None:
    """Time every submitted player bot's `choose_action` calls, one bot at a time
    (playing against `--opponent` baselines filling every other seat), and warn about
    anyone slower than `--threshold` per action -- run this before a live tournament,
    where one slow bot stalls the whole room waiting on it every time it's up.

    Each bot is tested in isolation against baselines, not against each other, so a
    slow result is attributable to that one bot's own `choose_action` -- nothing else
    running that game is being timed.
    """
    registry = build_registry()
    game_impl = registry.get(game)
    max_turns = 200

    players_dir = GAMES_ROOT / game / "bots" / "players"
    if not players_dir.exists():
        typer.echo(f"No players directory for game '{game}' ({players_dir}).")
        raise typer.Exit()

    candidates = sorted(
        path.name
        for path in players_dir.iterdir()
        if path.is_dir() and ((path / "bot.py").exists() or (path / "bot.pyc").exists())
    )
    if only:
        wanted = {name.strip() for name in only.split(",")}
        missing = wanted - set(candidates)
        if missing:
            raise typer.BadParameter(f"No such player folder(s) under {players_dir}: {', '.join(sorted(missing))}")
        candidates = [name for name in candidates if name in wanted]

    if not candidates:
        typer.echo(f"No player bots found under {players_dir}.")
        raise typer.Exit()

    typer.echo(f"Checking {len(candidates)} bot(s) for '{game}': {', '.join(candidates)}")
    typer.echo(f"({games} game(s) each, vs '{opponent}' filling other seats, threshold {threshold}s/action)\n")

    any_flagged = False
    rows: list[tuple[str, int, float, float, int]] = []

    for player_name in candidates:
        durations: list[float] = []
        error_count = 0

        for game_index in range(games):
            match_seed = None if seed is None else seed + game_index
            player_ids = game_impl.player_ids
            test_seat = player_ids[0]

            bots = {pid: build_bot(game_impl, opponent, pid, game) for pid in player_ids[1:]}
            bots[test_seat] = load_player_bot(game_id=game, player_name=player_name, bot_id=test_seat)

            context = MatchContext(game_id=game, seed=match_seed, player_ids=player_ids, max_turns=max_turns)
            for bot in bots.values():
                bot.reset(context)

            state = game_impl.create_initial_state(seed=match_seed)
            for _turn in range(max_turns):
                current = game_impl.current_player(state)
                legal_actions = game_impl.legal_actions(state, current)
                observation = game_impl.observe(state, current)
                observation["legal_actions"] = legal_actions
                bot = bots[current]

                if current == test_seat:
                    start = time.perf_counter()
                    try:
                        action = bot.choose_action(observation, context)
                    except Exception:
                        action = legal_actions[0]
                        error_count += 1
                    durations.append(time.perf_counter() - start)
                else:
                    action = bot.choose_action(observation, context)

                if action not in legal_actions:
                    action = legal_actions[0]

                step_result = game_impl.step(state, action)
                state = step_result.next_state
                if step_result.done:
                    break

        mean_s = sum(durations) / len(durations) if durations else 0.0
        max_s = max(durations) if durations else 0.0
        rows.append((player_name, len(durations), mean_s, max_s, error_count))

        flagged = max_s > threshold or error_count > 0
        any_flagged = any_flagged or flagged
        status = "SLOW" if max_s > threshold else "ok"
        line = (
            f"  player:{player_name:<20} actions={len(durations):<4} "
            f"mean={mean_s * 1000:7.1f}ms  max={max_s * 1000:7.1f}ms  [{status}]"
        )
        if error_count:
            line += f"  ({error_count} action(s) raised -- see below)"
        typer.echo(line)

        if max_s > threshold:
            typer.echo(
                f"    WARNING: player:{player_name} took {max_s:.2f}s on its slowest action "
                f"(> {threshold:.2f}s threshold) -- too slow for a live tournament."
            )
        if error_count:
            typer.echo(
                f"    WARNING: player:{player_name} raised an exception on {error_count} action(s) "
                "(engine fell back to legal_actions[0] each time -- fix before the tournament)."
            )

    typer.echo("")
    if any_flagged:
        typer.echo("Result: one or more bots need attention before the tournament (see WARNINGs above).")
        raise typer.Exit(code=1)
    typer.echo(f"Result: all {len(candidates)} bot(s) stayed under {threshold:.2f}s/action with no errors.")


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


def _build_game(registry: GameRegistry, game_id: str, num_players: int) -> GameProtocol:
    """Builds a game instance sized for `num_players`.

    Most games are fixed at 2 players (`registry.get(game_id)` with no kwargs). A game
    that supports a configurable player count declares `MIN_PLAYERS`/`MAX_PLAYERS`
    class attributes (see `SplendorGame`) -- for those, requesting a different count
    than the default re-fetches a freshly-sized instance via `num_players=...`, which
    the registry's factory (the game class itself) accepts as a constructor kwarg.
    """
    default = registry.get(game_id)
    if num_players == len(default.player_ids):
        return default

    min_players = getattr(default, "MIN_PLAYERS", len(default.player_ids))
    max_players = getattr(default, "MAX_PLAYERS", len(default.player_ids))
    if not (min_players <= num_players <= max_players):
        raise typer.BadParameter(
            f"Game '{game_id}' supports {min_players}-{max_players} players, got {num_players}."
        )
    return registry.get(game_id, num_players=num_players)


def _build_viewer(
    game_id: str, matchup_label: str | None, player_ids: list[str] | None = None
) -> GameViewerProtocol:
    if game_id == "tictactoe":
        from gamenight.games.tictactoe.gui import TicTacToeViewer

        return TicTacToeViewer(matchup_label=matchup_label)
    if game_id == "connect_four":
        from gamenight.games.connect_four.gui import ConnectFourViewer

        return ConnectFourViewer(matchup_label=matchup_label)
    if game_id == "battleship":
        from gamenight.games.battleship.gui import BattleshipViewer

        return BattleshipViewer(matchup_label=matchup_label)
    if game_id == "splendor":
        from gamenight.games.splendor.gui import SplendorViewer

        return SplendorViewer(player_ids=player_ids or ["player_1", "player_2"], matchup_label=matchup_label)
    if game_id == "mine_duel":
        from gamenight.games.mine_duel.gui import MineDuelViewer

        return MineDuelViewer(matchup_label=matchup_label)
    raise typer.BadParameter(f"GUI mode is not yet implemented for game '{game_id}'.")


def _build_bracket_viewer(
    game_id: str,
    summary: dict[str, Any],
    bracket_dir: Path,
    first_game_delay: float,
    rest_delay: float,
    show_final: bool,
):
    if game_id == "battleship":
        from gamenight.games.battleship.bracket_gui import BracketRevealViewer
    elif game_id == "splendor":
        from gamenight.games.splendor.bracket_gui import BracketRevealViewer
    else:
        raise typer.BadParameter(f"replay-bracket-gui is not yet implemented for game '{game_id}'.")

    return BracketRevealViewer(
        summary, bracket_dir, first_game_delay=first_game_delay, rest_delay=rest_delay, show_final=show_final
    )


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


def _single_game_records(result: MatchResult, player_ids: list[str]) -> dict[str, tuple[int, int]]:
    if result.winner is None:
        return {pid: (0, 0) for pid in player_ids}
    return {pid: ((1, 0) if pid == result.winner else (0, 1)) for pid in player_ids}


if __name__ == "__main__":
    app()
