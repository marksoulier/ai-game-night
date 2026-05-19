from gamenight.games import build_registry
from gamenight.games.tictactoe.bots.baselines.greedy_bot import GreedyBot
from gamenight.games.tictactoe.bots.baselines.random_bot import RandomBot
from gamenight.core.tournament import run_round_robin


def main() -> None:
    registry = build_registry()
    game = registry.get("tictactoe")
    bots = {
        "greedy": GreedyBot(bot_id="greedy"),
        "random": RandomBot(bot_id="random"),
    }
    summary = run_round_robin(game, bots, rounds=10)
    print(summary)


if __name__ == "__main__":
    main()
