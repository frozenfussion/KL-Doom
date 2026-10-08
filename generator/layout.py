"""Turn OSM features into a partition of the map area into typed regions.

Everything here works in Doom map units (see U) on an integer grid. The result
is a list of (key, polygon) "cells" that tile the whole map area with no gaps or
overlaps, plus the chosen start and exit positions.

Region keys:
    ('wall',)              solid band around the playable area
    ('filler',)            solid leftovers (areas the player cannot reach)
    ('bldg', floor, tex)   building: raised floor at `floor` units, facade `tex`
    ('road',) ('ground',) ('park',) ('path',) ('water',) ('exit',)   walkable
"""
import math

import shapely
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon, box
from shapely.ops import nearest_points

from osm import number

GRID = 1.0          # all geometry is snapped to whole map units
U = 32              # map units per metre, horizontally (player is 56 units = 1.75 m)
V = 15              # map units per metre, vertically (squashed so towers stay in range)
HALF = 10600        # half-size of the playable square, in map units
WALL = 400          # thickness of the solid band around it
MAX_FLOOR = 7000    # tallest building floor (ceilings are at 8192)
MIN_FLOOR = 160     # shortest building (more than the 24-unit step limit)
OPEN_R = 20         # passages narrower than 2*OPEN_R are filled in
PAD_R = 128         # radius of the exit pad

ROAD_WIDTH = {          # metres
    "motorway": 16, "motorway_link": 9, "trunk": 14, "trunk_link": 8,
    "primary": 12, "primary_link": 8, "secondary": 10, "secondary_link": 7,
    "tertiary": 9, "tertiary_link": 6, "residential": 7, "unclassified": 7,
    "living_street": 6, "service": 4.5, "busway": 6, "road": 7,
}
PATH_TYPES = {"footway", "path", "pedestrian", "cycleway", "steps", "track"}
PARK_LEISURE = {"park", "garden", "playground", "nature_reserve"}
PARK_LANDUSE = {"grass", "recreation_ground", "village_green", "forest", "meadow", "flowerbed"}
PARK_NATURAL = {"wood", "scrub", "grassland"}
SKIP_BUILDING = {"no", "roof", "carport", "pavilion", "canopy"}

# Wall textures for facades. All are 128 units tall, so they tile cleanly up a tower.
TOWER = ["SHAWN2"]                                       # steel and glass
HIGH = ["STARGR1", "COMPTILE", "GRAY5", "STARG3"]
MID = ["STARTAN1", "STARTAN3", "STARG1", "GRAY4", "STARGR1"]
LOW = ["STARTAN2", "STONE3", "STARG1", "BROWN96"]
MALL = ["STONE", "GRAY7"]                                # wide, low, big-footprint buildings


# --- geometry helpers ---------------------------------------------------------
def parts(g):
    """The polygons inside any geometry."""
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, (MultiPolygon, GeometryCollection)):
        out = []
        for sub in g.geoms:
            out += parts(sub)
        return out
    return []


def only_polygons(g):
    """Drop stray lines and points that overlay operations can leave behind."""
    ps = parts(g)
    if not ps:
        return Polygon()
    return ps[0] if len(ps) == 1 else MultiPolygon(ps)


def snap(g):
    return only_polygons(shapely.set_precision(shapely.make_valid(g), GRID))


def inter(a, b):
    return only_polygons(shapely.intersection(a, b, grid_size=GRID))


def diff(a, b):
    return only_polygons(shapely.difference(a, b, grid_size=GRID))


def union(geoms):
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    return only_polygons(shapely.union_all(geoms, grid_size=GRID)) if geoms else Polygon()


def opening(g, r):
    return g.buffer(-r, join_style="mitre").buffer(r, join_style="mitre")


# --- feature extraction ---------------------------------------------------------
def _underground(tags):
    if tags.get("tunnel") in ("yes", "building_passage", "culvert") or tags.get("covered") == "yes":
        return True
    layer = number(tags.get("layer"))
    return tags.get("layer", "").startswith("-") and layer is not None and layer > 0


def quantise(h):
    """Round building heights (metres) so neighbouring parts merge into fewer steps."""
    if h <= 12:
        return 12
    for limit in (20, 30, 45, 70, 110):
        if h <= limit:
            return limit
    return int(h / 20 + 0.5) * 20


def facade(h_m, area_m2, seed):
    if h_m >= 150:
        pool = TOWER
    elif area_m2 > 12000 and h_m < 60:
        pool = MALL
    elif h_m >= 60:
        pool = HIGH
    elif h_m >= 25:
        pool = MID
    else:
        pool = LOW
    return pool[seed % len(pool)]


def buildings(osm):
    """[(height_m, polygon)] - parts that float above the ground are ignored."""
    out = []
    for tags, poly in osm.areas():
        if "building" not in tags and "building:part" not in tags:
            continue
        if tags.get("building") in SKIP_BUILDING or _underground(tags):
            continue
        if number(tags.get("min_height")) or number(tags.get("building:min_level")):
            continue
        h = number(tags.get("height"))
        if h is None and number(tags.get("building:levels")):
            h = number(tags.get("building:levels")) * 3.5
        if h is None:
            small = tags.get("building") in ("garage", "garages", "shed", "kiosk", "hut", "service")
            area = poly.area / (U * U)
            h = 6 if small else (25 if area > 5000 else 15)
        out.append((h, snap(poly)))
    return out


def walkable_layers(osm):
    """Polygons for parks, water, roads and park paths."""
    parks, water, roads, paths = [], [], [], []
    for tags, poly in osm.areas():
        if "building" in tags or "building:part" in tags:
            continue
        if (tags.get("leisure") in PARK_LEISURE or tags.get("landuse") in PARK_LANDUSE
                or tags.get("natural") in PARK_NATURAL):
            parks.append(poly)
        if (tags.get("natural") == "water" or tags.get("waterway") == "riverbank"
                or tags.get("leisure") == "swimming_pool" or tags.get("amenity") == "fountain"):
            water.append(poly)
        if tags.get("highway") in PATH_TYPES | {"pedestrian"} and tags.get("area") == "yes":
            paths.append(poly)
    for tags, line in osm.lines():
        hw = tags.get("highway")
        if hw is None or _underground(tags) or tags.get("indoor"):
            continue
        if hw in ROAD_WIDTH:
            roads.append(line.buffer(ROAD_WIDTH[hw] * U / 2, cap_style="flat"))
        elif hw in PATH_TYPES and tags.get("area") != "yes" and tags.get("footway") != "crossing":
            paths.append(line.buffer((3 if hw == "steps" else 2.5) * U / 2, cap_style="flat"))
    return union(map(snap, parks)), union(map(snap, water)), union(map(snap, roads)), union(map(snap, paths))


# --- the partition --------------------------------------------------------------
def build(osm, focus_minheight=300):
    domain = box(-HALF - WALL, -HALF - WALL, HALF + WALL, HALF + WALL)
    playfield = box(-HALF, -HALF, HALF, HALF)

    blds = buildings(osm)
    parks, water, roads, paths = walkable_layers(osm)

    # Where the landmark is: the tallest parts, e.g. the Petronas Twin Towers.
    tall = [p for h, p in blds if h >= focus_minheight]
    focus = union(tall).centroid if tall else Point(0, 0)

    remaining = domain
    cells = []

    def paint(key, geom):
        nonlocal remaining
        if geom is None or geom.is_empty:
            return
        g = inter(snap(geom), remaining)
        if g.is_empty:
            return
        cells.append((key, g))
        remaining = diff(remaining, g)

    paint(("wall",), diff(domain, playfield))

    # Buildings: tallest first, so that tall parts win where footprints overlap.
    for h, poly in sorted(blds, key=lambda b: -b[0]):
        if poly.area < 2000:
            continue
        qh = quantise(h)
        floor = max(MIN_FLOOR, min(MAX_FLOOR, int(qh * V)))
        c = poly.centroid
        tex = facade(qh, poly.area / (U * U), int(abs(c.x) // 40 + abs(c.y) // 40))
        paint(("bldg", floor, tex), poly)

    # Everything else, in priority order. Thin slivers are removed from each layer.
    paint(("water",), opening(water, 12))
    park_paths = inter(paths, parks.buffer(160)) if not parks.is_empty else Polygon()
    paint(("road",), opening(roads, 12))
    paint(("path",), opening(park_paths, 12))
    paint(("park",), opening(parks, 12))
    paint(("ground",), remaining)

    cells = _merge(cells)
    cells = _tidy(cells, domain)
    return _finish(cells, domain, focus, parks)


def _merge(cells):
    by_key = {}
    for key, g in cells:
        by_key.setdefault(key, []).append(g)
    return [(k, union(gs)) for k, gs in by_key.items()]


def _tidy(cells, domain):
    """Move thin slivers of every region into 'ground' so no cell is too narrow."""
    extra, out = [], []
    for key, g in cells:
        if key in (("ground",), ("wall",)):
            out.append((key, g))
            continue
        kept = inter(opening(g, 10), g)
        extra.append(diff(g, kept))
        out.append((key, kept))
    result = []
    for key, g in out:
        if key == ("ground",):
            g = union([g] + extra)
        result.append((key, g))
    return [(k, g) for k, g in result if not g.is_empty]


def _finish(cells, domain, focus, parks):
    walk_keys = {("road",), ("ground",), ("park",), ("path",), ("water",)}
    walk = union([g for k, g in cells if k in walk_keys])

    # Fill in narrow passages the player could not fit through, then keep only the
    # main connected area (everything else becomes solid).
    opened = inter(opening(walk, OPEN_R), walk)
    comps = parts(opened)
    main = max(comps, key=lambda p: p.area)

    # Start: far end of the park from the landmark; exit: nearest open spot to it.
    park_area = inter(main, parks)
    inset = box(-HALF + 1500, -HALF + 1500, HALF - 1500, HALF - 1500)       # not right at the edge of the map
    start_zone = inter(park_area.buffer(-110, join_style="mitre"), inset) if not park_area.is_empty else Polygon()
    if start_zone.is_empty:
        start_zone = inter(main.buffer(-110, join_style="mitre"), inset)
    cands = [Point(c) for p in parts(start_zone) for c in p.exterior.coords]
    start = max(cands, key=lambda p: p.distance(focus))
    exit_zone = main.buffer(-PAD_R - 90, join_style="mitre")
    exit_pt = nearest_points(exit_zone, focus)[0]
    pad = snap(Point(exit_pt.x, exit_pt.y).buffer(PAD_R, quad_segs=4))

    out, filler = [], []
    for key, g in cells:
        if key in walk_keys:
            kept = inter(g, main)
            filler.append(diff(g, main))
            g = kept
        if key[0] in ("road", "ground", "park", "path", "water"):
            g = diff(g, pad)
        if not g.is_empty:
            out.append((key, g))
    out.append((("exit",), pad))
    filler = union(filler)
    if not filler.is_empty:
        out.append((("filler",), diff(filler, pad)))

    # Sanity: the cells should tile the domain. Snapping to the grid can leave
    # sub-unit slivers; those become faces later and get assigned to a neighbour.
    total = sum(g.area for _, g in out)
    if abs(total - domain.area) > domain.area * 1e-3:
        raise SystemExit("cells do not tile the map (%.0f vs %.0f)" % (total, domain.area))

    return {
        "cells": out,
        "start": (start.x, start.y),
        "exit": (exit_pt.x, exit_pt.y),
        "focus": (focus.x, focus.y),
        "domain": domain,
        "walkable": union([g for k, g in out if k in walk_keys | {("exit",)}]),
    }
