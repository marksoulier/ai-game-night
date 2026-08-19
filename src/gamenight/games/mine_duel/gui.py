from __future__ import annotations

import tkinter as tk

from gamenight.games.mine_duel.game import COLS, ROWS

CELL_SIZE = 42

BG_COLOR = "#0a1f2b"
HIDDEN_COLOR = "#1c4a63"
HIDDEN_OUTLINE = "#2f6a8a"
REVEALED_COLOR = "#d7dde3"
NEUTRAL_BORDER = "#8a97a1"
MINE_COLOR = "#c0392b"

PLAYER_COLORS = {"player_ember": "#ff9f45", "player_frost": "#5aa7ff"}
# Classic Minesweeper's number-color convention, kept legible on the light revealed-cell fill.
NUMBER_COLORS = {
    1: "#1a56db",
    2: "#1f9254",
    3: "#d92d20",
    4: "#5925dc",
    5: "#b54708",
    6: "#0e7490",
    7: "#101828",
    8: "#475467",
}


class MineDuelViewer:
    """A single shared board -- unlike Battleship's two-fleet layout, both players
    see (and act on) the exact same grid, so there's only one board to draw. Each
    revealed cell is tinted by whichever player revealed it (`owner_grid`), so a
    spectator can see at a glance who's been finding safe cells versus who's been
    finding mines, even though the bots themselves only ever see the shared board."""

    def __init__(self, matchup_label: str | None = None) -> None:
        self.closed = False
        self.root = tk.Tk()
        self.root.title("AI Game Night - Mine Duel")
        self.root.configure(bg=BG_COLOR)
        width = COLS * CELL_SIZE + 40
        height = ROWS * CELL_SIZE + 200
        self.root.geometry(f"{width}x{height}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if matchup_label:
            tk.Label(
                self.root, text=matchup_label, font=("Helvetica", 12), fg="#9fb6c9", bg=BG_COLOR
            ).pack(pady=(12, 0))

        self.status_var = tk.StringVar(value="Starting game...")
        tk.Label(
            self.root, textvariable=self.status_var, font=("Helvetica", 14, "bold"), fg="#eef4f8", bg=BG_COLOR
        ).pack(pady=10)

        scores_frame = tk.Frame(self.root, bg=BG_COLOR)
        scores_frame.pack()
        self.name_vars: dict[str, tk.StringVar] = {}
        self.score_vars: dict[str, tk.StringVar] = {}
        self.record_vars: dict[str, tk.StringVar] = {}
        for column, player_id in enumerate(("player_ember", "player_frost")):
            side = tk.Frame(scores_frame, bg=BG_COLOR)
            side.grid(row=0, column=column, padx=24)
            name_var = tk.StringVar(value=player_id)
            tk.Label(
                side, textvariable=name_var, font=("Helvetica", 12, "bold"),
                fg=PLAYER_COLORS[player_id], bg=BG_COLOR,
            ).pack()
            score_var = tk.StringVar(value="Score: 0")
            tk.Label(side, textvariable=score_var, font=("Helvetica", 11), fg="#9fb6c9", bg=BG_COLOR).pack()
            record_var = tk.StringVar(value="Wins: 0   Losses: 0")
            tk.Label(side, textvariable=record_var, font=("Helvetica", 10), fg="#7a8a94", bg=BG_COLOR).pack()
            self.name_vars[player_id] = name_var
            self.score_vars[player_id] = score_var
            self.record_vars[player_id] = record_var

        self.canvas = tk.Canvas(
            self.root, width=COLS * CELL_SIZE, height=ROWS * CELL_SIZE, bg=HIDDEN_COLOR, highlightthickness=0
        )
        self.canvas.pack(pady=12)

        legend = (
            "Both players see the same board -- no hidden fleets here. "
            "Orange/blue tint = who revealed that cell. Gray = the neutral opening (nobody's point). "
            "Red = a revealed mine."
        )
        tk.Label(
            self.root, text=legend, font=("Helvetica", 10), fg="#9fb6c9", bg=BG_COLOR, wraplength=width - 40
        ).pack(pady=(4, 12))

        self._draw_empty_grid()

    def _draw_empty_grid(self) -> None:
        for row in range(ROWS):
            for col in range(COLS):
                x0, y0 = col * CELL_SIZE, row * CELL_SIZE
                x1, y1 = x0 + CELL_SIZE, y0 + CELL_SIZE
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=HIDDEN_COLOR, outline=HIDDEN_OUTLINE)

    def set_names(self, names: dict[str, str]) -> None:
        for player_id, name in names.items():
            if player_id in self.name_vars:
                self.name_vars[player_id].set(name)
        self.root.update_idletasks()

    def set_records(self, records: dict[str, tuple[int, int]]) -> None:
        for player_id, (wins, losses) in records.items():
            if player_id in self.record_vars:
                self.record_vars[player_id].set(f"Wins: {wins}   Losses: {losses}")

    def update_state(
        self,
        state,
        turn: int | None = None,
        acting_player: str | None = None,
        action: dict | None = None,
    ) -> None:
        if self.closed:
            return

        cells = state["cells"]
        scores = state["scores"]
        for player_id, score in scores.items():
            if player_id in self.score_vars:
                self.score_vars[player_id].set(f"Score: {score}")

        self.canvas.delete("all")
        for row in range(ROWS):
            for col in range(COLS):
                self._draw_cell(row, col, cells[row][col])

        if state.get("done"):
            winner = state.get("winner")
            self.status_var.set(f"Game over -- winner: {winner}" if winner else "Game over -- draw")
        elif acting_player:
            self.status_var.set(f"Turn {turn}: {acting_player} revealed a cell")
        else:
            self.status_var.set("Starting game...")

        self.root.update_idletasks()
        self.root.update()

    def _draw_cell(self, row: int, col: int, cell: dict) -> None:
        x0, y0 = col * CELL_SIZE, row * CELL_SIZE
        x1, y1 = x0 + CELL_SIZE, y0 + CELL_SIZE

        if not cell["revealed"]:
            self.canvas.create_rectangle(x0, y0, x1, y1, fill=HIDDEN_COLOR, outline=HIDDEN_OUTLINE)
            return

        # Revealed cells keep the classic light Minesweeper look (numbers stay
        # legible); who revealed it shows as a colored border instead of a fill, so
        # it reads at a glance without fighting the number's own color.
        fill = MINE_COLOR if cell["mine"] else REVEALED_COLOR
        border = PLAYER_COLORS.get(cell["revealed_by"], NEUTRAL_BORDER)
        self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=border, width=3)

        if cell["mine"]:
            self.canvas.create_text(
                (x0 + x1) / 2, (y0 + y1) / 2, text="*", fill="#ffffff", font=("Helvetica", 16, "bold")
            )
        elif cell["adjacent"] > 0:
            self.canvas.create_text(
                (x0 + x1) / 2,
                (y0 + y1) / 2,
                text=str(cell["adjacent"]),
                fill=NUMBER_COLORS.get(cell["adjacent"], "#101828"),
                font=("Helvetica", 14, "bold"),
            )

    def wait_until_closed(self) -> None:
        while not self.closed:
            try:
                self.root.update_idletasks()
                self.root.update()
            except tk.TclError:
                break

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            try:
                self.root.destroy()
            except tk.TclError:
                pass

    def _on_close(self) -> None:
        self.closed = True
