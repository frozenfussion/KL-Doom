#!/usr/bin/env python3
"""Generate kl1.wad: Level 1 of KL-Doom, built from an OpenStreetMap snapshot of KLCC.

    python3 generator/make_level.py                       # -> data/kl1.wad
    python3 generator/make_level.py --preview map.png     # also draw a top-down map

Needs: shapely, numpy, Pillow (preview only), and the `zdbsp` node builder
(apt install zdbsp). The shareware doom1.wad must be in data/ (scripts/fetch-iwad.sh).
"""
import argparse
import math
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile

import shapely
from shapely.geometry import LineString, Point
from shapely.geometry.polygon import orient
from shapely.ops import nearest_points, polygonize
from shapely.strtree import STRtree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import faces            # noqa: E402
import graphics         # noqa: E402
import layout as L      # noqa: E402
import osm as O         # noqa: E402
import story            # noqa: E402
from wadio import IwadResources, read_wad, write_wad   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAT0, LON0 = 3.1579, 101.7116       # map origin: the Petronas Twin Towers
CEIL = 8192                         # every sector's ceiling (sky); buildings are raised floors
SOLID = {"bldg", "wall", "filler"}
MAP_NAME = "E1M1"
MAP_TITLE = "E1M1: KLCC and the Twin Towers"
ORIGINAL_TITLE = "E1M1: Hangar"

# floor, floor flat, light level, sector special
SECTORS = {
    "road":   (0,   "FLOOR6_2", 192, 0),    # dark gritty asphalt
    "ground": (8,   "FLOOR0_3", 208, 0),    # grey paving (8 units up: a kerb)
    "park":   (8,   "FLOOR7_2", 176, 0),    # mossy green grass
    "path":   (8,   "FLOOR5_3", 200, 0),    # tan paving
    "water":  (-8,  "FLAT14",   176, 0),    # blue water, shallow
    "exit":   (16,  "FLOOR1_7", 255, 8),    # glowing red pad
}
SOLID_FLAT = "FLAT1"
WALL_FLOOR, FILLER_FLOOR = 4000, 900
WALL_TEX, FILLER_TEX = "STONE2", "STONE3"

# Thing numbers
PLAYER = 1
ZOMBIE, SHOTGUNNER, IMP, DEMON, BARON = 3004, 9, 3001, 3002, 3003
SHOTGUN, CHAINGUN, LAUNCHER = 2001, 2002, 2003
CLIP, BULLETBOX, SHELLS, SHELLBOX, ROCKETBOX = 2007, 2048, 2008, 2049, 2046
STIM, MEDIKIT, HEALTH_BONUS, ARMOR_BONUS = 2011, 2012, 2014, 2015
GREEN_ARMOR, BLUE_ARMOR, SOULSPHERE, BACKPACK, MAP_ITEM = 2018, 2019, 2013, 8, 2026
BARREL, LAMP, COLUMN, TORCH = 2035, 2028, 48, 46


# --- partition -> Doom map ----------------------------------------------------
def info(key):
    k = key[0]
    if k in SECTORS:
        return SECTORS[k]
    if k == "bldg":
        return (key[1], SOLID_FLAT, 255, 0)
    return (WALL_FLOOR if k == "wall" else FILLER_FLOOR, SOLID_FLAT, 255, 0)


def facade(key):
    return key[2] if key[0] == "bldg" else (WALL_TEX if key[0] == "wall" else FILLER_TEX)


class MapBuilder:
    def __init__(self, result, iwad):
        self.iwad = iwad
        self.vertices, self.vindex = [], {}
        self.sectors, self.linedefs, self.sidedefs = [], [], []
        self.faces = self._faces(result["cells"])
        self._build()

    # Face = one polygon of the final partition; each becomes a sector.
    def _faces(self, cells):
        rings = []
        for _, g in cells:
            for p in L.parts(g):
                rings.append(LineString(p.exterior.coords))
                rings += [LineString(r.coords) for r in p.interiors]
        noded = shapely.union_all(rings, grid_size=L.GRID)
        faces = [orient(f, 1.0) for f in polygonize(noded)]

        polys, keys = [], []
        for key, g in cells:
            for p in L.parts(g):
                polys.append(p)
                keys.append(key)
        tree = STRtree(polys)
        out = []
        for f in faces:
            pt = f.representative_point()
            hit = tree.query(pt, predicate="within")
            idx = int(hit[0]) if len(hit) else int(tree.nearest(pt))
            out.append((keys[idx], f))
        return out

    def _vertex(self, pt):
        key = (int(round(pt[0])), int(round(pt[1])))
        if key not in self.vindex:
            self.vindex[key] = len(self.vertices)
            self.vertices.append(key)
        return self.vindex[key]

    def _build(self):
        tex = self.iwad.textures
        for key, _ in self.faces:
            floor, flat, light, special = info(key)
            self.iwad.check_flat(flat)
            self.sectors.append({"key": key, "floor": floor, "ceil": CEIL, "flat": flat,
                                 "light": light, "special": special})

        # Directed edges: the face lies on the LEFT of a -> b (CCW exteriors, CW holes).
        edges = {}
        for fid, (_, f) in enumerate(self.faces):
            for ring in [f.exterior] + list(f.interiors):
                pts = [(int(round(x)), int(round(y))) for x, y in ring.coords]
                for a, b in zip(pts, pts[1:]):
                    if a != b:
                        edges[(a, b)] = fid
        self.unmatched = 0
        done = set()
        for (a, b), fid in edges.items():
            if (a, b) in done:
                continue
            twin = edges.get((b, a))
            if twin is None:
                # Outer boundary: flip so the face is on the right (the front side).
                self._line(b, a, fid, None)
            else:
                done.add((b, a))
                self._line(a, b, twin, fid)     # right side = twin face (front), left = this face
            done.add((a, b))

    def _side(self, sec, other):
        """A sidedef for sector `sec`, facing `other` (None for a one-sided wall)."""
        s = self.sectors[sec]
        lower = upper = mid = "-"
        yoff = 0
        if other is None:
            mid = facade(s["key"])
        else:
            o = self.sectors[other]
            if s["floor"] < o["floor"]:
                if o["key"][0] in SOLID:
                    lower = facade(o["key"])
                    height = self.iwad.check_texture(lower) and self.iwad.textures[lower][1]
                    yoff = (-(o["floor"] - s["floor"])) % height     # bottom of the texture at the foot of the wall
                else:
                    lower = "STEP1" if o["floor"] - s["floor"] <= 8 else "STEP4"
        for t in (lower, upper, mid):
            if t != "-":
                self.iwad.check_texture(t)
        self.sidedefs.append((0, yoff, upper, lower, mid, sec))
        return len(self.sidedefs) - 1

    def _line(self, a, b, front, back):
        flags, special = 0, 0
        if back is None:
            flags = 0x01
        else:
            flags = 0x04
            if self.sectors[front]["key"][0] in SOLID or self.sectors[back]["key"][0] in SOLID:
                flags |= 0x01                     # nothing walks into a building
            if "exit" in (self.sectors[front]["key"][0], self.sectors[back]["key"][0]):
                special = 52                      # W1: walk over to end the level
        r = self._side(front, back)
        left = self._side(back, front) if back is not None else -1
        self.linedefs.append((self._vertex(a), self._vertex(b), flags, special, 0, r, left))


# --- gameplay -----------------------------------------------------------------
class Placer:
    """Chooses where monsters, pickups and decorations go, deterministically."""

    def __init__(self, result, seed, monsters=64):
        self.monster_count = monsters
        self.rng = random.Random(seed)
        self.start = Point(result["start"])
        self.exit = Point(result["exit"])
        self.walk = result["walkable"]
        self.cells = {}
        for key, g in result["cells"]:
            self.cells.setdefault(key[0], []).append(g)
        self.start_angle = result.get("start_angle")
        self.span = self.start.distance(self.exit)
        self.route = LineString([self.start, self.exit])
        self.things = []
        self.taken = []                       # (point, radius)
        # candidate points, kept clear of walls
        inner = self.walk.buffer(-72, join_style="mitre")
        minx, miny, maxx, maxy = inner.bounds
        shapely.prepare(inner)
        self.open_ground = self.walk.buffer(-100, join_style="mitre")      # wide enough that a lamp never blocks a route
        shapely.prepare(self.open_ground)
        self.points = []
        while len(self.points) < 6000:
            p = Point(self.rng.uniform(minx, maxx), self.rng.uniform(miny, maxy))
            if inner.contains(p):
                self.points.append(p)

    def progress(self, p):
        return max(0.0, min(1.0, self.start.distance(p) / self.span))

    def free(self, p, radius):
        return all(p.distance(q) >= r + radius for q, r in self.taken)

    def add(self, p, type_, angle=0, options=7, radius=40):
        self.things.append((int(round(p.x)), int(round(p.y)), angle, type_, options))
        self.taken.append((p, radius))

    def pick(self, near_t=None, width=0.08, radius=60, corridor=None, avoid_exit=300, avoid_start=0, zone=None):
        """A random free candidate point, optionally near a given progress value or route."""
        for _ in range(4000):
            p = self.rng.choice(self.points)
            if near_t is not None and abs(self.progress(p) - near_t) > width:
                continue
            if corridor is not None and self.rng.random() > math.exp(-(p.distance(self.route) / corridor) ** 2):
                continue
            if p.distance(self.exit) < avoid_exit or p.distance(self.start) < avoid_start:
                continue
            if zone is not None and not zone.contains(p):
                continue
            if self.free(p, radius):
                return p
        return None

    def run(self):
        sx, sy = self.start.x, self.start.y
        angle = int(round(math.degrees(math.atan2(self.exit.y - sy, self.exit.x - sx)) / 45.0)) * 45 % 360
        if self.start_angle is not None:
            angle = self.start_angle
        self.things.append((int(sx), int(sy), angle, PLAYER, 7))
        self.taken.append((self.start, 64))
        for i in (2, 3, 4):                   # unused coop starts keep the engine happy
            self.things.append((int(sx) + 48 * i, int(sy), angle, i, 7))

        # Landmarks around the exit pad.
        for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            p = Point(self.exit.x + dx * 230, self.exit.y + dy * 230)
            if self.open_ground.contains(p):
                self.add(p, TORCH, radius=24)
        if self.monster_count:
            self._guard_exit()

        # Start: orientation help and a first weapon.
        self._near_start(MAP_ITEM, 140)
        self._near_start(SHOTGUN, 260)
        self._near_start(CLIP, 200)
        self._near_start(STIM, 320)

        # Weapons and big pickups along the way, by progress.
        for t, kind in ((0.30, CHAINGUN), (0.34, BULLETBOX), (0.45, BACKPACK), (0.48, MEDIKIT),
                        (0.58, GREEN_ARMOR), (0.62, LAUNCHER), (0.66, ROCKETBOX), (0.74, SHELLBOX),
                        (0.80, MEDIKIT), (0.88, BLUE_ARMOR), (0.93, SOULSPHERE)):
            self._item(kind, t)
        for i in range(24):
            self._item(HEALTH_BONUS, (i + 0.5) / 24)
            if i % 2 == 0:
                self._item(ARMOR_BONUS, (i + 1) / 25)
            if i % 3 == 0:
                self._item(STIM, (i + 1.5) / 25)
            if i % 3 == 1:
                self._item(self.rng.choice((CLIP, SHELLS)), (i + 0.5) / 24)

        self._monsters(self.monster_count)
        self._decorations()
        return self.things

    def _near_start(self, kind, dist):
        for _ in range(500):
            a = self.rng.uniform(0, 2 * math.pi)
            p = Point(self.start.x + dist * math.cos(a), self.start.y + dist * math.sin(a))
            if self.walk.buffer(-60).contains(p) and self.free(p, 30):
                self.add(p, kind, radius=30)
                return

    def _item(self, kind, t):
        """Place a pickup near progress t, relaxing the constraints until it fits."""
        t = min(max(t, 0.03), 0.95)
        for width, corridor in ((0.06, 500), (0.12, 900), (0.2, 1500), (0.3, None)):
            p = self.pick(near_t=t, width=width, radius=40, corridor=corridor, avoid_start=200)
            if p is not None:
                self.add(p, kind, radius=30)
                return

    def _guard_exit(self):
        for dist, kind in ((700, BARON), (800, BARON), (500, IMP), (600, IMP), (650, DEMON), (550, SHOTGUNNER)):
            for _ in range(400):
                a = self.rng.uniform(0, 2 * math.pi)
                p = Point(self.exit.x + dist * math.cos(a), self.exit.y + dist * math.sin(a))
                if self.walk.buffer(-80).contains(p) and self.free(p, 70):
                    ang = int(round(math.degrees(math.atan2(self.start.y - p.y, self.start.x - p.x)) / 45.0)) * 45 % 360
                    self.add(p, kind, angle=ang, options=7, radius=70)
                    break

    def _monsters(self, count):
        for i in range(count):
            p = self.pick(radius=110, corridor=600, avoid_start=700, avoid_exit=450)
            if p is None:
                continue
            t, r = self.progress(p), self.rng.random()
            if t < 0.3:
                kind = ZOMBIE if r < 0.7 else SHOTGUNNER
            elif t < 0.7:
                kind = IMP if r < 0.4 else ZOMBIE if r < 0.65 else SHOTGUNNER if r < 0.87 else DEMON
            else:
                kind = IMP if r < 0.4 else DEMON if r < 0.65 else SHOTGUNNER if r < 0.9 else BARON
            roll = self.rng.random()
            options = 7 if roll < 0.6 else 6 if roll < 0.85 else 4      # more monsters on harder skills
            ang = self.rng.choice(range(0, 360, 45))
            self.add(p, kind, angle=ang, options=options, radius=70)
            if self.rng.random() < 0.3:
                q = self.pick(near_t=t, width=0.02, radius=40, avoid_exit=450)
                if q is not None and q.distance(p) < 500:
                    self.add(q, BARREL, radius=24)
        for i in range(14):
            p = self.pick(radius=60, corridor=800)
            if p is not None:
                self.add(p, BARREL, radius=24)

    def _decorations(self):
        """Street lamps along the kerbs."""
        road = L.union(self.cells.get("road", []))
        ground = L.union(self.cells.get("ground", [])).buffer(-40, join_style="mitre")
        if road.is_empty or ground.is_empty:
            return
        shapely.prepare(ground)
        count = 0
        for line in (road.boundary.geoms if hasattr(road.boundary, "geoms") else [road.boundary]):
            if line.length < 400:
                continue
            d = self.rng.uniform(0, 600)
            while d < line.length and count < 140:
                p = line.interpolate(d)
                d += 1100
                for nx, ny in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    q = Point(p.x + nx * 70, p.y + ny * 70)
                    if (ground.contains(q) and q.distance(self.exit) > 450 and q.distance(self.start) > 300
                            and self.open_ground.contains(q) and self.free(q, 24)):
                        self.add(q, LAMP, radius=24)
                        count += 1
                        break


# --- output -------------------------------------------------------------------
def name8(s):
    return s.encode("latin1")[:8].ljust(8, b"\0")


def lumps(mb, things):
    v = b"".join(struct.pack("<hh", x, y) for x, y in mb.vertices)
    ld = b"".join(struct.pack("<hhhhhhh", a, b, fl, sp, tag, r, l) for a, b, fl, sp, tag, r, l in mb.linedefs)
    sd = b"".join(struct.pack("<hh8s8s8sh", xo, yo, name8(u), name8(lo), name8(m), s)
                  for xo, yo, u, lo, m, s in mb.sidedefs)
    sc = b"".join(struct.pack("<hh8s8shhh", s["floor"], s["ceil"], name8(s["flat"]), name8("F_SKY1"),
                              s["light"], s["special"], 0) for s in mb.sectors)
    th = b"".join(struct.pack("<hhhhh", *t) for t in things)
    return [(MAP_NAME, b""), ("THINGS", th), ("LINEDEFS", ld), ("SIDEDEFS", sd), ("VERTEXES", v),
            ("SEGS", b""), ("SSECTORS", b""), ("NODES", b""), ("SECTORS", sc), ("REJECT", b""), ("BLOCKMAP", b"")]


ORIGINAL_E1TEXT = (
    "Once you beat the big badasses and\n"
    "clean out the moon base you're supposed\n"
    "to win, aren't you? Aren't you? Where's\n"
    "your fat reward and ticket home? What\n"
    "the hell is this? It's not supposed to\n"
    "end this way!\n"
    "\n"
    "It stinks like rotten meat, but looks\n"
    "like the lost Deimos base.  Looks like\n"
    "you're stuck on The Shores of Hell.\n"
    "The only way out is through.\n"
    "\n"
    "To continue the DOOM experience, play\n"
    "The Shores of Hell and its amazing\n"
    "sequel, Inferno!\n"
)


def dehacked():
    """Rename the level (automap, HUD) and replace the ending text."""
    text = "Patch File for DeHackEd v3.0\nDoom version = 19\nPatch format = 6\n"
    for old, new in ((ORIGINAL_TITLE, MAP_TITLE), (ORIGINAL_E1TEXT, story.ending_text())):
        text += "\nText %d %d\n%s%s\n" % (len(old), len(new), old, new)
    return text.encode("latin1")


def build_nodes(raw_wad, out_wad):
    tool = shutil.which("zdbsp")
    if tool is None:
        raise SystemExit("zdbsp not found - install it with: sudo apt install zdbsp")
    subprocess.run([tool, "--no-timing", "--zero-reject", "--empty-blockmap", "-o", out_wad, raw_wad],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def menu_graphics(iwad_path):
    """Lumps that replace or add to the IWAD's: menu logo, title screen and the intro story."""
    wad = graphics.Wad(iwad_path)
    fonts = {chr(c): wad.patch("STCFN%03d" % c)[0] for c in range(33, 96) if "STCFN%03d" % c in wad.ents}
    story.check(fonts)
    grid, _ = graphics.make_kl_doom(wad)
    logo = graphics.encode_patch(grid, left=26, top=0)       # the menu draws it at x=94; left=26 centres it
    title = graphics.encode_patch(graphics.build_titlepic(wad, wad.image(grid)))
    return [("M_DOOM", logo), ("TITLEPIC", title), ("KLSTORY", story.intro_lump())] + faces.face_lumps(wad)


def preview(result, path):
    from PIL import Image, ImageDraw
    size = 1400
    half = L.HALF + L.WALL
    s = size / (2 * half)
    im = Image.new("RGB", (size, size), (0, 0, 0))
    d = ImageDraw.Draw(im)
    colours = {"wall": (20, 20, 20), "filler": (70, 40, 40), "road": (70, 70, 78), "ground": (150, 150, 155),
               "park": (60, 120, 60), "path": (190, 170, 120), "water": (50, 90, 190), "exit": (255, 60, 60)}

    def px(x, y):
        return ((x + half) * s, size - (y + half) * s)

    polys = []
    for key, g in result["cells"]:
        for p in L.parts(g):
            polys.append((p.area, key, p))
    for _, key, p in sorted(polys, key=lambda t: -t[0]):
        if key[0] == "bldg":
            f = key[1]
            c = (min(255, 100 + f // 40), 80, 80 + min(150, f // 40))
        else:
            c = colours[key[0]]
        d.polygon([px(*q) for q in p.exterior.coords], fill=c, outline=(0, 0, 0))
    for name, c in (("start", (255, 255, 0)), ("exit", (255, 255, 255))):
        x, y = px(*result[name])
        d.ellipse([x - 9, y - 9, x + 9, y + 9], outline=c, width=3)
    im.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--osm", default=os.path.join(ROOT, "data/osm/klcc.osm"))
    ap.add_argument("--iwad", default=os.path.join(ROOT, "data/doom1.wad"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data/kl1.wad"))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--monsters", type=int, default=64, help="number of roaming monsters (0 for a quiet map)")
    ap.add_argument("--preview", help="write a top-down PNG of the generated map")
    ap.add_argument("--start", help="debug: override the player start as X,Y[,ANGLE] (map units, degrees)")
    args = ap.parse_args()

    iwad = IwadResources(args.iwad)
    project = O.Projector(LAT0, LON0, L.U)
    result = L.build(O.Osm(args.osm, project))
    if args.start:
        v = [float(n) for n in args.start.split(",")]
        inner = result["walkable"].buffer(-80, join_style="mitre")
        near = nearest_points(inner, Point(v[0], v[1]))[0]       # keep the debug start on open ground
        result["start"] = (near.x, near.y)
        if len(v) > 2:
            result["start_angle"] = int(v[2])
    if args.preview:
        preview(result, args.preview)

    mb = MapBuilder(result, iwad)
    things = Placer(result, args.seed, args.monsters).run()

    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "raw.wad")
        built = os.path.join(tmp, "built.wad")
        write_wad(raw, lumps(mb, things))
        build_nodes(raw, built)
        _, out = read_wad(built)
    out.append(("DEHACKED", dehacked()))
    out += menu_graphics(args.iwad)
    write_wad(args.out, out)

    counts = {n: len(b) for n, b in out}
    print("vertices %d  linedefs %d  sidedefs %d  sectors %d  things %d" %
          (len(mb.vertices), len(mb.linedefs), len(mb.sidedefs), len(mb.sectors), len(things)))
    print("segs %d  subsectors %d  nodes %d  -> %s (%d bytes)" %
          (counts["SEGS"] // 12, counts["SSECTORS"] // 4, counts["NODES"] // 28, args.out, os.path.getsize(args.out)))


if __name__ == "__main__":
    main()
