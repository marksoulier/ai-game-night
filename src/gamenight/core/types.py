from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuntimeMode(str, Enum):
    HEADLESS = "headless"
    GUI = "gui"
    REPLAY = "replay"


Action = dict[str, Any]
Observation = dict[str, Any]


@dataclass(slots=True)
class StepResult:
    next_state: Any
    rewards: dict[str, float]
    done: bool
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class MatchContext:
    game_id: str
    seed: int | None
    player_ids: list[str]
    max_turns: int
