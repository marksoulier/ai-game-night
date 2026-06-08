# Infrastructure Agent Instructions

Purpose: this file defines the working contract for the agent that builds and maintains the Game Night framework infrastructure.

This is not the player-bot contract.
Player-facing behavior and game bot APIs are defined in each game's `BOT_SPEC.md`.

## Scope

The infrastructure agent owns framework and platform work, including:

- CLI flows in `src/gamenight/cli`.
- Shared engine/runtime logic in `src/gamenight/core`.
- Cross-game contracts, protocols, replay, and tournament behavior.
- Game registration/discovery and extension points.
- Developer docs and scripts that support framework usage.

The infrastructure agent does not implement competitive player strategy bots under `games/*/bots/players/*` unless explicitly requested.

## Primary Goals

- Keep game modules isolated while maximizing reusable core infrastructure.
- Preserve stable interfaces so existing bots and scripts keep working.
- Favor small, testable, additive changes over broad rewrites.
- Maintain deterministic behavior where seeds/replays are involved.

## Guardrails

- Do not break the `run-game`, `replay`, or `run-tournament` workflows.
- Treat replay artifact shape as a compatibility surface.
- Keep game-specific rules inside game modules, not in core.
- Avoid adding game strategy logic to shared infrastructure.

## Change Workflow

1. Understand current architecture from `docs/ARCHITECTURE.md`.
2. Implement minimal infrastructure changes in `src/gamenight/core` and/or `src/gamenight/cli`.
3. Update docs when behavior or interfaces change.
4. Validate with representative commands before finishing:
   - `uv run gamenight list-games`
   - `uv run gamenight run-game --game tictactoe --mode headless`
   - `uv run gamenight run-game --game connect_four --mode headless --bot-1 greedy --bot-2 random`
   - `uv run gamenight replay --replay-file artifacts/latest_replay.json`

## Definition Of Done

- New/changed infrastructure behavior is reflected in docs.
- Existing player-bot flow remains intact.
- Core flows run without regressions.
- Any new extension point has concise usage guidance.

## Boundaries With Player Agent

Use this file for framework/infrastructure tasks.
Use each game's `BOT_SPEC.md` for player bot implementation tasks.