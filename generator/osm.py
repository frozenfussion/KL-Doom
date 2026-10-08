"""Read an OSM XML file and turn it into shapely geometry in Doom map units."""
import math
import re
import xml.etree.ElementTree as ET

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union


def number(text):
    """Leading number of an OSM value such as '30', '12.5 m' - or None."""
    if not text:
        return None
    m = re.match(r"\s*(\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else None


class Projector:
    """Local equirectangular projection around (lat0, lon0); output in map units."""

    def __init__(self, lat0, lon0, units_per_metre):
        self.lat0, self.lon0, self.k = lat0, lon0, units_per_metre
        self.mx = 111320.0 * math.cos(math.radians(lat0))
        self.my = 110574.0

    def __call__(self, lat, lon):
        return ((lon - self.lon0) * self.mx * self.k, (lat - self.lat0) * self.my * self.k)


class Osm:
    def __init__(self, path, project):
        self.project = project
        root = ET.parse(path).getroot()
        self.nodes = {}
        self.node_tags = {}
        for n in root.findall("node"):
            self.nodes[n.get("id")] = (float(n.get("lat")), float(n.get("lon")))
            tags = {t.get("k"): t.get("v") for t in n.findall("tag")}
            if tags:
                self.node_tags[n.get("id")] = tags
        self.ways = {}
        for w in root.findall("way"):
            self.ways[w.get("id")] = {
                "nodes": [nd.get("ref") for nd in w.findall("nd")],
                "tags": {t.get("k"): t.get("v") for t in w.findall("tag")},
            }
        self.relations = []
        for r in root.findall("relation"):
            self.relations.append({
                "id": r.get("id"),
                "tags": {t.get("k"): t.get("v") for t in r.findall("tag")},
                "members": [(m.get("type"), m.get("ref"), m.get("role")) for m in r.findall("member")],
            })

    # --- geometry helpers --------------------------------------------------
    def coords(self, way):
        return [self.project(*self.nodes[n]) for n in way["nodes"] if n in self.nodes]

    def way_polygon(self, way):
        pts = self.coords(way)
        if len(pts) < 4 or way["nodes"][0] != way["nodes"][-1]:
            return None
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        return poly if not poly.is_empty else None

    def way_line(self, way):
        pts = self.coords(way)
        return LineString(pts) if len(pts) >= 2 else None

    def relation_polygon(self, rel):
        outer, inner = [], []
        for mtype, ref, role in rel["members"]:
            if mtype != "way" or ref not in self.ways:
                continue
            line = self.way_line(self.ways[ref])
            if line is not None:
                (inner if role == "inner" else outer).append(line)
        shells = unary_union(list(polygonize(unary_union(outer)))) if outer else None
        if shells is None or shells.is_empty:
            return None
        if inner:
            holes = unary_union(list(polygonize(unary_union(inner))))
            shells = shells.difference(holes)
        return shells

    # --- feature iterators ---------------------------------------------------
    def areas(self):
        """Yield (tags, polygon) for every closed way and multipolygon relation."""
        for way in self.ways.values():
            poly = self.way_polygon(way)
            if poly is not None:
                yield way["tags"], poly
        for rel in self.relations:
            if rel["tags"].get("type") == "multipolygon":
                poly = self.relation_polygon(rel)
                if poly is not None:
                    yield rel["tags"], poly

    def lines(self):
        """Yield (tags, linestring) for every way."""
        for way in self.ways.values():
            line = self.way_line(way)
            if line is not None:
                yield way["tags"], line

    def points(self):
        for nid, tags in self.node_tags.items():
            yield tags, Point(*self.project(*self.nodes[nid]))
