# KL-Doom

Doom, set in Kuala Lumpur. Level 1 is built from real OpenStreetMap data.
Plays in the browser; the server only hosts static files.

## Status

- [x] Step 1: original shareware Doom (E1M1) running in the browser from a WebAssembly build
- [x] Step 2: OpenStreetMap snapshot of KLCC (`data/osm/klcc.osm`, `scripts/fetch-osm.sh`)
- [ ] Step 3: map generator -> `kl1.wad`
- [ ] Step 4: landing page
- [ ] Step 5: deploy (nginx/Caddy on an Ubuntu droplet)

## Build and run

```
scripts/fetch-iwad.sh        # shareware doom1.wad -> data/ (uses apt)
scripts/build.sh             # Emscripten + engine -> dist/
python3 -m http.server -d dist 8000
```

Open http://localhost:8000/. Serve `.wasm` as `application/wasm` in production.

## Layout

- `engine/` - [cloudflare/doom-wasm](https://github.com/cloudflare/doom-wasm) @ `65e0d3a` (Chocolate Doom for WebAssembly, GPL-2.0), with the patches below
- `web/` - the page that loads the engine
- `scripts/` - build and data scripts
- `data/` - game data (WADs are git-ignored)

## Patches to the engine

1. `configure.ac`: `EXTRA_EXPORTED_RUNTIME_METHODS` -> `EXPORTED_RUNTIME_METHODS` (renamed in current Emscripten).
2. `configure.ac`: `SAFE_HEAP` and `STACK_OVERFLOW_CHECK` off (debug options that abort at startup and slow the game); `STACK_SIZE=5MB`; `TOTAL_MEMORY` -> `INITIAL_MEMORY`.
3. `src/doomtype.h`: always use the 4-byte enum `boolean` in C. Current Emscripten headers include `<stdbool.h>` before it in some files, which made `boolean` 1 byte in `g_game.c` and 4 bytes elsewhere. Struct layouts then disagreed between files and game state was overwritten (e.g. `deathmatch` set to garbage, no player spawned).

## Credits

Map data: (c) OpenStreetMap contributors, https://www.openstreetmap.org/copyright
