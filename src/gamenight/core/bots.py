from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

from gamenight.core.protocols import BotProtocol, GameProtocol

GAMES_ROOT = Path(__file__).resolve().parent.parent / "games"


def build_bot(game_impl: GameProtocol, bot_name: str, bot_id: str, game_id: str) -> BotProtocol:
    name = bot_name.lower().strip()
    if name.startswith("player:"):
        player_name = name.split(":", maxsplit=1)[1].strip()
        return load_player_bot(game_id=game_id, player_name=player_name, bot_id=bot_id)
    return game_impl.build_baseline_bot(name, bot_id)


def load_player_bot(game_id: str, player_name: str, bot_id: str) -> BotProtocol:
    if not player_name:
        raise ValueError("Player bot name cannot be empty. Use player:<folder_name>.")

    bot_dir = GAMES_ROOT / game_id / "bots" / "players" / player_name
    source_file = bot_dir / "bot.py"
    encoded_file = bot_dir / "bot.pyc"
    module_name = f"gamenight_{game_id}_player_{player_name}"

    if source_file.exists():
        bot_file: Path = source_file
        spec = importlib.util.spec_from_file_location(module_name, bot_file)
    elif encoded_file.exists():
        # No source present -- this is a "blind" submission shared via `encode-bot`.
        # SourcelessFileLoader runs compiled bytecode directly, with no .py needed.
        bot_file = encoded_file
        loader = importlib.machinery.SourcelessFileLoader(module_name, str(bot_file))
        spec = importlib.util.spec_from_file_location(module_name, bot_file, loader=loader)
    else:
        raise FileNotFoundError(f"Neither bot.py nor bot.pyc found in {bot_dir}")

    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec for {bot_file}")

    module = importlib.util.module_from_spec(spec)
    # Register before exec: dataclasses (and other introspection that resolves
    # `from __future__ import annotations` strings via sys.modules) need the module
    # findable by name while its body is still executing.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    if not hasattr(module, "PlayerBot"):
        raise AttributeError(f"Expected class 'PlayerBot' in {bot_file}")

    return module.PlayerBot(bot_id=bot_id)
