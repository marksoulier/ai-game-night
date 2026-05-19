from __future__ import annotations

import tkinter as tk


class TicTacToeViewer:
    def __init__(self) -> None:
        self.closed = False
        self.root = tk.Tk()
        self.root.title("AI Game Night - Tic-Tac-Toe")
        self.root.geometry("360x440")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.status_var = tk.StringVar(value="Starting game...")
        status_label = tk.Label(self.root, textvariable=self.status_var, font=("Helvetica", 14, "bold"))
        status_label.pack(pady=12)

        board_frame = tk.Frame(self.root)
        board_frame.pack(pady=8)

        self.cells: list[tk.StringVar] = []
        self.index_labels: list[tk.Label] = []
        for index in range(9):
            cell_var = tk.StringVar(value=" ")
            self.cells.append(cell_var)
            frame = tk.Frame(board_frame)
            marker_label = tk.Label(
                frame,
                textvariable=cell_var,
                width=4,
                height=1,
                font=("Helvetica", 30, "bold"),
                relief="ridge",
                borderwidth=2,
            )
            marker_label.pack()
            idx_label = tk.Label(
                frame,
                text=f"{index}",
                font=("Helvetica", 10),
                fg="#888888"
            )
            idx_label.pack()
            self.index_labels.append(idx_label)
            row = index // 3
            col = index % 3
            frame.grid(row=row, column=col, padx=2, pady=2)

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
        for idx, marker in enumerate(board):
            self.cells[idx].set(marker if marker != " " else " ")

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
