# How To Add A Game

1. Create a new directory under `src/gamenight/games/<game_name>`.
2. Implement a game class that follows the shared protocol:
   - `create_initial_state`
   - `current_player`
   - `legal_actions`
   - `observe`
   - `step`
   - `render_text`
3. Add game-specific bot docs:
   - `BOT_SPEC.md`
   - `EXAMPLES.md`
   - `prompts/greedy_bot_prompt.md`
4. Register the game in `src/gamenight/games/__init__.py`.

## Game Folder Template

```
src/gamenight/games/<game_name>/
  game.py
  BOT_SPEC.md
  EXAMPLES.md
  prompts/
    greedy_bot_prompt.md
  bots/
    baselines/
    players/
```
