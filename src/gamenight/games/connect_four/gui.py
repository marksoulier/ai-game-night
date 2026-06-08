from __future__ import annotations

import tkinter as tk

from gamenight.games.connect_four.game import COLUMNS, ROWS


EMPTY_COLOR = "#e7edf6"
RED_COLOR = "#d6483f"
YELLOW_COLOR = "#e8c33b"
DISC_COLORS = {" ": EMPTY_COLOR, "R": RED_COLOR, "Y": YELLOW_COLOR}
CELL_SIZE = 56
DISC_PADDING = 6


class ConnectFourViewer:
    def __init__(self, matchup_label: str | None = None) -> None:
        self.closed = False
        self.root = tk.Tk()
        self.root.title("AI Game Night - Connect Four")
        self.root.geometry(f"{COLUMNS * CELL_SIZE + 80}x{ROWS * CELL_SIZE + 170}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if matchup_label:
            matchup = tk.Label(self.root, text=matchup_label, font=("Helvetica", 12), fg="#4a5670")
            matchup.pack(pady=(12, 0))

        self.status_var = tk.StringVar(value="Starting game...")
        status_label = tk.Label(self.root, textvariable=self.status_var, font=("Helvetica", 14, "bold"))
        status_label.pack(pady=12)

        board_width = COLUMNS * CELL_SIZE
        board_height = ROWS * CELL_SIZE
        self.canvas = tk.Canvas(self.root, width=board_width, height=board_height, bg="#3a6ea5", highlightthickness=0)
        self.canvas.pack(pady=8)

        self.discs: list[list[int]] = []
        for row in range(ROWS):
            disc_row: list[int] = []
            for col in range(COLUMNS):
                x0 = col * CELL_SIZE + DISC_PADDING
                y0 = row * CELL_SIZE + DISC_PADDING
                x1 = (col + 1) * CELL_SIZE - DISC_PADDING
                y1 = (row + 1) * CELL_SIZE - DISC_PADDING
                disc_id = self.canvas.create_oval(x0, y0, x1, y1, fill=EMPTY_COLOR, outline="#2a4f74", width=2)
                disc_row.append(disc_id)
            self.discs.append(disc_row)

        legend = tk.Label(
            self.root,
            text="You play in terminal input when using a human bot.",
            font=("Helvetica", 11),
        )
        legend.pack(pady=8)

    def update_state(
        self,
        state: dict,
        turn: int | None = None,
        acting_player: str | None = None,
        action: dict | None = None,
    ) -> None:
        if self.closed:
            return

        board = state["board"]
        for row in range(ROWS):
            for col in range(COLUMNS):
                marker = board[row * COLUMNS + col]
                self.canvas.itemconfigure(self.discs[row][col], fill=DISC_COLORS[marker])

        if state["done"]:
            if state["winner"] is None:
                self.status_var.set("Game over: draw")
            else:
                self.status_var.set(f"Game over: winner is {state['winner']}")
        else:
            message = f"Turn {state['turn_index'] + 1}: {state['current_player']} to move"
            if turn is not None and acting_player is not None and action is not None:
                message = f"Turn {turn}: {acting_player} played {action}"
            self.status_var.set(message)

        self.root.update_idletasks()
        self.root.update()

    def wait_until_closed(self) -> None:
        if not self.closed:
            self.root.mainloop()

    def close(self) -> None:
        if not self.closed and self.root.winfo_exists():
            self.closed = True
            self.root.destroy()

    def _on_close(self) -> None:
        self.close()
