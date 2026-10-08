#!/usr/bin/env bash
# Download an OpenStreetMap snapshot (OSM XML) for a bounding box into data/osm/.
#
#   scripts/fetch-osm.sh [name] [west south east north]
#
# Default: the KLCC area (Petronas Twin Towers, KLCC Park, Suria KLCC), ~800 m square.
# Uses the official OSM API (limit: 0.25 square degrees per request) - fine for
# one small area; do not loop this over many areas.
# Data (c) OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${1:-klcc}"
WEST="${2:-101.7080}"
SOUTH="${3:-3.1543}"
EAST="${4:-101.7152}"
NORTH="${5:-3.1615}"
OUT="$ROOT/data/osm/$NAME.osm"

mkdir -p "$ROOT/data/osm"
curl -fsS -m 120 \
  -H "User-Agent: KL-Doom/0.1 (+https://github.com/frozenfussion/KL-Doom)" \
  "https://api.openstreetmap.org/api/0.6/map?bbox=$WEST,$SOUTH,$EAST,$NORTH" \
  -o "$OUT"

ls -l "$OUT"
