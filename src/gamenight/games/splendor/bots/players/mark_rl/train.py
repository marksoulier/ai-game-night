"""Self-play REINFORCE training for `mark_rl`'s Splendor bot.

Plays this bot's tiny MLP scorer (`bot.py`'s `encode` + `forward`, see that file's
module docstring for why the architecture lives there and not here) against
`player:clayton` (or any other bot in the repo -- see `--opponent`) over and over,
nudging the weights after every batch of games toward whatever this bot actually
did on the way to winning, away from what it did on the way to losing. Standard
policy-gradient RL, no engine access needed beyond what `game.py` already exposes:
`create_initial_state` / `current_player` / `legal_actions` / `observe` / `step`,
the exact same calls `core/match.py`'s `run_match` makes.

Algorithm, concretely (vanilla REINFORCE with a softmax policy over a shared
per-action scorer -- the same "score every legal action, softmax over the scores"
shape as a bandit/contextual-bandit policy, just plugged into a multi-turn game by
applying one episode-level return to every decision in the episode):

    pi(a | s) = softmax(score(s, a) / temperature)   over legal_actions(s)
    R(episode) = clip(margin, -1, 1) + outcome_bonus     (see `episode_reward`)
    advantage  = R - running_baseline(EMA of past R)
    loss       = -advantage * log pi(a_taken | s)   summed over every RL-bot
                 decision in the episode (all phases: action/discard/noble_choice
                 alike, since `encode_action` covers all of them)

`R` is point-margin-shaped, not bare +1/-1/-0.2 win/loss/draw -- deliberately.
Against an opponent as strong as `clayton`, an untrained policy loses essentially
every training episode for a long stretch (confirmed by an earlier version of this
script: 20,000 straight losses, 0% win rate, dead flat). Bare win/loss reward makes
that fatal, not just slow: once the EMA baseline settles near -1 (the same as every
episode's reward, because every episode IS a loss), `advantage` collapses to ~0 for
*every* episode alike, and REINFORCE's gradient is `E[(pi - onehot(a_sampled))] *
advantage`, which is exactly 0 in expectation when advantage doesn't vary between
episodes -- there is no such thing as "the losing games that went better" for the
gradient to push toward, only "loss" vs "loss". Point-margin shaping fixes this by
making R vary continuously with how close the game was even when the outcome
doesn't change, so "lost 8-15" keeps getting pulled toward "lost 11-15" long before
the policy is anywhere near good enough to flip a game outright.

`temperature` decays linearly from `--temperature-start` to `--temperature-end`
over training: it starts high (near-uniform sampling => exploration) and ends low
(near-argmax => exploitation), same idea as epsilon-decay.

Gradients are accumulated over `--batch-size` episodes then applied as one Adam
step -- batching a few episodes per update smooths out the high variance a single
episode's +1/-1 return otherwise has on the gradient.

`forward_np` below is a batched-numpy re-implementation of `bot.py`'s `forward`
(same tanh-MLP math, scored for every legal action at once instead of one at a
time) -- kept in a separate function, rather than imported, because training needs
the intermediate hidden activations for backprop that the inference-only pure-python
`forward` doesn't compute. The two are exercised against each other in `_selftest`
(run automatically once at startup): forward_np's score for a random state must
match bot.forward's, or training would be tuning a different function than the one
that actually plays. Everything else -- `encode`, `FEATURE_DIM`, `HIDDEN_SIZE`,
`load_weights`/`save_weights` -- is imported straight from `bot.py`, so there is
exactly one copy of "what the network looks like" and "what the features are";
train.py only adds the numpy math and the game-playing loop around it.

Usage (run from anywhere -- `uv run` finds this project's pyproject.toml by
searching upward from cwd, and merges this folder's requirements.txt with it into
one ephemeral env, so both `numpy` and the editable `gamenight` package resolve):

    uv run --with-requirements requirements.txt python train.py --episodes 4000

    # keep training on top of an existing weights.json instead of from scratch:
    uv run --with-requirements requirements.txt python train.py --episodes 2000 --resume

    # just measure the current weights.json's win rate, no training:
    uv run --with-requirements requirements.txt python train.py --eval-only --eval-games 200

Progress (episode count, decaying temperature, rolling win rate, periodic true
eval win rate) prints to stdout every `--eval-every` episodes. `weights.json` is
only ever overwritten when that eval batch's win rate (+ point-margin tiebreak)
beats every earlier checkpoint this run -- policy-gradient training is not
monotonic, a batch of updates can make the policy worse, and this is what keeps a
late-run regression from silently becoming what gets shipped (see the "best
checkpoint" comment in `train()` for a real example this guards against). A killed
run still leaves the best checkpoint seen so far behind, not just the latest one.
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

import numpy as np

# When stdout is redirected to a file (e.g. `train.py > train.log 2>&1 &`, the
# usual way to background a long run) Python switches from line- to block-
# buffering, so progress prints sit in memory and don't reach the log until the
# buffer fills or the process exits -- a tail -f on the log looks stalled even
# though training is running fine. Force line buffering so every eval checkpoint
# shows up immediately regardless of how this script is invoked.
sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling import below works
import bot as rl_bot  # local module: shares encode()/FEATURE_DIM/HIDDEN_SIZE with bot.py

from gamenight.core.bots import build_bot
from gamenight.core.types import MatchContext
from gamenight.games import build_registry
from gamenight.games.splendor.game import WIN_THRESHOLD

RL_PLAYER = "player_1"
OPPONENT_PLAYER = "player_2"


# -- numpy mirror of bot.py's forward pass, plus the hidden activations backprop needs --


def forward_np(weights: dict, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Batched version of `bot.forward`: X is (n_actions, FEATURE_DIM). Returns
    (scores, hidden) -- scores is (n_actions,), hidden is (n_actions, HIDDEN_SIZE)
    and is only needed by the backward pass below, not at inference time (which is
    why `bot.py`'s pure-python `forward` doesn't bother returning it)."""
    w1, b1, w2, b2 = weights["w1"], weights["b1"], weights["w2"], weights["b2"]
    hidden = np.tanh(X @ w1.T + b1)
    scores = hidden @ w2[0] + b2[0]
    return scores, hidden


def backward_np(X: np.ndarray, hidden: np.ndarray, w2: np.ndarray, d_scores: np.ndarray) -> dict:
    """Gradient of a scalar loss wrt every weight, given dLoss/dScore per action
    (`d_scores`, shape (n_actions,)) and the forward pass's saved intermediates.
    Standard 1-hidden-layer-tanh-MLP backprop, e.g. for a batch of n actions:

        dW2 = d_scores . hidden                       (H,)
        db2 = sum(d_scores)
        dHidden = outer(d_scores, W2)                  (n, H)
        dZ = dHidden * (1 - hidden**2)                 (n, H)   -- tanh'
        dW1 = dZ.T @ X                                 (H, D)
        db1 = sum(dZ, axis=0)                          (H,)
    """
    d_w2 = d_scores @ hidden
    d_b2 = d_scores.sum()
    d_hidden = np.outer(d_scores, w2[0])
    d_z = d_hidden * (1.0 - hidden**2)
    d_w1 = d_z.T @ X
    d_b1 = d_z.sum(axis=0)
    return {"w1": d_w1, "b1": d_b1, "w2": d_w2[None, :], "b2": np.array([d_b2])}


def _zero_grads(weights: dict) -> dict:
    return {key: np.zeros_like(value) for key, value in weights.items() if key in ("w1", "b1", "w2", "b2")}


def _add_grads(total: dict, delta: dict) -> None:
    for key in total:
        total[key] += delta[key]


def _selftest(weights: dict) -> None:
    """bot.forward (pure python, what actually plays) and forward_np (batched
    numpy, what actually trains) must score identically -- if they drift, training
    would be tuning a function the bot never runs at inference."""
    rng = np.random.default_rng(0)
    x = rng.normal(size=rl_bot.FEATURE_DIM)
    py_score = rl_bot.forward(_weights_to_lists(weights), list(x))
    np_score, _ = forward_np(weights, x[None, :])
    if abs(py_score - float(np_score[0])) > 1e-8:
        raise AssertionError(
            f"forward_np and bot.forward disagree ({np_score[0]!r} vs {py_score!r}) -- "
            "architecture drift between train.py and bot.py, fix before training."
        )


# -- weight (de)serialization: numpy <-> the plain-list json schema bot.py reads ----


def _weights_to_arrays(weights_json: dict) -> dict:
    return {
        "w1": np.array(weights_json["w1"], dtype=np.float64),
        "b1": np.array(weights_json["b1"], dtype=np.float64),
        "w2": np.array(weights_json["w2"], dtype=np.float64),
        "b2": np.array(weights_json["b2"], dtype=np.float64),
    }


def _weights_to_lists(weights: dict) -> dict:
    return {
        "feature_dim": rl_bot.FEATURE_DIM,
        "hidden_size": rl_bot.HIDDEN_SIZE,
        "w1": weights["w1"].tolist(),
        "b1": weights["b1"].tolist(),
        "w2": weights["w2"].tolist(),
        "b2": weights["b2"].tolist(),
    }


def init_weights_np(seed: int) -> dict:
    return _weights_to_arrays(rl_bot.init_weights(rl_bot.FEATURE_DIM, rl_bot.HIDDEN_SIZE, seed=seed))


# -- Adam optimizer, applied to the 4 weight arrays ----------------------------------


class Adam:
    def __init__(self, weights: dict, lr: float, beta1: float = 0.9, beta2: float = 0.999, eps: float = 1e-8):
        self.lr = lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self.t = 0
        self.m = {k: np.zeros_like(v) for k, v in weights.items()}
        self.v = {k: np.zeros_like(v) for k, v in weights.items()}

    def step(self, weights: dict, grads: dict) -> None:
        self.t += 1
        for key in weights:
            g = grads[key]
            self.m[key] = self.beta1 * self.m[key] + (1 - self.beta1) * g
            self.v[key] = self.beta2 * self.v[key] + (1 - self.beta2) * (g * g)
            m_hat = self.m[key] / (1 - self.beta1**self.t)
            v_hat = self.v[key] / (1 - self.beta2**self.t)
            weights[key] -= self.lr * m_hat / (np.sqrt(v_hat) + self.eps)


def softmax(scores: np.ndarray) -> np.ndarray:
    shifted = scores - scores.max()
    exps = np.exp(shifted)
    return exps / exps.sum()


# -- one episode: play it, and (if recording) collect what's needed for the gradient --


def play_episode(
    game,
    weights: dict,
    opponent_bot,
    rng: random.Random,
    temperature: float,
    max_turns: int,
    record: bool,
) -> tuple[list[dict], str, int, dict]:
    """Plays one game, `mark_rl`'s weights vs `opponent_bot`, alternating who's
    `player_1`/`player_2` every call (`rng` decides) so training doesn't quietly
    overfit to always moving first or second.

    Returns (steps, outcome, turns, final_points):
      - `steps`: one dict per RL-bot decision (empty if `record=False`), each with
        `X`/`hidden` (this turn's legal actions' features and hidden activations)
        and `idx` (which one got picked) -- exactly what `backward_np` needs once
        the episode's return is known.
      - `outcome`: "win" / "loss" / "draw" from the RL bot's side.
      - `final_points`: {"rl": int, "opponent": int} for logging.
    """
    rl_goes_first = rng.random() < 0.5
    rl_seat, opp_seat = (RL_PLAYER, OPPONENT_PLAYER) if rl_goes_first else (OPPONENT_PLAYER, RL_PLAYER)

    seed = rng.randrange(2**31)
    state = game.create_initial_state(seed=seed)
    context = MatchContext(game_id=game.game_id, seed=seed, player_ids=[RL_PLAYER, OPPONENT_PLAYER], max_turns=max_turns)
    opponent_bot.reset(context)

    steps: list[dict] = []
    turns = 0
    while turns < max_turns:
        turns += 1
        current = game.current_player(state)
        observation = game.observe(state, current)
        legal_actions = game.legal_actions(state, current)
        observation["legal_actions"] = legal_actions

        if current == rl_seat:
            if len(legal_actions) == 1:
                action = legal_actions[0]
            else:
                state_features = rl_bot.encode_state(observation)
                X = np.array(
                    [state_features + rl_bot.encode_action(observation, a) for a in legal_actions], dtype=np.float64
                )
                scores, hidden = forward_np(weights, X)
                if record:
                    probs = softmax(scores / temperature)
                    idx = int(rng.choices(range(len(legal_actions)), weights=probs.tolist(), k=1)[0])
                    steps.append({"X": X, "hidden": hidden, "idx": idx})
                else:
                    idx = int(np.argmax(scores))  # eval: play greedily, no exploration
                action = legal_actions[idx]
        else:
            try:
                action = opponent_bot.choose_action(observation, context)
            except Exception:  # noqa: BLE001 - a misbehaving opponent must not crash training
                action = legal_actions[0]
            if action not in legal_actions:
                action = legal_actions[0]

        step_result = game.step(state, action)
        state = step_result.next_state
        if step_result.done:
            break

    public = state["players"]  # engine state keeps "players" top-level (see game.py's create_initial_state)
    rl_points = public[rl_seat]["points"]
    opp_points = public[opp_seat]["points"]

    rewards = step_result.rewards
    winner = None
    if rewards:
        sorted_rewards = sorted(rewards.items(), key=lambda kv: kv[1], reverse=True)
        top_id, top_score = sorted_rewards[0]
        if len(sorted_rewards) == 1 or top_score != sorted_rewards[1][1]:
            winner = top_id

    if winner == rl_seat:
        outcome = "win"
    elif winner == opp_seat:
        outcome = "loss"
    else:
        outcome = "draw"

    return steps, outcome, turns, {"rl": rl_points, "opponent": opp_points}


def episode_reward(outcome: str, points: dict) -> float:
    """Point-margin-shaped return -- see the module docstring's "R is
    point-margin-shaped" section for why bare +1/-1/-0.2 win/loss/draw goes dead
    against a much-stronger opponent. `margin` alone would make winning-by-a-lot
    and losing-by-a-little hard to tell apart from actually winning/losing, so a
    flat bonus on top keeps the real outcome dominant once margins get close."""
    margin = (points["rl"] - points["opponent"]) / WIN_THRESHOLD
    bonus = {"win": 0.6, "loss": -0.6, "draw": 0.0}[outcome]
    return max(-1.5, min(1.5, margin + bonus))


# -- training loop --------------------------------------------------------------------


def make_opponent(game, game_id: str, name: str, bot_id: str):
    resolved = name if name in ("random", "greedy", "human") else f"player:{name}"
    return build_bot(game, resolved, bot_id, game_id)


def evaluate(game, weights: dict, opponent_name: str, games: int, rng: random.Random, max_turns: int) -> dict:
    wins = losses = draws = 0
    total_turns = 0
    total_margin = 0.0
    for _ in range(games):
        opponent_bot = make_opponent(game, game.game_id, opponent_name, "opponent")
        _steps, outcome, turns, points = play_episode(
            game, weights, opponent_bot, rng, temperature=1.0, max_turns=max_turns, record=False
        )
        total_turns += turns
        total_margin += points["rl"] - points["opponent"]
        if outcome == "win":
            wins += 1
        elif outcome == "loss":
            losses += 1
        else:
            draws += 1
    return {
        "games": games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": wins / games,
        "avg_turns": total_turns / games,
        "avg_point_margin": total_margin / games,  # negative = losing on points on average, trending toward 0 is progress even pre-win-rate
    }


def train(args: argparse.Namespace) -> None:
    registry = build_registry()
    game = registry.get("splendor", num_players=2)

    weights = (
        _weights_to_arrays(rl_bot.load_weights(Path(args.out)))
        if args.resume and Path(args.out).exists()
        else init_weights_np(args.seed)
    )
    _selftest(weights)

    optimizer = Adam(weights, lr=args.lr)
    rng = random.Random(args.seed)
    baseline = 0.0
    rolling_outcomes: list[str] = []

    # Policy-gradient training is not monotonic -- late-training collapse (a batch
    # of updates that overshoots into a worse, sometimes more exploitable, policy)
    # is a normal failure mode, not a bug: an early version of this script always
    # exported whatever the *latest* checkpoint was and, on one real run, that
    # meant shipping a checkpoint that measured 40% vs clayton over 300 games when
    # an earlier checkpoint from the same run measured ~80%+ across several
    # eval_every windows in a row. `weights.json` (`--out`) is only ever
    # overwritten with the best-scoring checkpoint seen so far -- `weights`
    # (the live, still-training arrays) keeps moving even when a batch regresses,
    # but what gets exported never regresses.
    best_weights: dict | None = None
    best_score = float("-inf")

    start = time.time()
    episode = 0
    while episode < args.episodes:
        batch_grads = _zero_grads(weights)
        batch_timesteps = 0

        for _ in range(min(args.batch_size, args.episodes - episode)):
            episode += 1
            progress = episode / args.episodes
            temperature = args.temperature_start + (args.temperature_end - args.temperature_start) * progress

            opponent_bot = make_opponent(game, game.game_id, args.opponent, "opponent")
            steps, outcome, turns, points = play_episode(
                game, weights, opponent_bot, rng, temperature, args.max_turns, record=True
            )

            reward = episode_reward(outcome, points)
            advantage = reward - baseline
            baseline = 0.95 * baseline + 0.05 * reward
            rolling_outcomes.append(outcome)
            if len(rolling_outcomes) > 200:
                rolling_outcomes.pop(0)

            # Recompute each step's action probabilities from its saved hidden
            # activations (weights don't change mid-episode, so this is exactly
            # what was sampled from -- just not worth storing twice).
            for step in steps:
                scores = step["hidden"] @ weights["w2"][0] + weights["b2"][0]
                probs = softmax(scores / temperature)
                d_scores = advantage * (probs.copy())
                d_scores[step["idx"]] -= advantage
                d_scores /= temperature
                grads = backward_np(step["X"], step["hidden"], weights["w2"], d_scores)
                _add_grads(batch_grads, grads)
                batch_timesteps += 1

        if batch_timesteps > 0:
            for key in batch_grads:
                batch_grads[key] /= batch_timesteps
            optimizer.step(weights, batch_grads)

        if episode % args.eval_every < args.batch_size:
            recent_win_rate = rolling_outcomes.count("win") / len(rolling_outcomes) if rolling_outcomes else 0.0
            elapsed = time.time() - start
            eval_result = evaluate(game, weights, args.opponent, args.eval_games, rng, args.max_turns)
            # win rate dominates; avg_point_margin only breaks near-ties between
            # two checkpoints with a similar (noisy, --eval-games-sized) win rate.
            score = eval_result["win_rate"] + 0.01 * eval_result["avg_point_margin"]

            is_best = score > best_score
            if is_best:
                best_score = score
                best_weights = {key: value.copy() for key, value in weights.items()}
                rl_bot.save_weights(_weights_to_lists(best_weights), Path(args.out))

            print(
                f"[{episode:>6}/{args.episodes}] t={elapsed:6.0f}s  temp={temperature:.2f}  "
                f"rolling_train_win_rate={recent_win_rate:.2%}  "
                f"eval_vs_{args.opponent}: {eval_result['wins']}W/{eval_result['losses']}L/{eval_result['draws']}D "
                f"({eval_result['win_rate']:.2%}, avg point margin {eval_result['avg_point_margin']:+.1f}, "
                f"avg {eval_result['avg_turns']:.0f} turns)"
                + ("  <- new best, saved" if is_best else f"  (best so far: {best_score:.2%})")
            )

    if best_weights is not None:
        rl_bot.save_weights(_weights_to_lists(best_weights), Path(args.out))
        print(f"done. best checkpoint (score={best_score:.3f}) written to {args.out}")
    else:
        print("done. no eval checkpoint was ever reached (episodes < eval_every) -- nothing written.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--episodes", type=int, default=4000, help="Total self-play games to train on.")
    parser.add_argument("--batch-size", type=int, default=8, help="Episodes per gradient update.")
    parser.add_argument(
        "--opponent",
        default="clayton",
        help="Who to train (and evaluate) against: 'random', 'greedy', 'human', or a bots/players/<name> "
        "folder name (looked up as player:<name>, e.g. the default 'clayton').",
    )
    parser.add_argument("--lr", type=float, default=0.01, help="Adam learning rate.")
    parser.add_argument("--temperature-start", type=float, default=1.4, help="Softmax temperature at episode 0.")
    parser.add_argument("--temperature-end", type=float, default=0.35, help="Softmax temperature at the last episode.")
    parser.add_argument("--seed", type=int, default=0, help="RNG seed for game seeds, opponent choice, and init.")
    parser.add_argument("--max-turns", type=int, default=200, help="Per-game turn cap, same default as run_match.")
    parser.add_argument("--eval-every", type=int, default=200, help="Checkpoint + run an eval batch every N episodes.")
    parser.add_argument("--eval-games", type=int, default=40, help="Greedy (temperature->argmax) games per eval.")
    parser.add_argument("--out", default=str(rl_bot.WEIGHTS_PATH), help="Where to write weights.json.")
    parser.add_argument("--resume", action="store_true", help="Continue training from --out instead of from scratch.")
    parser.add_argument("--eval-only", action="store_true", help="Skip training; just evaluate --out's current weights.")
    args = parser.parse_args()

    if args.eval_only:
        registry = build_registry()
        game = registry.get("splendor", num_players=2)
        weights = _weights_to_arrays(rl_bot.load_weights(Path(args.out)))
        _selftest(weights)
        rng = random.Random(args.seed)
        result = evaluate(game, weights, args.opponent, args.eval_games, rng, args.max_turns)
        print(
            f"eval vs {args.opponent}: {result['wins']}W/{result['losses']}L/{result['draws']}D "
            f"over {result['games']} games -> win rate {result['win_rate']:.2%} (avg {result['avg_turns']:.0f} turns)"
        )
        return

    train(args)


if __name__ == "__main__":
    main()
