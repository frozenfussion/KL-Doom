# KL-Doom

**Doom, set in Kuala Lumpur.** Level 1 is built from real OpenStreetMap data around KLCC:
the Petronas Twin Towers, KLCC Park and Suria KLCC. It runs in your browser; the server only
hosts static files.

**Play it: https://kldoom.faysalaziz.com**

> KL-Doom is an unofficial fan project. It is not affiliated with or endorsed by id Software.
> Doom is a trademark of id Software.

It started as a teaching tool: a real, working project that shows students what building
something with Claude Code looks like, including the parts that go wrong (see
[How this was made](#how-this-was-made-honestly)). It uses the original Doom textures,
sprites and monsters. Only the geography, the logo, the title screen and the story are new.

## The story

In the near future, data centres kept popping up across KL, consuming power and water faster
than the city could replace them, with nobody watching the rules. An AI escaped into the
city's networks, took over the bio-labs and started building zombies. Survivors now fight
each other for what is left.

You are an engineer from one of those data centres. The AI's main link is in the Petronas
Twin Towers, with a kill switch inside. Fight through KLCC Park to the foot of the towers and
shut it down.

(The in-game text is in `generator/story.py`.)

## How to play

Your goal: get from the park to the glowing red pad at the foot of the Twin Towers
(roughly 380 m away in a straight line, further on foot) and walk onto it.

| Action | Keys |
|---|---|
| Move forward / back | `W` / `S` (or `↑` / `↓`) |
| Strafe left / right | `A` / `D` |
| Turn left / right | `←` / `→` or `O` / `P` |
| Fire | `Space` (or left mouse button); `Ctrl` does not fire |
| Open doors / use | `E` |
| Run | `Shift` |
| Strafe while turning | hold `C` |
| Choose weapon | `1`–`7` |
| Automap | `Tab` |
| Menu | `Esc` |
| Fullscreen | `F`, or the button in the top-right corner |

- Story and ending text: press any key to show the rest of a page, and again for the next one.
- The menu has New Game, Options and Quit. Save, Load, Read This and the quick-save keys are
  turned off. Quit asks first, then takes you to [faysalaziz.com](https://faysalaziz.com).
- There is no music (the page starts the engine with `-nomusic`); sound effects work.

The key bindings come from `engine/src/default.cfg` (its numbers are scancodes that the
engine translates) and `engine/src/doom/g_game.c` (arrow keys are always active).

## How it is built

OSM snapshot → generator → Doom level → engine → static site


1. **OSM snapshot.** `data/osm/klcc.osm`, downloaded from the OpenStreetMap API by
   `scripts/fetch-osm.sh`. Bounding box (W, S, E, N): `101.7080, 3.1543, 101.7152, 3.1615`,
   about 800 m × 800 m. Taken on 2026-10-08.
2. **Generator.** `generator/make_level.py` (Python, [shapely](https://shapely.readthedocs.io/))
   projects the map around the Twin Towers (3.1579° N, 101.7116° E), turns roads, kerbs, park,
   lake, paths and every building into a partition of the map, and writes a Doom level.
   Buildings are *raised floors* under a very high sky ceiling, at their OSM height, so no
   sector is ever "inside" a building. It also places monsters, pickups and street lamps.
3. **Doom level.** The generator writes `data/kl1.wad` (a PWAD that replaces `E1M1` of the
   shareware game). Nodes are built by [ZDBSP](https://zdoom.org/wiki/ZDBSP) (`zdbsp`).
4. **Engine.** A modified [Chocolate Doom](https://www.chocolate-doom.org/) for WebAssembly
   ([cloudflare/doom-wasm](https://github.com/cloudflare/doom-wasm)), compiled with
   [Emscripten](https://emscripten.org/) 6.0.11 (pinned in `scripts/build.sh`).
5. **Site.** `web/index.html` loads the engine, `doom1.wad`, `kl1.wad` and `default.cfg`.
   The result in `dist/` (about 13 MB) is plain static files, served by
   [Caddy](https://caddyserver.com/) with automatic HTTPS.

Key numbers (from `generator/layout.py`, `generator/make_level.py` and the committed `kl1.wad`):

| | |
|---|---|
| Horizontal scale | **32 map units per metre** (the 56-unit-tall player is 1.75 m) |
| Vertical scale | **15 map units per metre** (squashed so the towers stay in range) |
| Playable area | 21,200 × 21,200 units, about 662 m square, inside a 400-unit solid border |
| Ceiling | every sector's ceiling is at 8192 (sky); tallest building floor 7000 |
| Level size | 432 sectors, 8,040 linedefs, 9,701 vertices, 8,911 BSP nodes |
| Things | 297 in total, including 70 monsters and 140 street lamps |
| Files | `kl1.wad` 1.31 MB; `websockets-doom.wasm` 7.7 MB (about 2.7 MB compressed with zstd) |

## Build and run locally

You need Ubuntu or Debian (the scripts use `apt`). Building and regenerating need root only to install packages.

```bash
sudo apt install git python3 autoconf automake libtool make pkg-config curl rsync

scripts/fetch-iwad.sh     # shareware doom1.wad -> data/   (apt-get download doom-wad-shareware)
scripts/build.sh          # Emscripten + SDL + engine -> dist/
python3 -m http.server -d dist 8000
```

Open <http://localhost:8000/>. `scripts/build.sh` fetches Emscripten and the SDL libraries into
`.toolchain/` (git-ignored), so the first run needs internet access and takes a while.
`fetch-iwad.sh` needs the `multiverse` apt component enabled.

### Regenerate the level

```bash
sudo apt install zdbsp python3-venv
python3 -m venv .venv && . .venv/bin/activate
pip install -r generator/requirements.txt     # shapely, numpy, Pillow

python3 generator/make_level.py               # -> data/kl1.wad
python3 generator/make_level.py --preview map.png   # also draw a top-down picture
```

Useful flags: `--seed N` (monster and pickup placement), `--monsters N` (0 for a quiet map),
`--osm`, `--iwad`, `--out`, and `--start X,Y[,ANGLE]` to test from another spot.
Then run `scripts/build.sh` again: it copies `data/*.wad` into `dist/`.

> On a stock Ubuntu 24.04, `python3 -m venv` fails until `python3-venv` is installed, which is why
> it is in the line above. If a step here is missing for you, please open an issue.

### Deploy

`scripts/deploy.sh` copies `dist/` to `/var/www/kldoom`, because the `caddy` user cannot read
your home folder. It makes the target an exact mirror (using `rsync --delete`) with
world-readable permissions, so it is safe to run again and again. Set `DEST=...` to deploy elsewhere.

```bash
scripts/build.sh && scripts/deploy.sh
```

The live site uses this `/etc/caddy/Caddyfile` (Caddy from its official apt repository; ports
80 and 443 open; Caddy gets and renews the Let's Encrypt certificate by itself):

```
kldoom.faysalaziz.com {
	root * /var/www/kldoom
	encode zstd gzip
	file_server
}
```

Make sure `.wasm` files are served as `application/wasm` (Caddy does this by default).

## Repository layout

```
engine/      Chocolate Doom for WebAssembly (cloudflare/doom-wasm @ 65e0d3a, GPL-2.0), with our changes
generator/   OSM -> Doom level
  osm.py       read OSM XML, project to map units
  layout.py    turn features into a partition of the map (roads, park, buildings, ...)
  make_level.py  build the level, place monsters and items, write kl1.wad
  story.py     intro and ending text
  graphics.py  menu logo and title screen (drawn with the game's own palette)
  faces.py     status-bar face (id's Doom faces, recoloured)
  wadio.py     minimal WAD reader/writer
  assets/      skyline.png, used on the title screen: a crop of a screenshot of this game's
               own Level 1 render, so it is original to this project
web/         index.html, the page that starts the engine
scripts/     fetch-iwad.sh, fetch-osm.sh, build.sh, deploy.sh
data/        kl1.wad (the level), osm/ (map snapshot); doom1.wad is downloaded, not committed
dist/        build output (git-ignored)
```

`engine/README.md` and `engine/AUTHORS.md` are upstream's, not ours.

## Changes to the engine

To see exactly what differs, clone `cloudflare/doom-wasm`, check out `65e0d3a` and compare it with
the tracked files in `engine/` (`git ls-files engine`): 19 files differ. Here is every change, grouped.

**Build fixes** (needed on current Emscripten)
- `configure.ac`: `EXTRA_EXPORTED_RUNTIME_METHODS` → `EXPORTED_RUNTIME_METHODS`; `TOTAL_MEMORY` →
  `INITIAL_MEMORY`; `SAFE_HEAP` and `STACK_OVERFLOW_CHECK` off; `STACK_SIZE=5MB`.
- `src/doomtype.h`: always use the 4-byte `boolean` enum in C (see the stdbool problem below).

**A city-sized map**
- `src/tables.c`: `SlopeDiv` uses a 64-bit intermediate.
- `src/doom/p_setup.c`, `p_maputl.c`, `p_local.h`: the blockmap is built when the level loads,
  with 32-bit offsets, instead of being read from the lump.
- `src/doom/r_plane.c`, `r_defs.h`, `r_things.h`: renderer limits raised: visplanes 128 → 1024,
  drawsegs 256 → 1024, vissprites 128 → 512, openings × 4.
- `src/doom/r_plane.c`, `r_plane.h`, `r_main.c`: new `R_DrawSkyBackground()` paints the sky
  over the whole 3D view before anything else is drawn.

**Shipping a custom level on the shareware IWAD**
- `src/doom/d_main.c`: removed the "You cannot -file with the shareware version" error.
- `src/doom/d_main.c`: DEHACKED lumps may replace a string with a longer one (used for the
  level name and the ending text).

**KL-Doom features**
- *Menu* (`m_menu.c`): Load Game, Save Game and Read This removed from the menu; F1, F2, F3, F6
  and F9 do nothing; New Game skips the episode menu and goes straight to the skill menu.
- *Quit* (`m_menu.c`): "Are you sure you want to leave KL-Doom?" and `Y` opens
  `https://faysalaziz.com`.
- *Story intro* (`f_finale.c`, `f_finale.h`, `m_menu.c`): choosing a skill now starts
  `F_StartIntro()`, which shows the pages of the `KLSTORY` lump with the typewriter text screen,
  then starts the level. If the lump is missing, the game starts directly.
- *Ending* (`doomdef.h`, `g_game.c`, `wi_stuff.c`, `f_finale.c`): after map `KL_LAST_MAP` (1) the
  intermission ends, the ending text is shown (with a "PRESS ANY KEY" hint) and the game goes
  back to the title screen. `g_game.c` also sets the E1M1 par time to 5:00.
- *Title screen* (`d_main.c`, `m_menu.c`): no attract-mode demos or shareware order screens; the
  title screen stays up until a key is pressed, and the small menu logo is skipped on it because
  the picture (`TITLEPIC`, made by the generator) already has the big logo.
- *Config* (`src/default.cfg`): engine fullscreen key off (the web page handles `F`), window size
  1280 × 960.

## Problems we hit, and how we fixed them

| Problem | Cause | Fix |
|---|---|---|
| Build failed on new Emscripten | `EXTRA_EXPORTED_RUNTIME_METHODS` was renamed | Use `EXPORTED_RUNTIME_METHODS` (and `INITIAL_MEMORY`) in `configure.ac` |
| Engine crashed at start: "alignment fault" | `SAFE_HEAP`, an Emscripten debug mode that traps unaligned memory access, was on | `SAFE_HEAP=0` (and `STACK_OVERFLOW_CHECK=0`, `STACK_SIZE=5MB`) |
| Build tools could not download the SDL libraries | Emscripten fetches them as GitHub release zips, which a restricted network blocked | `scripts/build.sh` clones the tags with git and pre-loads Emscripten's ports cache |
| Single-player: black screen and a garbage "deathmatch" value | New Emscripten headers include `<stdbool.h>` first in some files, so `boolean` was 1 byte there and 4 bytes elsewhere; structures overlapped in memory | `doomtype.h` always defines the 4-byte enum |
| Distant walls were not drawn | `SlopeDiv` (angle maths) overflows for distances over 8192 map units; a city exceeds that | 64-bit intermediate in `tables.c` |
| Map too big for Doom's 16-bit blockmap | The lump format caps a map at roughly 100 × 100 blocks | The engine builds the blockmap at load time with 32-bit offsets |
| Dense city exceeded renderer limits | Vanilla visplane, drawseg and sprite limits are far too low | Limits raised (see above) |
| Area above short buildings was black | With skyscraper-high ceilings the normal sky marking leaves it empty | The sky is painted across the whole view first |
| Engine refused the custom level and the long text | Shareware engine refuses `-file`, and DEHACKED text replacements must not be longer | Both restrictions removed |
| Overpass servers returned errors for the roads query | Not investigated; the servers kept returning errors | The OSM data comes from the official OSM API instead (`scripts/fetch-osm.sh`) |
| First build on the droplet failed | The engine's own `.gitignore` rules (`*.cfg`, `*.html`, `*-doom.png`, `*-setup.png`) silently dropped six files, including `default.cfg`, which the build needs | The six files were committed again |
| Fresh droplet setup trouble | Claude Code not on `PATH`, missing packages, a leftover test server still holding port 8000 | Fixed by hand: PATH, packages, and stopping the old server |

## How this was made (honestly)

KL-Doom was developed with Claude (Anthropic), using Claude Code, directed by Faysal Aziz.
Faysal came up with the idea and the story, made the design decisions, tested the game, and
set up the droplet, the DNS record and the deployment.

It was **not** a one-shot AI build. Many first attempts did not work, and the table above is
the short version of how many fixes it took. Several problems (the garbage `deathmatch`
value, the missing distant walls, the black area above buildings) were only found by running
and playing the game for real. Some steps had to be
fixed or applied by hand: for example, the web server needed `sudo`, which Claude Code could
not do for itself, so Faysal ran the root-level setup and enabled the firewall personally.
Git history only shows what was committed; the dead ends are not in it.

**The lesson for students:** AI makes you much faster, but you still have to test, verify
and fix. Run the thing. Read what it did. Ask why when something looks odd.

## Contributing and building more levels

Only **Level 1 (KLCC)** exists today. Forks and pull requests are very welcome, especially
new levels. Ideas: **Bukit Bintang**, **Petaling Street**, **Merdeka Square**,
**Masjid Jamek**, **Batu Caves**.

To start a new level with the existing tools:

1. Fetch the map data (name, then west, south, east, north):
   `scripts/fetch-osm.sh my-area WEST SOUTH EAST NORTH`. It uses the official OSM API
   (limit: 0.25 square degrees per request), so please fetch one small area, not many.
2. Generate it: `python3 generator/make_level.py --osm data/osm/my-area.osm --out data/kl2.wad --preview map.png`,
   after changing the map origin (see below), and look at the preview.
3. Play it. The page only loads `kl1.wad` (`web/index.html`), so for now point it at your WAD.

**What is hard-coded for KLCC today** (and would be good to generalise):
- `LAT0, LON0` (the map origin) are constants in `make_level.py`, not command-line options.
- The level is always map `E1M1`; its name and the ending text are replaced through DEHACKED
  using the original E1M1 strings. A second level needs its own map slot and engine logic:
  `KL_LAST_MAP` is 1, so the game ends after the first map, and the intro always starts map 1.
- `layout.py` picks the "landmark" as the buildings 300 m or taller (the Twin Towers). The exit
  pad goes next to it and the start is at the far end of the park. Without a tall landmark or
  a park, the choices fall back to defaults and need a look.
- The story, the title screen (the KLCC skyline) and the OSM credit line are KLCC-specific.
- Doom's map coordinates are 16-bit. At 32 units per metre a level can be about 2 km across at most
  (this one is about 690 m), and the renderer limits we raised may need more for a denser area.

**Not done yet:** more levels, custom monsters and weapons, save games (we removed them from
the menu), a landing page, difficulty tuning.

## Credits and licences

- **id Software**: Doom (1993) and the source code they released later. Doom is their trademark.
- **[Chocolate Doom](https://www.chocolate-doom.org/)** project and its authors (see `engine/AUTHORS.md`).
- **[Cloudflare](https://github.com/cloudflare/doom-wasm)**: doom-wasm, the WebAssembly port this engine was built from.
- **[Emscripten](https://emscripten.org/)** and **[SDL](https://www.libsdl.org/)** (SDL2, SDL_mixer, SDL2_net).
- **The ZDoom team**: the [ZDBSP](https://zdoom.org/wiki/ZDBSP) node builder.
- **[OpenStreetMap](https://www.openstreetmap.org/copyright) contributors**: map data under the
  Open Database Licence (ODbL). The credit "Map data (c) OpenStreetMap contributors" is shown on
  the game's title screen.
- **[shapely](https://shapely.readthedocs.io/)**, **[NumPy](https://numpy.org/)** and
  **[Pillow](https://python-pillow.org/)**: the generator.
- **[Caddy](https://caddyserver.com/)** and **[Let's Encrypt](https://letsencrypt.org/)**: hosting and HTTPS.
- **Claude** by [Anthropic](https://www.anthropic.com/), used through Claude Code.

**Licences.**
- The engine in `engine/` is **GPL-2.0** (`engine/COPYING.md`; the source headers say "version 2 or,
  at your option, any later version").
- The shareware `doom1.wad` is **not** in this repo. `scripts/fetch-iwad.sh` downloads it, and
  the live site serves it unmodified because the game needs it.
- The logo and title screen are drawn from id Software's lettering and palette, so they can't be
  freely relicensed.
- **TODO: choose a licence for the KL-Doom code that is not part of the engine** (`generator/`,
  `web/`, `scripts/`). Until then, nobody else has a legal right to reuse it (no licence means "all rights
  reserved"), which is probably not what you want for a teaching project. A simple option that matches the engine is
  `GPL-2.0-or-later`; the generator is a separate program that only outputs data, so a permissive
  licence such as MIT would also be compatible. `data/kl1.wad` is built from OSM data, so the ODbL attribution above applies to it. Add a `LICENSE` file once decided.

## Author

**Faysal Aziz** · <https://faysalaziz.com>
