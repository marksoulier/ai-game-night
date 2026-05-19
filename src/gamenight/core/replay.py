from __future__ import annotations

from typing import Any


def replay_to_text(events: list[dict[str, Any]], max_rows: int | None = None) -> str:
    rows: list[str] = []
    limit = max_rows if max_rows is not None else len(events)
    for event in events[:limit]:
        rows.append(
            f"turn={event['turn']} player={event['player_id']} action={event['action']} done={event['done']}"
        )
    return "\n".join(rows)
