from __future__ import annotations

import time
import tkinter as tk
from pathlib import Path
from typing import Any

from gamenight.core.match import load_replay_file
from gamenight.games.battleship.gui import BOARD_SIZE, CELL_SIZE, PLAYER_COLORS, WATER_COLOR, draw_board, status_text

BG = "#0a2538"
CARD_BG = "#123349"
CARD_BORDER = "#1c5475"
TEXT_COLOR = "#eef4f8"
DIM_TEXT_COLOR = "#6f8aa0"
WINNER_COLOR = "#7CFFB2"


class BracketRevealViewer:
    """Single-window bracket "reveal": shows the full bracket tree with round-1
    entrants visible and every later slot blank ("???"), plus a "Play Next Match"
    button that replays that match's saved games (first game slow, the rest fast)
    on an embedded board, then fills in the winner -- propagating it into the next
    round's slot (or the champion banner for the final).

    If `summary` is a tournament summary (from `run-tournament`, with "round_robin"
    and "bracket" sections), a round-robin standings table is shown immediately and
    an "Overall Standings" table updates live as each bracket match is revealed.

    Built entirely from a saved summary JSON (see `core/bracket.py`) plus the
    per-game replay files it references -- no bots run, this only re-renders saved
    state snapshots.
    """

    def __init__(
        self,
        summary: dict[str, Any],
        bracket_dir: Path,
        first_game_delay: float = 0.5,
        rest_delay: float = 0.05,
        show_final: bool = False,
    ) -> None:
        self.summary = summary
        self.bracket_dir = bracket_dir
        self.first_game_delay = first_game_delay
        self.rest_delay = rest_delay
        self.show_final = show_final
        self.closed = False

        if "bracket" in summary and "round_robin" in summary:
            self.bracket_summary = summary["bracket"]
            self.round_robin: dict[str, Any] | None = summary["round_robin"]
        else:
            self.bracket_summary = summary
            self.round_robin = None

        self.rounds: list[list[dict[str, Any]]] = self.bracket_summary["rounds"]
        self._flat_matches = [
            (round_idx, match_idx)
            for round_idx, round_results in enumerate(self.rounds)
            for match_idx in range(len(round_results))
        ]
        self._queue_pos = 0

        self.standings: dict[str, dict[str, int]] = {}
        if self.round_robin is not None:
            for name, record in self.round_robin["standings"].items():
                self.standings[name] = dict(record)
        for name in self.bracket_summary["entrants"]:
            self.standings.setdefault(name, {"wins": 0, "losses": 0})

        self.root = tk.Tk()
        self.root.title(f"AI Game Night - {summary['game_id']} Bracket Reveal")
        self.root.configure(bg=BG)
        standings_width = 200 if self.round_robin is not None else 0
        board_width = BOARD_SIZE * CELL_SIZE * 2 + 140 + standings_width
        self.root.geometry(f"{max(board_width, 900)}x1080")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.match_vars: list[list[dict[str, tk.StringVar]]] = []
        self.champion_var = tk.StringVar(value="Champion: ???")

        # Wrap everything in a vertically-scrollable canvas so the page can grow
        # taller than the window (e.g. many bracket rounds or status text) without
        # cutting off the controls at the bottom.
        outer_canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        vbar = tk.Scrollbar(self.root, orient="vertical", command=outer_canvas.yview)
        outer_canvas.configure(yscrollcommand=vbar.set)
        outer_canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        content = tk.Frame(outer_canvas, bg=BG)
        content_window = outer_canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda _e: outer_canvas.configure(scrollregion=outer_canvas.bbox("all")))
        outer_canvas.bind("<Configure>", lambda e: outer_canvas.itemconfigure(content_window, width=e.width))

        def _on_mousewheel(event: tk.Event) -> None:
            if event.num == 4:
                outer_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                outer_canvas.yview_scroll(1, "units")
            else:
                outer_canvas.yview_scroll(int(-event.delta / 120), "units")

        outer_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        outer_canvas.bind_all("<Button-4>", _on_mousewheel)
        outer_canvas.bind_all("<Button-5>", _on_mousewheel)

        self._build_standings(content)

        main = tk.Frame(content, bg=BG)
        main.pack(side="left", fill="both", expand=True)

        self._build_tree(main)
        self._build_board(main)
        self._build_controls(main)

        self._init_round_zero_labels()

        if self.show_final:
            self._reveal_all()

    # -- layout ------------------------------------------------------------------

    def _build_standings(self, parent: tk.Frame) -> None:
        self.standings_vars: dict[str, tk.StringVar] = {}
        if self.round_robin is None:
            return

        outer = tk.Frame(parent, bg=BG)
        outer.pack(side="left", fill="y", padx=(10, 4), pady=10, anchor="n")

        rr_frame = tk.Frame(outer, bg=BG)
        rr_frame.pack(anchor="w", pady=(0, 16))
        tk.Label(
            rr_frame, text="Round Robin Standings", font=("Helvetica", 11, "bold"), fg=TEXT_COLOR, bg=BG
        ).pack(anchor="w")
        rr_standings = self.round_robin["standings"]
        ranked = sorted(
            self.round_robin["entrants"],
            key=lambda name: (-rr_standings[name]["wins"], rr_standings[name]["losses"]),
        )
        for name in ranked:
            record = rr_standings[name]
            tk.Label(
                rr_frame,
                text=f"{name}: {record['wins']}-{record['losses']}",
                font=("Helvetica", 10),
                fg=TEXT_COLOR,
                bg=BG,
                anchor="w",
            ).pack(anchor="w")

        overall_frame = tk.Frame(outer, bg=BG)
        overall_frame.pack(anchor="w")
        tk.Label(
            overall_frame, text="Overall Standings", font=("Helvetica", 11, "bold"), fg=TEXT_COLOR, bg=BG
        ).pack(anchor="w")
        ranked_overall = sorted(
            self.bracket_summary["entrants"],
            key=lambda name: (-self.standings[name]["wins"], self.standings[name]["losses"]),
        )
        for name in ranked_overall:
            record = self.standings[name]
            var = tk.StringVar(value=f"{name}: {record['wins']}-{record['losses']}")
            tk.Label(overall_frame, textvariable=var, font=("Helvetica", 10), fg=TEXT_COLOR, bg=BG, anchor="w").pack(
                anchor="w"
            )
            self.standings_vars[name] = var

        results_frame = tk.Frame(outer, bg=BG)
        results_frame.pack(anchor="w", pady=(16, 0))
        tk.Label(
            results_frame, text="Round Robin Results", font=("Helvetica", 11, "bold"), fg=TEXT_COLOR, bg=BG
        ).pack(anchor="w")
        for series in self.round_robin["matches"]:
            score = f"{series['wins'][series['bot_a']]}-{series['wins'][series['bot_b']]}"
            text = f"{series['bot_a']} vs {series['bot_b']}: {score} -> {series['winner']}"
            tk.Label(
                results_frame,
                text=text,
                font=("Helvetica", 9),
                fg=TEXT_COLOR,
                bg=BG,
                anchor="w",
                justify="left",
                wraplength=190,
            ).pack(anchor="w")

    def _build_tree(self, parent: tk.Frame) -> None:
        outer = tk.Frame(parent, bg=BG)
        outer.pack(fill="x", padx=10, pady=(10, 4))

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0, height=400)
        hbar = tk.Scrollbar(outer, orient="horizontal", command=canvas.xview)
        canvas.configure(xscrollcommand=hbar.set)
        canvas.pack(side="top", fill="x")
        hbar.pack(side="bottom", fill="x")

        tree = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=tree, anchor="nw")
        tree.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))

        for round_idx, round_results in enumerate(self.rounds):
            column = tk.Frame(tree, bg=BG)
            column.grid(row=0, column=round_idx, padx=10, sticky="n")
            tk.Label(
                column, text=f"Round {round_idx + 1}", font=("Helvetica", 11, "bold"), fg=TEXT_COLOR, bg=BG
            ).pack(pady=(0, 6))

            round_vars: list[dict[str, tk.StringVar]] = []
            for match_idx in range(len(round_results)):
                round_vars.append(self._build_match_card(column))
            self.match_vars.append(round_vars)

        champion_column = tk.Frame(tree, bg=BG)
        champion_column.grid(row=0, column=len(self.rounds), padx=10, sticky="n")
        tk.Label(
            champion_column, text="Champion", font=("Helvetica", 11, "bold"), fg=TEXT_COLOR, bg=BG
        ).pack(pady=(0, 6))
        tk.Label(
            champion_column,
            textvariable=self.champion_var,
            font=("Helvetica", 12, "bold"),
            fg=WINNER_COLOR,
            bg=CARD_BG,
            relief="solid",
            bd=1,
            padx=10,
            pady=18,
            wraplength=140,
        ).pack(pady=4)

    def _build_match_card(self, parent: tk.Frame) -> dict[str, tk.StringVar]:
        bot_a_var = tk.StringVar(value="???")
        bot_b_var = tk.StringVar(value="???")
        winner_var = tk.StringVar(value="Winner: ???")

        card = tk.Frame(parent, bg=CARD_BG, highlightbackground=CARD_BORDER, highlightthickness=1)
        card.pack(pady=4, ipadx=8, ipady=6)

        tk.Label(card, textvariable=bot_a_var, font=("Helvetica", 10), fg=TEXT_COLOR, bg=CARD_BG, width=18, anchor="w").pack()
        tk.Label(card, text="vs", font=("Helvetica", 8), fg=DIM_TEXT_COLOR, bg=CARD_BG).pack()
        tk.Label(card, textvariable=bot_b_var, font=("Helvetica", 10), fg=TEXT_COLOR, bg=CARD_BG, width=18, anchor="w").pack()
        tk.Label(card, textvariable=winner_var, font=("Helvetica", 10, "bold"), fg=WINNER_COLOR, bg=CARD_BG, width=18, anchor="w").pack(pady=(4, 0))

        return {"bot_a": bot_a_var, "bot_b": bot_b_var, "winner": winner_var}

    def _build_board(self, parent: tk.Frame) -> None:
        self.status_var = tk.StringVar(value="Click \"Play Next Match\" to begin.")
        tk.Label(
            parent, textvariable=self.status_var, font=("Helvetica", 13, "bold"), fg=TEXT_COLOR, bg=BG
        ).pack(pady=(6, 6))

        boards = tk.Frame(parent, bg=BG)
        boards.pack(padx=20)

        self.canvases: dict[str, tk.Canvas] = {}
        self.name_vars: dict[str, tk.StringVar] = {}
        for column, player_id in enumerate(("player_blue", "player_orange")):
            side = tk.Frame(boards, bg=BG)
            side.grid(row=0, column=column, padx=14)

            name_var = tk.StringVar(value="")
            tk.Label(
                side, textvariable=name_var, font=("Helvetica", 12, "bold"), fg=PLAYER_COLORS[player_id], bg=BG
            ).pack(pady=(0, 6))

            canvas = tk.Canvas(
                side,
                width=BOARD_SIZE * CELL_SIZE,
                height=BOARD_SIZE * CELL_SIZE,
                bg=WATER_COLOR,
                highlightthickness=0,
            )
            canvas.pack()

            self.canvases[player_id] = canvas
            self.name_vars[player_id] = name_var

    def _build_controls(self, parent: tk.Frame) -> None:
        controls = tk.Frame(parent, bg=BG)
        controls.pack(pady=(4, 12))
        self.play_button = tk.Button(controls, text="Play Next Match", command=self._play_next, font=("Helvetica", 11, "bold"))
        self.play_button.pack()

    # -- bracket state -------------------------------------------------------------

    def _init_round_zero_labels(self) -> None:
        for match_idx, series in enumerate(self.rounds[0]):
            vars_ = self.match_vars[0][match_idx]
            vars_["bot_a"].set(series["bot_a"])
            vars_["bot_b"].set("(bye)" if series["bye"] else series["bot_b"])
            if series["bye"]:
                vars_["winner"].set(f"Winner: {series['bot_a']}")

    def _reveal_winner(self, round_idx: int, match_idx: int) -> None:
        series = self.rounds[round_idx][match_idx]
        winner = series["winner"]

        if series["bye"]:
            self.match_vars[round_idx][match_idx]["winner"].set(f"Winner: {winner}")
        else:
            score = f"{series['wins'][series['bot_a']]}-{series['wins'][series['bot_b']]}"
            self.match_vars[round_idx][match_idx]["winner"].set(f"Winner: {winner} ({score})")

            loser = series["bot_b"] if winner == series["bot_a"] else series["bot_a"]
            self.standings[winner]["wins"] += 1
            self.standings[loser]["losses"] += 1
            for name in (winner, loser):
                if name in self.standings_vars:
                    record = self.standings[name]
                    self.standings_vars[name].set(f"{name}: {record['wins']}-{record['losses']}")

        if round_idx + 1 < len(self.rounds):
            next_match_idx = match_idx // 2
            slot = "bot_a" if match_idx % 2 == 0 else "bot_b"
            self.match_vars[round_idx + 1][next_match_idx][slot].set(winner)
        else:
            self.champion_var.set(f"Champion: {winner}")

    def _reveal_all(self) -> None:
        """Skip the reveal animation: fill in every match's winner/score, the
        live standings, and the champion banner immediately, then show the
        final game state of the championship match.
        """
        for round_idx, match_idx in self._flat_matches:
            self._reveal_winner(round_idx, match_idx)
        self._queue_pos = len(self._flat_matches)
        self.play_button.config(state="disabled")

        final_series: dict[str, Any] | None = None
        for round_results in reversed(self.rounds):
            for series in round_results:
                if not series["bye"]:
                    final_series = series
                    break
            if final_series is not None:
                break

        if final_series is not None and final_series["games"]:
            self.name_vars["player_blue"].set(final_series["bot_a"])
            self.name_vars["player_orange"].set(final_series["bot_b"])
            last_game = final_series["games"][-1]
            swap = last_game["first_bot"] != final_series["bot_a"]
            events = load_replay_file(Path(last_game["replay_file"]))
            if events:
                self._update_boards(events[-1]["state"], swap)
            label = f"Round {final_series['round_index']}: {final_series['bot_a']} vs {final_series['bot_b']}"
            self.status_var.set(f"{label} -> winner: {final_series['winner']} (final state)")
        else:
            self.status_var.set("Bracket complete!")

    # -- playback --------------------------------------------------------------------

    def _play_next(self) -> None:
        while self._queue_pos < len(self._flat_matches):
            round_idx, match_idx = self._flat_matches[self._queue_pos]
            series = self.rounds[round_idx][match_idx]

            if series["bye"]:
                self._reveal_winner(round_idx, match_idx)
                self._queue_pos += 1
                continue

            self._play_match(round_idx, match_idx, series)
            self._queue_pos += 1
            return

        self.status_var.set("Bracket complete!")
        self.play_button.config(state="disabled")

    def _play_match(self, round_idx: int, match_idx: int, series: dict[str, Any]) -> None:
        if not self._safe_call(lambda: self.play_button.config(state="disabled")):
            return
        label = f"Round {round_idx + 1}: {series['bot_a']} vs {series['bot_b']}"

        # Keep each bot on the same side (left = bot_a, right = bot_b) across every
        # game of this match, regardless of which player_id it was assigned in-game.
        self.name_vars["player_blue"].set(series["bot_a"])
        self.name_vars["player_orange"].set(series["bot_b"])

        for game_index, game in enumerate(series["games"]):
            if self.closed:
                return
            delay = self.first_game_delay if game_index == 0 else self.rest_delay
            swap = game["first_bot"] != series["bot_a"]

            replay_path = Path(game["replay_file"])
            events = load_replay_file(replay_path)
            for event in events:
                if self.closed:
                    return
                status = f"{label} -- game {game_index + 1}/{len(series['games'])}: " + status_text(
                    event["state"], event["turn"], event["player_id"], event["action"]
                )
                self.status_var.set(status)
                self._update_boards(event["state"], swap)
                if not self._safe_call(lambda: (self.root.update_idletasks(), self.root.update())):
                    return
                if delay > 0:
                    time.sleep(delay)

        self._reveal_winner(round_idx, match_idx)
        self.status_var.set(f"{label} -> winner: {series['winner']}")
        if not self.closed:
            self._safe_call(lambda: self.play_button.config(state="normal"))

    def _safe_call(self, fn) -> bool:
        """Run a Tk call, treating a destroyed window (TclError) as `closed`."""
        try:
            fn()
            return True
        except tk.TclError:
            self.closed = True
            return False

    def _update_boards(self, state: dict[str, Any], swap: bool) -> None:
        """Draw fleets/shots so `series["bot_a"]` always renders on the left
        canvas and `series["bot_b"]` on the right, regardless of which
        player_id (player_blue/player_orange) each bot was assigned this game.
        """
        left_id, right_id = ("player_orange", "player_blue") if swap else ("player_blue", "player_orange")
        draw_board(self.canvases["player_blue"], state["fleets"][left_id], state["shots"][right_id])
        draw_board(self.canvases["player_orange"], state["fleets"][right_id], state["shots"][left_id])

    # -- lifecycle ---------------------------------------------------------------------

    def run(self) -> None:
        if not self.closed:
            self.root.mainloop()

    def close(self) -> None:
        if not self.closed and self.root.winfo_exists():
            self.closed = True
            self.root.destroy()

    def _on_close(self) -> None:
        self.close()
