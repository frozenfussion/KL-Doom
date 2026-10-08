"""The status-bar face. Recolours id's 42 face pictures: darker brown skin, black hair.

Every expression, the damage stages, the blood and the god-mode and dead faces are kept;
only the colours change, so everything still lines up exactly like the original.
"""
import numpy as np

from graphics import encode_patch

SKIN_MUL = np.array([0.80, 0.74, 0.66])      # light skin -> medium brown
HAIR_LIGHT = np.array([44.0, 32.0, 26.0])    # black hair, brightest highlight
HAIR_DARK = np.array([3.0, 3.0, 3.0])
FADE = 3                                     # rows over which hair blends into skin
HAIR_ROWS = 8                                # rows from the top that are hair on a front-facing face
HAIR_ROWS_TURNED = 11                        # a turned head shows more hair


def lump_names():
    out = []
    for r in range(5):
        out += ["STFST%d%d" % (r, c) for c in (1, 0, 2)]
        out += ["STFTL%d0" % r, "STFTR%d0" % r, "STFOUCH%d" % r, "STFEVL%d" % r, "STFKILL%d" % r]
    return out + ["STFGOD0", "STFDEAD0"]


def _is_brown(rgb):
    r, g, b = (int(v) for v in rgb)
    return r >= g >= b and r - b > 20 and g > 0.45 * r      # not blood (red) and not grey


def recolour(wad, name):
    w, h, left, top, idx = wad.patch(name)
    pal = np.array(wad.pal, dtype=float)
    turned = name.startswith(("STFTL", "STFTR"))
    hair_rows = HAIR_ROWS_TURNED if turned else HAIR_ROWS
    out = [[None] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            i = idx[y][x]
            if i is None:
                continue
            rgb = pal[i]
            if _is_brown(rgb):
                lum = rgb.mean() / 255.0
                hair = HAIR_DARK + (HAIR_LIGHT - HAIR_DARK) * min(1.0, lum / 0.75)
                skin = rgb * SKIN_MUL
                m = min(1.0, max(0.0, (hair_rows + FADE - y) / FADE))     # 1 = all hair, 0 = all skin
                rgb = hair * m + skin * (1 - m)
            d = ((pal - rgb) ** 2).sum(axis=1)
            d[[0, 255]] += 1e6          # never pick black-reserved or transparent-looking entries
            out[y][x] = int(d.argmin())
    return out, left, top


def face_lumps(wad):
    lumps = []
    for n in lump_names():
        grid, left, top = recolour(wad, n)
        lumps.append((n, encode_patch(grid, left=left, top=top)))
    return lumps
