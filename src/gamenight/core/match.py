from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from gamenight.core.protocols import BotProtocol, GameProtocol
from gamenight.core.types import MatchContext


@dataclass(slots=True)
class MatchResult:
    winner: str | None
    turns: int
    replay: list[dict[str, Any]]


def run_match(
    game: GameProtocol,
    bots: dict[str, BotProtocol],
    seed: int | None = None,
    max_turns: int = 200,
) -> MatchResult:
    return _run_match_impl(
        game=game,
        bots=bots,
        seed=seed,
        max_turns=max_turns,
        step_observer=None,
        turn_delay_s=0.0,
    )


def run_match_with_observer(
    game: GameProtocol,
    bots: dict[str, BotProtocol],
    seed: int | None = None,
    max_turns: int = 200,
    step_observer: Callable[[dict[str, Any]], None] | None = None,
    turn_delay_s: float = 0.0,
) -> MatchResult:
    return _run_match_impl(
        game=game,
        bots=bots,
        seed=seed,
        max_turns=max_turns,
        step_observer=step_observer,
        turn_delay_s=turn_delay_s,
    )


def _run_match_impl(
    game: GameProtocol,
    bots: dict[str, BotProtocol],
    seed: int | None,
    max_turns: int,
    step_observer: Callable[[dict[str, Any]], None] | None,
    turn_delay_s: float,
) -> MatchResult:
    player_ids = list(bots.keys())
    context = MatchContext(game_id=game.game_id, seed=seed, player_ids=player_ids, max_turns=max_turns)

    for bot in bots.values():
        bot.reset(context)

    state = game.create_initial_state(seed=seed)
    if step_observer is not None:
        step_observer({"turn": 0, "player_id": None, "action": None, "state": state, "done": False})

    replay: list[dict[str, Any]] = []
    turns = 0

    while turns < max_turns:
        turns += 1
        player_id = game.current_player(state)
        bot = bots[player_id]

        observation = game.observe(state, player_id)
        legal_actions = game.legal_actions(state, player_id)
        observation["legal_actions"] = legal_actions

        action = bot.choose_action(observation, context)
        if action not in legal_actions:
            action = legal_actions[0]

        step_result = game.step(state, action)
        replay_event = {
            "turn": turns,
            "player_id": player_id,
            "action": action,
            "state": step_result.next_state,
            "events": step_result.events,
            "rewards": step_result.rewards,
            "done": step_result.done,
        }
        replay.append(replay_event)
        state = step_result.next_state

        if step_observer is not None:
            step_observer(replay_event)

        if turn_delay_s > 0:
            time.sleep(turn_delay_s)

        if step_result.done:
            winner = _winner_from_rewards(step_result.rewards)
            return MatchResult(winner=winner, turns=turns, replay=replay)

    return MatchResult(winner=None, turns=turns, replay=replay)


def save_replay_file(replay: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(replay, indent=2), encoding="utf-8")


def load_replay_file(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _winner_from_rewards(rewards: dict[str, float]) -> str | None:
    sorted_rewards = sorted(rewards.items(), key=lambda item: item[1], reverse=True)
    if not sorted_rewards:
        return None
    top_player, top_score = sorted_rewards[0]
    if len(sorted_rewards) > 1 and top_score == sorted_rewards[1][1]:
        return None
    return top_player
