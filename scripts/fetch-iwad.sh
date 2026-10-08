#!/usr/bin/env bash
# Fetch the shareware doom1.wad (Doom Episode 1) into data/.
# Uses Ubuntu/Debian's doom-wad-shareware package (multiverse/non-free).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/data/doom1.wad"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK:?}"' EXIT

if [ -f "$OUT" ]; then
  echo "data/doom1.wad already present"
  exit 0
fi

mkdir -p "$ROOT/data"
cd "$WORK"
apt-get download doom-wad-shareware
dpkg-deb -x doom-wad-shareware_*.deb "$WORK/x"
cp "$WORK/x/usr/share/games/doom/doom1.wad" "$OUT"
ls -l "$OUT"
