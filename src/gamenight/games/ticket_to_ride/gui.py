from __future__ import annotations

import math
import tkinter as tk

from gamenight.games.ticket_to_ride.data import CITIES, ROUTES

MAP_WIDTH = 900
MAP_HEIGHT = 500
MAP_MARGIN = 34
DOUBLE_ROUTE_OFFSET = 5

BG_COLOR = "#0a1622"
PANEL_BG = "#0a1622"
CITY_FILL = "#e8eaed"
CITY_OUTLINE = "#0a1622"
LABEL_COLOR = "#9fb0bf"
TEXT_COLOR = "#eef4f8"
DIM_TEXT = "#7a8a9a"

ROUTE_COLOR_HEX = {
    "purple": "#b388ff",
    "white": "#e8eaed",
    "blue": "#4da6ff",
    "yellow": "#ffe066",
    "orange": "#ffa94d",
    "black": "#9aa0a6",
    "red": "#ff6b6b",
    "green": "#69db7c",
    "gray": "#5b6672",
}

PLAYER_COLORS = ["#ff5c5c", "#5ab0ff", "#5ce39a", "#ffcf56", "#c77dff"]


def _screen_xy(city: str) -> tuple[float, float]:
    x, y = CITIES[city]
    sx = MAP_MARGIN + x * (MAP_WIDTH - 2 * MAP_MARGIN)
    sy = MAP_MARGIN + (1 - y) * (MAP_HEIGHT - 2 * MAP_MARGIN)  # data's y increases north; screen y increases down
    return sx, sy


class TicketToRideViewer:
    """A single compact, whole-map view -- no scrolling, no zoom, everything visible
    at once. Unclaimed routes render as thin lines in their own official color;
    claiming one thickens the line and adds a small dot in the claiming player's
    color at its midpoint, so ownership reads at a glance without needing a second
    color scheme layered on top of the route colors that already matter for play."""

    def __init__(self, player_ids: list[str], matchup_label: str | None = None) -> None:
        self.closed = False
        self.player_ids = player_ids
        self.player_color = {pid: PLAYER_COLORS[i % len(PLAYER_COLORS)] for i, pid in enumerate(player_ids)}

        self.root = tk.Tk()
        self.root.title("AI Game Night - Ticket to Ride")
        self.root.configure(bg=BG_COLOR)
        width = MAP_WIDTH + 20
        height = MAP_HEIGHT + 170 + 16 * (max(0, (len(player_ids) - 1) // 2))
        self.root.geometry(f"{width}x{height}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if matchup_label:
            tk.Label(self.root, text=matchup_label, font=("Helvetica", 11), fg=DIM_TEXT, bg=BG_COLOR).pack(pady=(8, 0))

        self.status_var = tk.StringVar(value="Starting game...")
        tk.Label(self.root, textvariable=self.status_var, font=("Helvetica", 13, "bold"), fg=TEXT_COLOR, bg=BG_COLOR).pack(
            pady=(4, 4)
        )

        self.players_var = tk.StringVar(value="")
        tk.Label(
            self.root,
            textvariable=self.players_var,
            font=("Helvetica", 10),
            fg=DIM_TEXT,
            bg=BG_COLOR,
            justify="center",
        ).pack()

        self.canvas = tk.Canvas(self.root, width=MAP_WIDTH, height=MAP_HEIGHT, bg=BG_COLOR, highlightthickness=0)
        self.canvas.pack(pady=(8, 4))

        self.record_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.record_var, font=("Helvetica", 10), fg=DIM_TEXT, bg=BG_COLOR).pack()

        self._draw_static_map()

    # -- static map (cities + unclaimed routes) drawn once, then redrawn on top per update --

    def _draw_static_map(self) -> None:
        self.canvas.delete("all")
        self._draw_routes({})
        self._draw_cities()

    def _draw_cities(self) -> None:
        for name in CITIES:
            x, y = _screen_xy(name)
            self.canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=CITY_FILL, outline=CITY_OUTLINE, width=1)
            self.canvas.create_text(x, y - 9, text=name, fill=LABEL_COLOR, font=("Helvetica", 7), anchor="s")

    def _draw_routes(self, route_owner_by_id: dict) -> None:
        for route in ROUTES:
            ax, ay = _screen_xy(route.city_a)
            bx, by = _screen_xy(route.city_b)
            offset = self._perpendicular_offset(ax, ay, bx, by, route)
            ax, ay, bx, by = ax + offset[0], ay + offset[1], bx + offset[0], by + offset[1]

            owner = route_owner_by_id.get(route.route_id)
            color = ROUTE_COLOR_HEX.get(route.color, ROUTE_COLOR_HEX["gray"])
            width = 4 if owner else 1.6
            self.canvas.create_line(ax, ay, bx, by, fill=color, width=width, capstyle="round")
            if owner:
                mx, my = (ax + bx) / 2, (ay + by) / 2
                dot_color = self.player_color.get(owner, "#ffffff")
                self.canvas.create_oval(mx - 3.5, my - 3.5, mx + 3.5, my + 3.5, fill=dot_color, outline="")

    @staticmethod
    def _perpendicular_offset(ax: float, ay: float, bx: float, by: float, route) -> tuple[float, float]:
        if route.twin_id is None:
            return (0.0, 0.0)
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy) or 1.0
        perp = (-dy / length, dx / length)
        # Lower route_id of the pair offsets one way, the other offsets the opposite way.
        sign = 1 if route.route_id < route.twin_id else -1
        return (perp[0] * DOUBLE_ROUTE_OFFSET * sign, perp[1] * DOUBLE_ROUTE_OFFSET * sign)

    # -- public viewer API ------------------------------------------------------------------

    def set_names(self, names: dict[str, str]) -> None:
        self.names = names
        self.root.update_idletasks()

    def set_records(self, records: dict[str, tuple[int, int]]) -> None:
        parts = [f"{pid}: {wins}W-{losses}L" for pid, (wins, losses) in records.items()]
        self.record_var.set("   ".join(parts))
        self.root.update_idletasks()

    def update_state(
        self,
        state,
        turn: int | None = None,
        acting_player: str | None = None,
        action: dict | None = None,
    ) -> None:
        if self.closed:
            return

        route_owner_by_id = {i: owner for i, owner in enumerate(state["route_owner"]) if owner is not None}
        self.canvas.delete("all")
        self._draw_routes(route_owner_by_id)
        self._draw_cities()

        # Compact per-player summaries, wrapped two-per-line so this stays legible
        # (and stays inside the window) at any supported player count (2-5).
        entries = []
        for pid in self.player_ids:
            p = state["players"][pid]
            entries.append(f"{pid}  T:{p['trains_remaining']}  H:{sum(p['hand'].values())}  "
                            f"Tk:{len(p['tickets'])}  Pts:{p['route_score']}")
        rows = ["    ".join(entries[i:i + 2]) for i in range(0, len(entries), 2)]
        self.players_var.set("\n".join(rows))

        if state.get("done"):
            winner = state.get("winner")
            self.status_var.set(f"Game over -- winner: {winner}" if winner else "Game over -- draw")
        elif acting_player:
            self.status_var.set(f"Turn {turn}: {acting_player}  |  phase: {state['phase']}")
        else:
            self.status_var.set("Starting game...")

        self.root.update_idletasks()
        self.root.update()

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
