from __future__ import annotations

import tkinter as tk

from gamenight.games.splendor.game import COLORS

FONT = "Helvetica"

BG_TOP = "#0f0c09"
BG_BOTTOM = "#241a12"
INK = "#f3ece0"
MUTED = "#a8998a"
CARD_BG = "#2a2118"
DECK_BG = "#211a13"
DECK_STROKE = "#4a3c28"
MAT_BG = "#211a13"
MAT_BORDER = "#3a2f22"
STATUS_BG = "#241d15"

GEM_FILL = {
    "white": "#ece6d6",
    "blue": "#3f7cc2",
    "green": "#3f9d5c",
    "red": "#c0394a",
    "black": "#5c564c",
    "gold": "#d4af37",
}
GEM_OUTLINE = {
    "white": "#8f8672",
    "blue": "#1f4a7a",
    "green": "#1f5c34",
    "red": "#7a1f2a",
    "black": "#211f1b",
    "gold": "#8a6a1a",
}
GEM_TEXT = {
    "white": "#241d15",
    "blue": "#eef4fb",
    "green": "#eef8f0",
    "red": "#fbeeef",
    "black": "#ece6d6",
    "gold": "#241d15",
}
ALL_TOKEN_TYPES = COLORS + ["gold"]

# Cycled by seat index -- enough distinct, legible-on-dark-background hues for the
# 4-player maximum. Seat 0 (bottom / "your" seat) always gets the first one.
SEAT_ACCENTS = ["#e0a458", "#5aa9a3", "#a884d1", "#d18a9e"]

CARD_W, CARD_H = 84, 108
COL_STEP = CARD_W + 14
ROW_GAP = 12
DECK_W = 46
MARKET_X = DECK_W + 10

TABLE_W = 440
TABLE_H = 580

MAT_W, MAT_H = 460, 262
GAP = 26
MARGIN = 24


def _seat_layout(num_players: int) -> dict:
    """Returns pixel positions for the table and each seat's mat, seat 0 = bottom
    ("your" seat, closest to the viewer), remaining seats fanned around the other
    edges -- the same "you at the bottom, everyone else around the table" arrangement
    a physical card game has, rather than a flat left-to-right row of mats.
    """
    if num_players == 2:
        canvas_w = max(TABLE_W, MAT_W) + 2 * MARGIN
        center_x = canvas_w / 2
        top_y = MARGIN
        table_y = top_y + MAT_H + GAP
        bottom_y = table_y + TABLE_H + GAP
        canvas_h = bottom_y + MAT_H + MARGIN
        return {
            "canvas_w": canvas_w,
            "canvas_h": canvas_h,
            "table_xy": (center_x - TABLE_W / 2, table_y),
            "mats": [
                (center_x - MAT_W / 2, bottom_y),  # seat 0: bottom
                (center_x - MAT_W / 2, top_y),  # seat 1: top
            ],
        }

    if num_players == 3:
        top_row_w = 2 * MAT_W + GAP
        canvas_w = max(TABLE_W, top_row_w, MAT_W) + 2 * MARGIN
        center_x = canvas_w / 2
        top_y = MARGIN
        table_y = top_y + MAT_H + GAP
        bottom_y = table_y + TABLE_H + GAP
        canvas_h = bottom_y + MAT_H + MARGIN
        return {
            "canvas_w": canvas_w,
            "canvas_h": canvas_h,
            "table_xy": (center_x - TABLE_W / 2, table_y),
            "mats": [
                (center_x - MAT_W / 2, bottom_y),  # seat 0: bottom
                (center_x - GAP / 2 - MAT_W, top_y),  # seat 1: top-left
                (center_x + GAP / 2, top_y),  # seat 2: top-right
            ],
        }

    # num_players == 4: bottom / left / top / right, like sitting at a square table.
    canvas_w = MAT_W + GAP + TABLE_W + GAP + MAT_W + 2 * MARGIN
    center_x = canvas_w / 2
    top_y = MARGIN
    table_y = top_y + MAT_H + GAP
    bottom_y = table_y + TABLE_H + GAP
    canvas_h = bottom_y + MAT_H + MARGIN
    side_y = table_y + TABLE_H / 2 - MAT_H / 2
    return {
        "canvas_w": canvas_w,
        "canvas_h": canvas_h,
        "table_xy": (center_x - TABLE_W / 2, table_y),
        "mats": [
            (center_x - MAT_W / 2, bottom_y),  # seat 0: bottom
            (MARGIN, side_y),  # seat 1: left
            (center_x - MAT_W / 2, top_y),  # seat 2: top
            (canvas_w - MARGIN - MAT_W, side_y),  # seat 3: right
        ],
    }


class SplendorViewer:
    """Spectator view for Splendor, seated like a real table: seat 0 (`player_ids[0]`)
    always sits at the bottom, closest to the viewer, and every other seat fans out
    around the remaining edges (see `_seat_layout`).

    Unlike Battleship, there's no "spectator sees more than the bots" trick needed for
    most of the board -- the market, bank, and every player's points/bonuses/tokens are
    already public (see BOT_SPEC.md's Information Policy). Reserved cards ARE drawn in
    full here, though, which *is* a spectator-only privilege the same way Battleship's
    TV view is: a market-reserved card was plainly visible to everyone the instant
    before it was taken, and even a blind deck reservation is exactly the kind of thing
    worth showing a human watching along, even though `observe()` keeps redacting
    reserved cards from the *opponent bot* -- the two are intentionally different, one
    is what makes competition fair, the other is what makes the broadcast useful.

    The canvas scrolls (both directions) rather than trying to shrink an already-dense
    board down to fit a fixed window -- 4-player games have real width and height it
    needs, and shrinking small text to squeeze it in would cost more readability than
    scrolling does.
    """

    def __init__(self, player_ids: list[str], matchup_label: str | None = None) -> None:
        self.closed = False
        self.player_ids = list(player_ids)
        self.layout = _seat_layout(len(self.player_ids))

        self.root = tk.Tk()
        self.root.title("AI Game Night - Splendor")
        self.root.configure(bg=BG_TOP)
        viewport_w = min(self.layout["canvas_w"] + 40, 1180)
        viewport_h = min(self.layout["canvas_h"] + 90, 880)
        self.root.geometry(f"{int(viewport_w)}x{int(viewport_h)}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if matchup_label:
            tk.Label(
                self.root, text=matchup_label, font=(FONT, 12), fg=MUTED, bg=BG_TOP, wraplength=int(viewport_w) - 20
            ).pack(pady=(10, 0))

        self.status_var = tk.StringVar(value="Starting game...")
        tk.Label(
            self.root,
            textvariable=self.status_var,
            font=(FONT, 13, "bold"),
            fg=INK,
            bg=BG_TOP,
            wraplength=int(viewport_w) - 20,
        ).pack(pady=(6, 8))

        # Scrollable canvas: a fixed-size viewport onto a (usually larger) drawing
        # surface, so a 4-player board never gets clipped -- drag the scrollbars, use
        # the mouse wheel/trackpad, or resize the window; nothing gets silently cut off.
        frame = tk.Frame(self.root, bg=BG_TOP)
        frame.pack(fill="both", expand=True, padx=16, pady=(0, 4))
        vsb = tk.Scrollbar(frame, orient="vertical")
        hsb = tk.Scrollbar(frame, orient="horizontal")
        self.canvas = tk.Canvas(
            frame,
            width=min(self.layout["canvas_w"], viewport_w - 40),
            height=min(self.layout["canvas_h"], viewport_h - 130),
            bg=BG_BOTTOM,
            highlightthickness=0,
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
        )
        vsb.config(command=self.canvas.yview)
        hsb.config(command=self.canvas.xview)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        self.canvas.configure(scrollregion=(0, 0, self.layout["canvas_w"], self.layout["canvas_h"]))

        self.canvas.bind("<MouseWheel>", self._on_mousewheel)  # macOS / Windows
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))  # Linux
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
        self.canvas.bind("<Shift-MouseWheel>", lambda e: self.canvas.xview_scroll(int(-e.delta / 40), "units"))

        self.record_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.record_var, font=(FONT, 10), fg=MUTED, bg=BG_TOP).pack(pady=(0, 8))

        self._names: dict[str, str] = {pid: pid for pid in self.player_ids}

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 40), "units")

    def set_names(self, names: dict[str, str]) -> None:
        for player_id, name in names.items():
            self._names[player_id] = f"{player_id} ({name})"
        self.root.update_idletasks()

    def set_records(self, records: dict[str, tuple[int, int]]) -> None:
        text = "   |   ".join(
            f"{self._names.get(pid, pid)}: {wins}W-{losses}L" for pid, (wins, losses) in records.items()
        )
        self.record_var.set(text)
        self.root.update_idletasks()

    def update_state(
        self,
        state: dict,
        turn: int | None = None,
        acting_player: str | None = None,
        action: dict | None = None,
    ) -> None:
        if self.closed:
            return

        draw_board(self.canvas, state, self.player_ids, self.layout)
        self.status_var.set(status_text(state, turn, acting_player, action))

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


# -- drawing (module-level: reusable the way battleship/gui.py's draw_board is) -----


def draw_board(canvas: tk.Canvas, state: dict, player_ids: list[str], layout: dict) -> None:
    canvas.delete("all")

    table_x, table_y = layout["table_xy"]
    _draw_table(canvas, state, table_x, table_y)

    for seat_index, (mat_x, mat_y) in enumerate(layout["mats"]):
        player_id = player_ids[seat_index]
        accent = SEAT_ACCENTS[seat_index % len(SEAT_ACCENTS)]
        is_current = state["current_player"] == player_id and not state["done"]
        _draw_mat(canvas, mat_x, mat_y, player_id, state["players"][player_id], accent, is_current)


def _draw_table(canvas: tk.Canvas, state: dict, x: float, y: float) -> None:
    canvas.create_rectangle(
        x - 12, y - 12, x + TABLE_W + 12, y + TABLE_H + 12, fill=STATUS_BG, outline=DECK_STROKE, width=1
    )

    nobles = state["nobles"]
    canvas.create_text(
        x + 4, y + 12, text=f"NOBLES IN PLAY ({len(nobles)})", font=(FONT, 10, "bold"), fill=MUTED, anchor="w"
    )
    nx = x + 4
    for noble in nobles:
        _draw_noble(canvas, nx, y + 22, noble)
        nx += 66

    market_y = y + 96
    canvas.create_text(x + 4, market_y - 10, text="MARKET", font=(FONT, 10, "bold"), fill=MUTED, anchor="w")
    row_y = market_y
    for tier_key, label in (("3", "III"), ("2", "II"), ("1", "I")):
        tier = state["tiers"][tier_key]
        _draw_deck_stub(canvas, x + 4, row_y, label, len(tier["deck"]))
        cx = x + 4 + MARKET_X
        for card in tier["face_up"]:
            _draw_card(canvas, cx, row_y, card)
            cx += COL_STEP
        row_y += CARD_H + ROW_GAP

    bank_y = row_y + 14
    canvas.create_text(x + 4, bank_y, text="BANK", font=(FONT, 10, "bold"), fill=MUTED, anchor="w")
    cy = bank_y + 36
    cx = x + 4 + 24
    for color in ALL_TOKEN_TYPES:
        canvas.create_oval(
            cx - 22, cy - 22, cx + 22, cy + 22, fill=GEM_FILL[color], outline=GEM_OUTLINE[color], width=2
        )
        canvas.create_text(cx, cy, text=str(state["bank"][color]), font=(FONT, 14, "bold"), fill=GEM_TEXT[color])
        canvas.create_text(cx, cy + 32, text=color, font=(FONT, 9), fill=MUTED)
        cx += 64


def _draw_noble(canvas: tk.Canvas, x: float, y: float, noble: dict) -> None:
    size = 60
    canvas.create_rectangle(x, y, x + size, y + size, fill="#241d15", outline="#7a5a2e", width=2)
    _badge(canvas, x + 14, y + 14, "gold", noble["points"], r=11)
    cx = x + size - 13
    for color, amount in noble["requirement"].items():
        _pip(canvas, cx, y + size - 13, color, amount, r=10)
        cx -= 22


def _draw_deck_stub(canvas: tk.Canvas, x: float, y: float, label: str, remaining: int) -> None:
    canvas.create_rectangle(x, y, x + DECK_W, y + CARD_H, fill=DECK_BG, outline=DECK_STROKE, width=2)
    for i in range(5):
        yy = y + 8 + i * 9
        canvas.create_line(x + 5, yy, x + DECK_W - 5, yy + 11, fill="#3a2f22")
    canvas.create_text(x + DECK_W / 2, y + 16, text=label, font=(FONT, 12, "bold"), fill="#c9b98f")
    canvas.create_text(x + DECK_W / 2, y + CARD_H - 10, text=f"{remaining}", font=(FONT, 9), fill=MUTED)


def _draw_card(canvas: tk.Canvas, x: float, y: float, card: dict) -> None:
    bonus = card["bonus"]
    canvas.create_rectangle(x, y, x + CARD_W, y + CARD_H, fill=CARD_BG, outline=GEM_OUTLINE[bonus], width=2)
    canvas.create_rectangle(x + 7, y + 7, x + 21, y + 21, fill=GEM_FILL[bonus], outline=GEM_OUTLINE[bonus])
    if card["points"]:
        _badge(canvas, x + CARD_W - 15, y + 15, "gold", card["points"], r=10)

    py = y + CARD_H - 15
    for color in COLORS:
        amount = card["cost"].get(color, 0)
        if amount:
            _pip(canvas, x + 15, py, color, amount, r=8)
            py -= 19


def _draw_mini_card(canvas: tk.Canvas, x: float, y: float, w: float, h: float, card: dict) -> None:
    """A smaller version of `_draw_card`, used for a player mat's reserved-card row.

    Every reserved card is drawn in full here regardless of `card["source"]` -- this
    is the spectator GUI, which is deliberately more generous than `observe()` (see
    the "Information Policy" note above `SplendorViewer`). A small "(blind)" tag marks
    the ones reserved off the top of a deck, purely as a spectator convenience: it's
    the one thing even a bot's own `observe()` never reveals about an *opponent's*
    reserve (market-origin reserves are shown to bots too -- see BOT_SPEC.md).
    """
    bonus = card["bonus"]
    canvas.create_rectangle(x, y, x + w, y + h, fill=CARD_BG, outline=GEM_OUTLINE[bonus], width=2)
    canvas.create_rectangle(x + 4, y + 4, x + 13, y + 13, fill=GEM_FILL[bonus], outline=GEM_OUTLINE[bonus])
    if card["points"]:
        _badge(canvas, x + w - 10, y + 10, "gold", card["points"], r=8)
    py = y + h - 10
    for color in COLORS:
        amount = card["cost"].get(color, 0)
        if amount:
            _pip(canvas, x + 10, py, color, amount, r=6)
            py -= 13
    if card.get("source") == "deck":
        canvas.create_text(x + w / 2, y + h + 9, text="(blind)", font=(FONT, 7), fill=MUTED)


def _draw_card_stack(canvas: tk.Canvas, x: float, y: float, color: str, count: int) -> float:
    """Draws up to 3 overlapping card silhouettes for one bonus color (a physical
    stack visually caps out anyway -- what matters is the color and the count) plus a
    count badge, and returns the x position for whatever comes next in the row."""
    if count <= 0:
        return x
    stack_w, stack_h = 24, 32
    layers = min(count, 3)
    for i in range(layers):
        offset = i * 3
        canvas.create_rectangle(
            x + offset, y + offset, x + offset + stack_w, y + offset + stack_h,
            fill=GEM_FILL[color], outline=GEM_OUTLINE[color], width=1.5,
        )
    badge_x = x + (layers - 1) * 3 + stack_w - 8
    badge_y = y + (layers - 1) * 3 + stack_h - 8
    canvas.create_oval(badge_x - 9, badge_y - 9, badge_x + 9, badge_y + 9, fill="#241d15", outline=GEM_OUTLINE[color])
    canvas.create_text(badge_x, badge_y, text=str(count), font=(FONT, 9, "bold"), fill=INK)
    return x + stack_w + (layers - 1) * 3 + 12


def _draw_mat(
    canvas: tk.Canvas, x: float, y: float, player_id: str, player: dict, accent: str, is_current: bool
) -> None:
    border = accent if is_current else MAT_BORDER
    canvas.create_rectangle(
        x, y, x + MAT_W, y + MAT_H, fill=MAT_BG, outline=border, width=3 if is_current else 1
    )
    canvas.create_text(x + 14, y + 18, text=player_id, font=(FONT, 13, "bold"), fill=accent, anchor="w")
    canvas.create_text(
        x + MAT_W - 14, y + 18, text=f"{player['points']} pts", font=(FONT, 13, "bold"), fill=INK, anchor="e"
    )

    canvas.create_text(x + 14, y + 42, text="OWNED CARDS (by bonus color)", font=(FONT, 9), fill=MUTED, anchor="w")
    cx = x + 14
    any_owned = False
    for color in COLORS:
        count = player["bonuses"][color]
        if count:
            any_owned = True
            cx = _draw_card_stack(canvas, cx, y + 50, color, count) + 6
    if not any_owned:
        canvas.create_text(x + 14, y + 68, text="none yet", font=(FONT, 10), fill=MUTED, anchor="w")

    canvas.create_text(x + 14, y + 108, text="TOKENS HELD", font=(FONT, 9), fill=MUTED, anchor="w")
    cx = x + 28
    for color in ALL_TOKEN_TYPES:
        amount = player["tokens"][color]
        if amount:
            _pip(canvas, cx, y + 126, color, amount, r=11)
            cx += 26

    reserved = player["reserved"]
    canvas.create_text(x + 14, y + 150, text=f"RESERVED ({len(reserved)}/3)", font=(FONT, 9), fill=MUTED, anchor="w")
    rx = x + 14
    for card in reserved:
        _draw_mini_card(canvas, rx, y + 158, 60, 78, card)
        rx += 68
    if not reserved:
        canvas.create_text(x + 14, y + 178, text="none", font=(FONT, 10), fill=MUTED, anchor="w")


def _badge(canvas: tk.Canvas, cx: float, cy: float, color: str, value: int, r: float) -> None:
    canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=GEM_FILL[color], outline=GEM_OUTLINE[color], width=1.5)
    canvas.create_text(cx, cy, text=str(value), font=(FONT, 10, "bold"), fill=GEM_TEXT[color])


def _pip(canvas: tk.Canvas, cx: float, cy: float, color: str, value: int, r: float) -> None:
    canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=GEM_FILL[color], outline=GEM_OUTLINE[color], width=1.5)
    canvas.create_text(cx, cy, text=str(value), font=(FONT, 9, "bold"), fill=GEM_TEXT[color])


# -- status ----------------------------------------------------------------------------


def status_text(state: dict, turn: int | None, acting_player: str | None, action: dict | None) -> str:
    if state["done"]:
        if state["winner"] is None:
            return "Game over -- a true draw (equal points, equal cards)"
        return f"Game over -- winner is {state['winner']}"

    if turn is None or acting_player is None or action is None:
        current = state["current_player"]
        if state["phase"] == "discard":
            return f"{current} must discard down to 10 tokens"
        if state["phase"] == "noble_choice":
            return f"{current} qualifies for multiple nobles -- choosing one"
        return f"{current} to act"

    return f"Turn {turn}: {acting_player} {_describe(action, state, acting_player)}"


def _describe(action: dict, state: dict, acting_player: str) -> str:
    """Describes the action that produced `state`.

    `action` is the *raw* action a bot returned (exactly the dict `run-game`'s
    `step_observer` hands to `update_state`, per `core/match.py`'s replay event shape)
    -- it does NOT carry the richer fields (`points`, `bonus`, ...) that only live in
    `StepResult.events`. Same fix Battleship's `status_text` already uses: pull that
    detail back out of the resulting `state` instead (e.g. the just-purchased card is
    always the last entry in the buyer's now-updated `owned` list).
    """
    action_type = action["type"]
    if action_type == "take_tokens":
        colors = action["colors"]
        if len(colors) == 2 and colors[0] == colors[1]:
            return f"took 2x {colors[0]}"
        return f"took 1 each of {', '.join(colors)}"
    if action_type == "reserve_card":
        if action["location"] == "deck":
            return f"reserved blind from tier {action['tier']}"
        return f"reserved {action['card_id']}"
    if action_type == "purchase_card":
        card = state["players"][acting_player]["owned"][-1]
        pts = f", +{card['points']}pt" if card["points"] else ""
        return f"purchased {card['id']} (bonus: {card['bonus']}{pts})"
    if action_type == "discard_token":
        return f"discarded 1 {action['color']}"
    if action_type == "choose_noble":
        return f"claimed noble {action['noble_id']}"
    if action_type == "pass":
        return "passed (no legal action available)"
    return str(action)
