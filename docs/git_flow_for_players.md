# Git Flow For Players

## Branching

1. Create your branch: `player/<your_name>`.
2. Only add files in your personal bot folder.

## Allowed Change Scope

- Allowed: `src/gamenight/games/<game>/bots/players/<your_name>/**`
- Avoid editing baseline bots, core engine, or other player folders.

## Pull Request Checklist

1. Bot class is named `PlayerBot`.
2. Bot returns valid legal actions.
3. Bot does not use hidden information.
4. Bot passes local run command.
