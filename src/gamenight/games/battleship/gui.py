from __future__ import annotations

import tkinter as tk

from gamenight.games.battleship.game import BOARD_SIZE, SHIPS

CELL_SIZE = 34
SHIP_MARGIN = 4

WATER_COLOR = "#0e3a52"
GRID_LINE_COLOR = "#1c5475"
SHIP_COLOR = "#9aa7b3"
SHIP_OUTLINE = "#4a5560"
SHIP_HIGHLIGHT = "#c7d0d8"
SUNK_SHIP_COLOR = "#3a4048"
SUNK_MARK_COLOR = "#15181c"
HIT_COLOR = "#e63946"
HIT_OUTLINE = "#9d1f29"
MISS_COLOR = "#bfe9ec"
MISS_OUTLINE = "#6fa8ae"

PLAYER_COLORS = {"player_blue": "#5aa7ff", "player_orange": "#ff9f45"}


class BattleshipViewer:
    """A "TV broadcast" view: both fleets fully revealed, side by side.

    Neither bot ever sees the opponent's ships (see BOT_SPEC.md's redaction rules) --
    but a spectator watching the whole match benefits from seeing more than either
    contestant does, the same way a TV audience watches a poker hand from above. Each
    side's board shows that player's full fleet plus every shot the opponent has fired
    at it, so you can watch shots land near (and eventually on) hidden ships in real time.
    """

    def __init__(self, matchup_label: str | None = None) -> None:
        self.closed = False
        self.root = tk.Tk()
        self.root.title("AI Game Night - Battleship")
        self.root.configure(bg="#0a2538")
        width = BOARD_SIZE * CELL_SIZE * 2 + 140
        height = BOARD_SIZE * CELL_SIZE + 230
        self.root.geometry(f"{width}x{height}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if matchup_label:
            tk.Label(
                self.root, text=matchup_label, font=("Helvetica", 12), fg="#9fb6c9", bg="#0a2538"
            ).pack(pady=(12, 0))

        self.status_var = tk.StringVar(value="Starting game...")
        tk.Label(
            self.root,
            textvariable=self.status_var,
            font=("Helvetica", 14, "bold"),
            fg="#eef4f8",
            bg="#0a2538",
        ).pack(pady=10)

        boards = tk.Frame(self.root, bg="#0a2538")
        boards.pack(padx=20)

        self.canvases: dict[str, tk.Canvas] = {}
        first_id, second_id = "player_blue", "player_orange"
        for column, player_id in enumerate((first_id, second_id)):
            side = tk.Frame(boards, bg="#0a2538")
            side.grid(row=0, column=column, padx=14)
            tk.Label(
                side,
                text=player_id,
                font=("Helvetica", 13, "bold"),
                fg=PLAYER_COLORS[player_id],
                bg="#0a2538",
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

        legend = (
            "Ships are revealed for spectators only -- bots never see the opponent's fleet.   "
            "Steel = ship   Dark = sunk   Red ring = hit   Pale ring = miss"
        )
        tk.Label(self.root, text=legend, font=("Helvetica", 10), fg="#9fb6c9", bg="#0a2538", wraplength=width - 40).pack(
            pady=(10, 12)
        )

    def update_state(
        self,
        state: dict,
        turn: int | None = None,
        acting_player: str | None = None,
        action: dict | None = None,
    ) -> None:
        if self.closed:
            return

        for player_id, canvas in self.canvases.items():
            opponent_id = "player_orange" if player_id == "player_blue" else "player_blue"
            self._draw_board(canvas, state["fleets"][player_id], state["shots"][opponent_id])

        self.status_var.set(self._status_text(state, turn, acting_player, action))

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

    # -- drawing ----------------------------------------------------------------------

    def _draw_board(self, canvas: tk.Canvas, fleet: list[dict], incoming_shots: list[dict]) -> None:
        canvas.delete("all")
        size = BOARD_SIZE * CELL_SIZE
        canvas.create_rectangle(0, 0, size, size, fill=WATER_COLOR, outline="")
        for i in range(BOARD_SIZE + 1):
            canvas.create_line(0, i * CELL_SIZE, size, i * CELL_SIZE, fill=GRID_LINE_COLOR)
            canvas.create_line(i * CELL_SIZE, 0, i * CELL_SIZE, size, fill=GRID_LINE_COLOR)

        for ship in fleet:
            self._draw_ship(canvas, ship)

        for shot in incoming_shots:
            self._draw_shot_marker(canvas, shot)

    def _draw_ship(self, canvas: tk.Canvas, ship: dict) -> None:
        cells = ship["cells"]
        rows = [cell[0] for cell in cells]
        cols = [cell[1] for cell in cells]
        x0 = min(cols) * CELL_SIZE + SHIP_MARGIN
        y0 = min(rows) * CELL_SIZE + SHIP_MARGIN
        x1 = (max(cols) + 1) * CELL_SIZE - SHIP_MARGIN
        y1 = (max(rows) + 1) * CELL_SIZE - SHIP_MARGIN

        fill = SUNK_SHIP_COLOR if ship["sunk"] else SHIP_COLOR
        canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=SHIP_OUTLINE, width=2)

        if not ship["sunk"]:
            mid_x, mid_y = (x0 + x1) / 2, (y0 + y1) / 2
            if max(cols) > min(cols):
                canvas.create_line(x0 + 6, mid_y, x1 - 6, mid_y, fill=SHIP_HIGHLIGHT, width=2)
            else:
                canvas.create_line(mid_x, y0 + 6, mid_x, y1 - 6, fill=SHIP_HIGHLIGHT, width=2)
        else:
            canvas.create_line(x0 + 4, y0 + 4, x1 - 4, y1 - 4, fill=SUNK_MARK_COLOR, width=3)
            canvas.create_line(x0 + 4, y1 - 4, x1 - 4, y0 + 4, fill=SUNK_MARK_COLOR, width=3)

    def _draw_shot_marker(self, canvas: tk.Canvas, shot: dict) -> None:
        center_x = shot["col"] * CELL_SIZE + CELL_SIZE / 2
        center_y = shot["row"] * CELL_SIZE + CELL_SIZE / 2
        if shot["result"] in ("hit", "sunk"):
            radius = CELL_SIZE * 0.27
            canvas.create_oval(
                center_x - radius, center_y - radius, center_x + radius, center_y + radius,
                fill=HIT_COLOR, outline=HIT_OUTLINE, width=2,
            )
            canvas.create_line(center_x - radius * 0.5, center_y, center_x + radius * 0.5, center_y, fill=HIT_OUTLINE, width=2)
            canvas.create_line(center_x, center_y - radius * 0.5, center_x, center_y + radius * 0.5, fill=HIT_OUTLINE, width=2)
        else:
            radius = CELL_SIZE * 0.20
            canvas.create_oval(
                center_x - radius, center_y - radius, center_x + radius, center_y + radius,
                outline=MISS_OUTLINE, fill=MISS_COLOR, width=2,
            )

    # -- status -------------------------------------------------------------------------

    def _status_text(
        self,
        state: dict,
        turn: int | None,
        acting_player: str | None,
        action: dict | None,
    ) -> str:
        if state["done"]:
            return f"Game over -- winner is {state['winner']}"

        if turn is None or acting_player is None or action is None:
            current = state["current_player"]
            if state["phase"] == "placement":
                ship_name, ship_length = SHIPS[len(state["fleets"][current])]
                return f"Placement: {current} is placing their {ship_name} ({ship_length} cells)"
            return f"Battle: {current} to fire"

        if action.get("type") == "place_ship":
            return (
                f"Turn {turn}: {acting_player} placed their {action['ship']} "
                f"at ({action['row']}, {action['col']}), {action['orientation']}"
            )

        last_shot = state["shots"][acting_player][-1]
        outcomes = {
            "miss": "missed",
            "hit": "scored a hit",
            "sunk": f"sank the {last_shot['ship']}",
        }
        return (
            f"Turn {turn}: {acting_player} fired at ({last_shot['row']}, {last_shot['col']}) "
            f"-- {outcomes[last_shot['result']]}"
        )
