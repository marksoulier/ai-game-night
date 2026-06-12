# Architecture

This repository uses a modular game architecture:

1. Shared contracts and runners in `src/gamenight/core`.
2. Game-specific modules in `src/gamenight/games/<game_name>`.
3. Game-specific prompts and bot docs stored with each game.

## Runtime Modes

- Headless: Fast simulation for tournaments.
- GUI: Interactive mode for local play (game-specific renderer can be added).
- Replay: Play through saved event logs from match output.

## Information Policy

Bots receive maximum natural information available to a player in a real game.

- Include public state.
- Include current player's private state.
- Include legal actions.
- Include context and recent history as applicable.

Do not provide hidden information from opponents or undealt deck order in imperfect-information games.

## Match Artifact Contract

Each match writes a replay artifact containing ordered events:

- turn
- player_id
- action
- state snapshot
- rewards
- done
- bot_error

This allows game-dependent rendering with shared replay controls.

## Bot Error Handling

A bot's `choose_action` may raise, or may return something that isn't in
`legal_actions`. Either case is caught per-turn: the engine substitutes
`legal_actions[0]`, records a human-readable message in that turn's
`bot_error` field (otherwise `None`), and play continues normally.

This keeps a single misbehaving bot from crashing an entire series/bracket
run — every other match still completes and its replay is saved. Reviewing
`bot_error` across a replay is the way to spot a bot that's silently playing
fallback moves all game.
