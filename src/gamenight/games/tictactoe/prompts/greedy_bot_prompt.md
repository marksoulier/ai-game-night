# Prompt: Generate Tic-Tac-Toe Greedy Bot

You are writing a Python class for this repository.

Task:

- Create class `PlayerBot` in `bot.py`.
- The class must expose:
  - `__init__(self, bot_id: str)`
  - `reset(self, context)`
  - `choose_action(self, observation, context)`

Rules:

1. Read only from the provided `observation` and `context`.
2. Never use hidden information.
3. Return one action from `observation["legal_actions"]`.
4. If your preferred action is not legal, fall back to a legal action.

Greedy strategy requirements:

1. If a move wins this turn, play it.
2. Else if opponent can win next turn, block it.
3. Else prefer center, then corners, then edges.

Observation schema summary:

- `observation["public_state"]["board"]`: list of 9 board cells
- `observation["private_state"]["marker"]`: current marker (`X` or `O`)
- `observation["legal_actions"]`: list of actions shaped like `{"type":"place","index":i}`

Output:

- Return valid Python code only.
