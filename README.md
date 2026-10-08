# KL-Doom

Doom, set in Kuala Lumpur. Level 1 is built from real OpenStreetMap data.
Plays in the browser; the server only hosts static files.

## Status

- [x] Step 1: original shareware Doom (E1M1) running in the browser from a WebAssembly build
- [x] Step 2: OpenStreetMap snapshot of KLCC (`data/osm/klcc.osm`, `scripts/fetch-osm.sh`)
- [x] Step 3: map generator -> `data/kl1.wad` (`generator/make_level.py`)
- [ ] Step 4: landing page
- [ ] Step 5: deploy (nginx/Caddy on an Ubuntu droplet)

## Build and run

```
scripts/fetch-iwad.sh        # shareware doom1.wad -> data/ (uses apt)
scripts/build.sh             # Emscripten + engine -> dist/
python3 -m http.server -d dist 8000
```

Open http://localhost:8000/. Serve `.wasm` as `application/wasm` in production.

## Level 1 (KLCC)

Generated from the OSM snapshot by `generator/make_level.py` and committed as `data/kl1.wad`:
streets, kerbs, KLCC Park with its lake and paths, and every building at its OSM height
(the Twin Towers as stepped silver towers). Walk from the park to the glowing exit pad at the
foot of the towers (about 450 m). Only original Doom textures, sprites and monsters are used.

```
sudo apt install zdbsp                 # node builder
pip install -r generator/requirements.txt
python3 generator/make_level.py        # -> data/kl1.wad (add --preview map.png for a top-down picture)
```

Scale is 32 map units per metre horizontally (so the player is 1.75 m tall) and 15 per metre
vertically. Buildings are raised floors under a very high sky ceiling, so no sector is ever
"inside" a building.

## Layout

- `engine/` - [cloudflare/doom-wasm](https://github.com/cloudflare/doom-wasm) @ `65e0d3a` (Chocolate Doom for WebAssembly, GPL-2.0), with the patches below
- `generator/` - OSM -> Doom level generator (`osm.py`, `layout.py`, `make_level.py`, `wadio.py`)
- `web/` - the page that loads the engine
- `scripts/` - build and data scripts
- `data/` - game data (WADs are git-ignored)

## Patches to the engine

Build fixes (needed on current Emscripten):

1. `configure.ac`: `EXTRA_EXPORTED_RUNTIME_METHODS` -> `EXPORTED_RUNTIME_METHODS`; `SAFE_HEAP` and `STACK_OVERFLOW_CHECK` off; `STACK_SIZE=5MB`; `TOTAL_MEMORY` -> `INITIAL_MEMORY`.
2. `src/doomtype.h`: always use the 4-byte enum `boolean` in C. Current Emscripten headers include `<stdbool.h>` before it in some files, which made `boolean` 1 byte in `g_game.c` and 4 bytes elsewhere, so struct layouts disagreed and game state was overwritten (e.g. `deathmatch` set to garbage, no player spawned).

Changes for a city-sized map:

3. `src/tables.c`: `SlopeDiv` uses a 64-bit intermediate. The 32-bit original overflows for anything more than 8192 map units away, so distant walls were not drawn.
4. `src/doom/p_setup.c`, `p_maputl.c`, `p_local.h`: the blockmap is built at load time with 32-bit offsets instead of read from the lump (the lump format caps a map at roughly 100 x 100 blocks).
5. `r_plane.c`, `r_defs.h`, `r_things.h`: renderer limits raised (visplanes 128 -> 1024, drawsegs 256 -> 1024, vissprites 128 -> 512, openings x4).
6. `r_plane.c`, `r_main.c`: the sky is painted over the whole 3D view first. With skyscraper-high ceilings the normal sky marking leaves the area above short buildings empty.

Changes for shipping a custom level on the shareware IWAD:

7. `d_main.c`: removed "You cannot -file with the shareware version"; DEHACKED lumps may replace strings with longer ones.
8. `doomdef.h`, `g_game.c`, `wi_stuff.c`, `f_finale.c`: after `KL_LAST_MAP` (1) the intermission ends and the ending text is shown, then the game returns to the title screen. `g_game.c`: 5:00 par time for E1M1.

## Credits

Map data: (c) OpenStreetMap contributors, https://www.openstreetmap.org/copyright
