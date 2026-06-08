AI Game Night

Gather people together to play classic board, card or dice games. Snacks and drinks provided
Have a computer version of the game prepared.
Everyone reviews potentially plays the game, the rules and plays it together. After everyone is given 30min with the help of LLM to code up an AI that can play the game against other computers. 

To assist players a user bot is provided, “a bot that just asks in the terminal for the desired action so the human is the decision maker”. There will be a random bot, “given a set of actions it will choose a random action”. Then the user will be given a prepared prompt they can send to the AI to make a greedy bot.

A clear git flow will be explained that ensures no merge conflicts and all uses can combine their work easily for competing one against another. Easy documentation will be shown about how game bots can be easily swappable. Also infrastructure will be built to run large quantity of games keeping tracks of stats of the game. 

The game night is ended by playing an AI video that is created revealing then statistics are shown for the comparison between each of the AIs.

Infrastructure for the game night code base will be modular where bots will be designed for a specific game but the infrastructure between games will be similar. Documentation in the infrastructure will be detailed enough that a LLM could easily understand and write a corresponding bot. This will be sorted in a folder structure that makes sense. The structure will be designed so games are isolated from one another and bots are designed for a specific game not across games.

Instructions for AI to help with preparing the computer version of the game:

Discuss what is currently online in githubs for digital representation of the game, look at how good the visuals are and how well it would integrate into the game night framework. Propose either creating the game from scratch or utilizing another open source digital version of the game. Place the game modular in the game night framework so multiple games can be side by side. Utilize uv and python as the base systems for running the game. Python will be the base for running the infastructure. A single uv install will be used for the entire infrastructure. 

Also check whether the game is already "solved" in the game-theory sense (perfect play
fully computed — e.g. tic-tac-toe is a forced draw, Connect Four is a forced first-player
win) and report that up front before recommending it, including who proved it and when if
that's findable. This isn't a reason to rule a game out by itself — it's context the
person choosing should have going in: a solved game means a strong-enough bot can play
*perfectly* rather than just "well," and that perfect-vs-perfect outcomes are a known,
fixed result, which can flatten how surprising repeated top-bot-vs-top-bot matches feel
over time. Better to surface that as part of the recommendation than have it discovered
as a surprise after the infrastructure for the game is already built.
