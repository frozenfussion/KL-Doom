#!/usr/bin/env bash
# Publish the built site (dist/) to the directory Caddy serves from.
#
#   scripts/deploy.sh
#
# Caddy runs as the "caddy" user and cannot read /home, so dist/ is copied to
# /var/www/kldoom. Safe to run repeatedly: rsync makes the target an exact
# mirror of dist/ (removing files that no longer exist there).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/dist"
DEST="${DEST:-/var/www/kldoom}"

if [ ! -f "$SRC/index.html" ]; then
  echo "error: $SRC/index.html not found - run scripts/build.sh first" >&2
  exit 1
fi

SUDO=""
[ "$(id -u)" -eq 0 ] || SUDO="sudo"

$SUDO install -d -m 755 "$DEST"
# World-readable files/dirs so the caddy user can serve them, regardless of
# the permissions in dist/.
$SUDO rsync -rt --delete --chmod=D755,F644 "$SRC"/ "$DEST"/

echo "Deployed $SRC -> $DEST"
