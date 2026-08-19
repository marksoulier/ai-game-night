"""Static board data for the official USA map, verified against multiple sources
(see README.md's Research section for citations): 36 cities, 100 route segments
(22 of which are "double routes" -- two parallel segments between the same pair of
cities), and all 30 official Destination Ticket cards.

This module is deliberately pure data plus small derivation helpers -- no game rules
live here (see game.py), matching the "board data is dumb static data" split
Splendor's `types.py` established.
"""

from __future__ import annotations

from dataclasses import dataclass

TRAIN_COLORS: tuple[str, ...] = (
    "purple", "white", "blue", "yellow", "orange", "black", "red", "green",
)
WILD = "wild"  # a locomotive card -- substitutes for any color when claiming a route
GRAY = "gray"  # a route's own "color" when it accepts any single declared color

# Official train car deck composition: 12 of each of the 8 colors + 14 locomotives = 110.
TRAIN_CARDS_PER_COLOR = 12
WILD_CARDS_IN_DECK = 14

TRAINS_PER_PLAYER = 45
FACE_UP_DISPLAY_SIZE = 5
INITIAL_HAND_SIZE = 4
TICKET_DRAW_COUNT = 3
INITIAL_TICKET_MIN_KEEP = 2
TICKET_DRAW_MIN_KEEP = 1
LONGEST_PATH_BONUS = 10

# Route length -> points, the official scoring table.
ROUTE_POINTS: dict[int, int] = {1: 1, 2: 2, 3: 4, 4: 7, 5: 10, 6: 15}

MIN_PLAYERS = 2
MAX_PLAYERS = 5


@dataclass(slots=True, frozen=True)
class Route:
    route_id: int
    city_a: str
    city_b: str
    length: int
    color: str  # one of TRAIN_COLORS, or GRAY
    twin_id: int | None  # the other route_id of the same city pair, if any


@dataclass(slots=True, frozen=True)
class Ticket:
    ticket_id: int
    city_a: str
    city_b: str
    points: int


CITIES: dict[str, tuple[float, float]] = {
    "Atlanta": (0.7806, 0.3669),
    "Boston": (0.9452, 0.7936),
    "Calgary": (0.2347, 0.8715),
    "Charleston": (0.8719, 0.3564),
    "Chicago": (0.6839, 0.5964),
    "Dallas": (0.5545, 0.2210),
    "Denver": (0.3903, 0.4511),
    "Duluth": (0.5636, 0.6858),
    "El Paso": (0.3777, 0.1854),
    "Helena": (0.3327, 0.6775),
    "Houston": (0.5954, 0.1629),
    "Kansas City": (0.5549, 0.4772),
    "Las Vegas": (0.2075, 0.3355),
    "Little Rock": (0.6233, 0.3444),
    "Los Angeles": (0.1447, 0.2503),
    "Miami": (0.9037, 0.1253),
    "Montreal": (0.8754, 0.8777),
    "Nashville": (0.7310, 0.4186),
    "New Orleans": (0.6860, 0.1802),
    "New York": (0.8939, 0.6837),
    "Oklahoma City": (0.5354, 0.3501),
    "Omaha": (0.5347, 0.5515),
    "Phoenix": (0.2616, 0.2403),
    "Pittsburgh": (0.8116, 0.6179),
    "Portland": (0.0823, 0.6905),
    "Raleigh": (0.8447, 0.4521),
    "Saint Louis": (0.6383, 0.4746),
    "Salt Lake City": (0.2626, 0.4965),
    "San Francisco": (0.0684, 0.4024),
    "Santa Fe": (0.3830, 0.3182),
    "Sault St. Marie": (0.6885, 0.7826),
    "Seattle": (0.1036, 0.7669),
    "Toronto": (0.7952, 0.7517),
    "Vancouver": (0.1081, 0.8458),
    "Washington": (0.9016, 0.5509),
    "Winnipeg": (0.4534, 0.8553),
}
# Coordinates are normalized to [0, 1] in standard math orientation (y increases
# northward, e.g. Vancouver y=0.85 vs Miami y=0.13) -- a renderer drawing on a
# screen/canvas (y increases downward) needs to flip: screen_y = 1 - y.

# (city_a, city_b, length, color) -- "gray" routes accept any single declared color.
# Two entries with the same city pair are a "double route" (see game.py's double-route
# claiming rule: unusable in pairs at 2-3 players, claimable by two different players
# but never the same player at 4-5 players).
_ROUTE_TUPLES: list[tuple[str, str, int, str]] = [
    ("Vancouver", "Calgary", 3, "gray"),
    ("Vancouver", "Seattle", 1, "gray"),
    ("Vancouver", "Seattle", 1, "gray"),
    ("Seattle", "Calgary", 4, "gray"),
    ("Seattle", "Helena", 6, "yellow"),
    ("Seattle", "Portland", 1, "gray"),
    ("Seattle", "Portland", 1, "gray"),
    ("Portland", "Salt Lake City", 6, "blue"),
    ("Portland", "San Francisco", 5, "green"),
    ("Portland", "San Francisco", 5, "purple"),
    ("San Francisco", "Salt Lake City", 5, "orange"),
    ("San Francisco", "Salt Lake City", 5, "white"),
    ("San Francisco", "Los Angeles", 3, "yellow"),
    ("San Francisco", "Los Angeles", 3, "purple"),
    ("Los Angeles", "Las Vegas", 2, "gray"),
    ("Los Angeles", "Phoenix", 3, "gray"),
    ("Los Angeles", "El Paso", 6, "black"),
    ("Calgary", "Winnipeg", 6, "white"),
    ("Calgary", "Helena", 4, "gray"),
    ("Helena", "Winnipeg", 4, "blue"),
    ("Helena", "Salt Lake City", 3, "purple"),
    ("Helena", "Denver", 4, "green"),
    ("Helena", "Duluth", 6, "orange"),
    ("Helena", "Omaha", 5, "red"),
    ("Salt Lake City", "Denver", 3, "red"),
    ("Salt Lake City", "Denver", 3, "yellow"),
    ("Las Vegas", "Salt Lake City", 3, "orange"),
    ("Phoenix", "Denver", 5, "white"),
    ("Phoenix", "Santa Fe", 3, "gray"),
    ("Phoenix", "El Paso", 3, "gray"),
    ("Winnipeg", "Sault St. Marie", 6, "gray"),
    ("Winnipeg", "Duluth", 4, "black"),
    ("Duluth", "Sault St. Marie", 3, "gray"),
    ("Duluth", "Toronto", 6, "purple"),
    ("Duluth", "Chicago", 3, "red"),
    ("Duluth", "Omaha", 2, "gray"),
    ("Duluth", "Omaha", 2, "gray"),
    ("Omaha", "Chicago", 4, "blue"),
    ("Omaha", "Kansas City", 1, "gray"),
    ("Omaha", "Kansas City", 1, "gray"),
    ("Kansas City", "Saint Louis", 2, "blue"),
    ("Kansas City", "Saint Louis", 2, "purple"),
    ("Kansas City", "Oklahoma City", 2, "gray"),
    ("Kansas City", "Oklahoma City", 2, "gray"),
    ("Oklahoma City", "Little Rock", 2, "gray"),
    ("Oklahoma City", "Dallas", 2, "gray"),
    ("Oklahoma City", "Dallas", 2, "gray"),
    ("Dallas", "Little Rock", 2, "gray"),
    ("Dallas", "Houston", 1, "gray"),
    ("Dallas", "Houston", 1, "gray"),
    ("Houston", "New Orleans", 2, "gray"),
    ("El Paso", "Houston", 6, "green"),
    ("El Paso", "Dallas", 4, "red"),
    ("El Paso", "Oklahoma City", 5, "yellow"),
    ("El Paso", "Santa Fe", 2, "gray"),
    ("Santa Fe", "Oklahoma City", 3, "blue"),
    ("Oklahoma City", "Denver", 4, "red"),
    ("Santa Fe", "Denver", 2, "gray"),
    ("Denver", "Kansas City", 4, "black"),
    ("Denver", "Kansas City", 4, "orange"),
    ("Denver", "Omaha", 4, "purple"),
    ("New Orleans", "Miami", 6, "red"),
    ("New Orleans", "Atlanta", 4, "orange"),
    ("New Orleans", "Atlanta", 4, "yellow"),
    ("New Orleans", "Little Rock", 3, "green"),
    ("Little Rock", "Nashville", 3, "white"),
    ("Little Rock", "Saint Louis", 2, "gray"),
    ("Saint Louis", "Nashville", 2, "gray"),
    ("Saint Louis", "Pittsburgh", 5, "green"),
    ("Saint Louis", "Chicago", 2, "green"),
    ("Saint Louis", "Chicago", 2, "white"),
    ("Chicago", "Pittsburgh", 3, "black"),
    ("Chicago", "Pittsburgh", 3, "orange"),
    ("Chicago", "Toronto", 4, "white"),
    ("Sault St. Marie", "Montreal", 5, "black"),
    ("Toronto", "Montreal", 3, "gray"),
    ("Sault St. Marie", "Toronto", 2, "gray"),
    ("Toronto", "Pittsburgh", 2, "gray"),
    ("Pittsburgh", "New York", 2, "white"),
    ("Pittsburgh", "New York", 2, "green"),
    ("Pittsburgh", "Washington", 2, "gray"),
    ("Pittsburgh", "Raleigh", 2, "gray"),
    ("Nashville", "Raleigh", 3, "black"),
    ("Nashville", "Atlanta", 1, "gray"),
    ("Nashville", "Pittsburgh", 4, "yellow"),
    ("Atlanta", "Miami", 5, "blue"),
    ("Atlanta", "Charleston", 2, "gray"),
    ("Atlanta", "Raleigh", 2, "gray"),
    ("Atlanta", "Raleigh", 2, "gray"),
    ("Charleston", "Miami", 4, "purple"),
    ("Raleigh", "Charleston", 2, "gray"),
    ("Raleigh", "Washington", 2, "gray"),
    ("Raleigh", "Washington", 2, "gray"),
    ("Washington", "New York", 2, "orange"),
    ("Washington", "New York", 2, "black"),
    ("New York", "Boston", 2, "yellow"),
    ("New York", "Boston", 2, "red"),
    ("New York", "Montreal", 3, "blue"),
    ("Boston", "Montreal", 2, "gray"),
    ("Boston", "Montreal", 2, "gray"),
]

# (city_a, city_b, points) -- all 30 official Destination Ticket cards.
_TICKET_TUPLES: list[tuple[str, str, int]] = [
    ("Los Angeles", "New York", 21),
    ("Duluth", "Houston", 8),
    ("Sault St. Marie", "Nashville", 8),
    ("New York", "Atlanta", 6),
    ("Portland", "Nashville", 17),
    ("Vancouver", "Montreal", 20),
    ("Duluth", "El Paso", 10),
    ("Toronto", "Miami", 10),
    ("Portland", "Phoenix", 11),
    ("Dallas", "New York", 11),
    ("Calgary", "Salt Lake City", 7),
    ("Calgary", "Phoenix", 13),
    ("Los Angeles", "Miami", 20),
    ("Winnipeg", "Little Rock", 11),
    ("San Francisco", "Atlanta", 17),
    ("Kansas City", "Houston", 5),
    ("Los Angeles", "Chicago", 16),
    ("Denver", "Pittsburgh", 11),
    ("Chicago", "Santa Fe", 9),
    ("Vancouver", "Santa Fe", 13),
    ("Boston", "Miami", 12),
    ("Chicago", "New Orleans", 7),
    ("Montreal", "Atlanta", 9),
    ("Seattle", "New York", 22),
    ("Denver", "El Paso", 4),
    ("Helena", "Los Angeles", 8),
    ("Winnipeg", "Houston", 12),
    ("Montreal", "New Orleans", 13),
    ("Sault St. Marie", "Oklahoma City", 9),
    ("Seattle", "Los Angeles", 9),
]


def _build_routes() -> list[Route]:
    pair_indices: dict[tuple[str, str], list[int]] = {}
    for idx, (city_a, city_b, _length, _color) in enumerate(_ROUTE_TUPLES):
        key = tuple(sorted((city_a, city_b)))
        pair_indices.setdefault(key, []).append(idx)

    routes = []
    for idx, (city_a, city_b, length, color) in enumerate(_ROUTE_TUPLES):
        key = tuple(sorted((city_a, city_b)))
        siblings = [i for i in pair_indices[key] if i != idx]
        twin_id = siblings[0] if siblings else None
        routes.append(Route(route_id=idx, city_a=city_a, city_b=city_b, length=length, color=color, twin_id=twin_id))
    return routes


def _build_tickets() -> list[Ticket]:
    return [
        Ticket(ticket_id=idx, city_a=city_a, city_b=city_b, points=points)
        for idx, (city_a, city_b, points) in enumerate(_TICKET_TUPLES)
    ]


ROUTES: list[Route] = _build_routes()
TICKETS: list[Ticket] = _build_tickets()

# route_id -> Route, for O(1) lookups; every game.py access goes through this rather
# than scanning ROUTES.
ROUTES_BY_ID: dict[int, Route] = {route.route_id: route for route in ROUTES}
TICKETS_BY_ID: dict[int, Ticket] = {ticket.ticket_id: ticket for ticket in TICKETS}
