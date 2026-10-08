#!/usr/bin/env bash
# Build the browser (WebAssembly) engine and assemble the static site in dist/.
#
#   scripts/build.sh
#
# Needs: git, python3, autoconf/automake/libtool, make, pkg-config, curl.
# Everything else (Emscripten, SDL libraries) is fetched into .toolchain/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EMSDK_VERSION="${EMSDK_VERSION:-6.0.11}"
EMSDK_DIR="${EMSDK_DIR:-$ROOT/.toolchain/emsdk}"
PORTS_DIR="$ROOT/.toolchain/ports"
export GIT_LFS_SKIP_SMUDGE=1

# --- 1. Emscripten ---------------------------------------------------------
if [ ! -d "$EMSDK_DIR" ]; then
  git clone --depth 1 https://github.com/emscripten-core/emsdk "$EMSDK_DIR"
fi
"$EMSDK_DIR/emsdk" install "$EMSDK_VERSION"
"$EMSDK_DIR/emsdk" activate "$EMSDK_VERSION"
# shellcheck disable=SC1091
source "$EMSDK_DIR/emsdk_env.sh" >/dev/null

# --- 2. SDL ports -----------------------------------------------------------
# Emscripten normally downloads these as GitHub release zips. Where GitHub
# archive downloads are blocked, clone the tags with git and pre-load
# Emscripten's ports cache instead. The names/tags below match Emscripten 6.0.11
# (see tools/ports/sdl2.py, sdl2_mixer.py, sdl2_net.py); update with the SDK.
CACHE_PORTS="$(em-config CACHE)/ports"

seed_port() { # name subdir repo tag zip-url
  local name="$1" subdir="$2" repo="$3" tag="$4" url="$5"
  local dest="$CACHE_PORTS/$name"
  if [ -f "$dest/.emscripten_url" ] && [ "$(cat "$dest/.emscripten_url")" = "$url" ]; then
    return 0
  fi
  mkdir -p "$PORTS_DIR"
  local clone="$PORTS_DIR/$name"
  [ -d "$clone" ] || git clone --depth 1 --branch "$tag" "$repo" "$clone"
  mkdir -p "$dest"
  rm -rf "${dest:?}/$subdir"
  cp -r "$clone" "$dest/$subdir"
  printf '%s\n' "$url" > "$dest/.emscripten_url"
}

seed_port sdl2       SDL-release-2.32.10      https://github.com/libsdl-org/SDL           release-2.32.10 https://github.com/libsdl-org/SDL/archive/release-2.32.10.zip
seed_port sdl2_mixer SDL_mixer-release-2.8.0  https://github.com/libsdl-org/SDL_mixer     release-2.8.0   https://github.com/libsdl-org/SDL_mixer/archive/release-2.8.0.zip
seed_port sdl2_net   SDL2_net-version_2       https://github.com/emscripten-ports/SDL2_net version_2       https://github.com/emscripten-ports/SDL2_net/archive/version_2.zip

# --- 3. Engine --------------------------------------------------------------
cd "$ROOT/engine"
./scripts/build.sh

# --- 4. Static site ---------------------------------------------------------
DIST="$ROOT/dist"
mkdir -p "$DIST"
cp src/websockets-doom.js src/websockets-doom.wasm src/default.cfg "$DIST/"
cp "$ROOT/web/index.html" "$DIST/"
if [ -f "$ROOT/data/doom1.wad" ]; then
  cp "$ROOT/data/doom1.wad" "$DIST/"
else
  echo "NOTE: data/doom1.wad not found - run scripts/fetch-iwad.sh, then re-run this script."
fi
for wad in "$ROOT"/data/*.wad; do
  [ -e "$wad" ] && [ "$(basename "$wad")" != "doom1.wad" ] && cp "$wad" "$DIST/"
done

echo "Built: $DIST  (serve it with: python3 -m http.server -d dist 8000)"
