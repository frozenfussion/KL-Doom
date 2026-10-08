"""Pixel art for KL-Doom, drawn with the game's own palette.

- make_kl_doom():  a 'KL' in the style of the DOOM menu logo, joined to the original lettering
- build_titlepic(): the title screen (KLCC skyline, reflected in the lake, with the new logo)
- encode_patch():  palette-indexed pixels -> Doom picture lump
"""
import os
import random
import struct

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
WAD = os.path.join(os.path.dirname(HERE), "data", "doom1.wad")
SKYLINE = os.path.join(HERE, "assets", "skyline.png")


class Wad:
    def __init__(self, path=WAD):
        d = open(path, "rb").read()
        self.d = d
        ident, n, off = struct.unpack("<4sii", d[:12])
        self.ents = {}
        for i in range(n):
            p, s, name = struct.unpack("<ii8s", d[off + 16 * i: off + 16 * i + 16])
            self.ents.setdefault(name.rstrip(b"\0").decode("latin1"), (p, s))
        pal = self.data("PLAYPAL")[:768]
        self.pal = [tuple(pal[i * 3:i * 3 + 3]) for i in range(256)]

    def data(self, name):
        p, s = self.ents[name]
        return self.d[p:p + s]

    def patch(self, name):
        """Return (width, height, left, top, index grid[y][x] with None for transparent)."""
        b = self.data(name)
        w, h, l, t = struct.unpack("<hhhh", b[:8])
        cols = struct.unpack("<%dI" % w, b[8:8 + 4 * w])
        idx = [[None] * w for _ in range(h)]
        for x, co in enumerate(cols):
            p = co
            while b[p] != 255:
                rs, cnt = b[p], b[p + 1]
                p += 3
                for k in range(cnt):
                    if rs + k < h:
                        idx[rs + k][x] = b[p + k]
                p += cnt + 1
        return w, h, l, t, idx

    def image(self, idx):
        h, w = len(idx), len(idx[0])
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        px = im.load()
        for y in range(h):
            for x in range(w):
                if idx[y][x] is not None:
                    px[x, y] = self.pal[idx[y][x]] + (255,)
        return im


def encode_patch(idx, left=0, top=0):
    """Index grid -> Doom picture-format lump."""
    h, w = len(idx), len(idx[0])
    columns = []
    for x in range(w):
        col = b""
        y = 0
        while y < h:
            if idx[y][x] is None:
                y += 1
                continue
            start = y
            run = []
            while y < h and idx[y][x] is not None and y - start < 254:
                run.append(idx[y][x])
                y += 1
            col += bytes([start, len(run), 0]) + bytes(run) + bytes([0])
        columns.append(col + b"\xff")
    header = struct.pack("<hhhh", w, h, left, top)
    base = 8 + 4 * w
    offsets, pos = [], base
    for c in columns:
        offsets.append(pos)
        pos += len(c)
    return header + struct.pack("<%dI" % w, *offsets) + b"".join(columns)


def make_kl_doom(wad, rng_seed=7):
    """Return (index grid of the full 'KL DOOM' logo, width of the added 'KL' part)."""
    w0, h0, _, _, orig = wad.patch("M_DOOM")
    rng = random.Random(rng_seed)

    # Material samples from the original, kept per row so the vertical gradients match.
    def band(rows, xs, ok):
        out = {}
        for y in rows:
            vals = [orig[y][x] for x in xs if orig[y][x] is not None and ok(orig[y][x])]
            if vals:
                out[y] = vals
        return out

    def brownish(i):
        r, g, b = wad.pal[i]
        return r >= g >= b and r > 50 and not (r > 200 and g > 190)

    blue_rows = band(range(4, 30), list(range(6, 11)) + list(range(22, 28)), lambda i: wad.pal[i][2] > wad.pal[i][0])
    rock_rows = band(range(32, 54), range(7, 29), brownish)
    blue = [v for vals in blue_rows.values() for v in vals]
    rock = [v for vals in rock_rows.values() for v in vals]

    def material(rows, y):
        keys = sorted(rows)
        near = min(keys, key=lambda k: abs(k - y))
        return rows[near]

    left_gradient = [orig[y][3] if orig[y][3] is not None else orig[y][4] for y in range(h0)]
    yellow, dark_red = 241, 189
    top_bar = [orig[0][5], orig[1][5], orig[2][6]]

    LW = 30                       # width of one added letter
    W = 2 * LW + w0
    H = 60
    canvas = [[None] * W for _ in range(H)]

    def noise(rows, x, y):
        # pick from the sample for this row; coarse in x so it looks like the original's grain
        r = random.Random((x // 2) * 73856093 ^ y * 19349663 ^ rng_seed)
        vals = material(rows, y)
        return vals[r.randrange(len(vals))]

    def letter_mask(points, x0):
        m = Image.new("L", (W, H + 10), 0)
        ImageDraw.Draw(m).polygon([(x0 + px, py) for px, py in points], fill=255)
        return m

    def slant(m, x0, top_y=3):
        # cut the bottom with a diagonal like the original letters: lower on the left, higher on the right
        px = m.load()
        for x in range(x0, x0 + LW):
            yb = 57 - int(0.45 * (x - x0))
            for y in range(H + 10):
                if y > yb:
                    px[x, y] = 0
        return m

    shapes = {
        "K": [(3, 3), (13, 3), (13, 25), (21, 3), (30, 3), (19, 28), (30, 40), (30, 62), (21, 62), (13, 42), (13, 62), (3, 62)],
        "L": [(3, 3), (13, 3), (13, 40), (30, 40), (30, 62), (3, 62)],
    }
    for i, ch in enumerate("KL"):
        x0 = i * LW
        face = slant(letter_mask(shapes[ch], x0), x0)
        fp = face.load()
        inside = lambda x, y: 0 <= x < W and 0 <= y < H + 10 and fp[x, y] > 0
        # extrusion band under the face: same silhouette shifted down, in darker rock
        for y in range(H):
            for x in range(x0, x0 + LW):
                if inside(x, y):
                    continue
                if any(inside(x, y - k) for k in range(1, 7)):
                    canvas[y][x] = noise(rock_rows, x, y)
        # face fill
        for y in range(H):
            for x in range(x0, x0 + LW):
                if inside(x, y):
                    canvas[y][x] = noise(blue_rows if y < 31 else rock_rows, x, y)
        # edges
        for y in range(H):
            for x in range(x0, x0 + LW):
                if not inside(x, y):
                    continue
                if not inside(x - 1, y):
                    for k in range(3):
                        if inside(x + k, y):
                            canvas[y][x + k] = left_gradient[min(y, h0 - 1)]
                elif not inside(x + 1, y):
                    for k in range(3):
                        if inside(x - k, y):
                            canvas[y][x - k] = left_gradient[min(y, h0 - 1)]
                if not inside(x, y - 1) and y < 10:
                    for k in range(2):
                        if inside(x, y + k):
                            canvas[y + k][x] = top_bar[k % len(top_bar)]
                if not inside(x, y + 1):
                    canvas[y][x] = yellow

    # original DOOM to the right
    for y in range(h0):
        for x in range(w0):
            if orig[y][x] is not None:
                canvas[y][2 * LW + x] = orig[y][x]
    return canvas, 2 * LW


# --- title screen -------------------------------------------------------------
class Screen:
    """A 320x200 true-colour canvas that patches and text can be drawn onto."""

    def __init__(self, wad, base=None):
        self.wad = wad
        self.im = (base or Image.new("RGB", (320, 200), (0, 0, 0))).convert("RGBA")
        self.font = {}
        for code in range(33, 96):
            name = "STCFN%03d" % code
            if name in wad.ents:
                self.font[code] = wad.patch(name)

    def patch(self, image, x, y):
        self.im.alpha_composite(image, (x, y))

    def text(self, line, x, y):
        """Draw like the engine's text screens: 4 px for a space, glyph widths otherwise."""
        for ch in line.upper():
            code = ord(ch)
            if code not in self.font:
                x += 4
                continue
            w, h, l, t, idx = self.font[code]
            self.im.alpha_composite(self.wad.image(idx), (x - l, y - t))
            x += w

    def quantise(self):
        """Snap every pixel to the nearest colour of the game's palette; return the index grid."""
        pal = np.array(self.wad.pal, dtype=np.int32)
        arr = np.array(self.im.convert("RGB"), dtype=np.int32).reshape(-1, 3)
        out = np.empty(len(arr), dtype=np.int32)
        for i in range(0, len(arr), 8192):
            chunk = arr[i:i + 8192]
            out[i:i + 8192] = ((chunk[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
        self.im = Image.fromarray(pal[out].reshape(200, 320, 3).astype(np.uint8)).convert("RGBA")
        return out.reshape(200, 320).tolist()


def build_titlepic(wad, logo_image):
    """The 320x200 title screen as an index grid."""
    top = Image.open(SKYLINE).convert("RGB").resize((320, 120), Image.BOX)
    refl = top.transpose(Image.FLIP_TOP_BOTTOM).point(lambda v: int(v * 0.45))
    refl = Image.merge("RGB", (refl.getchannel(0).point(lambda v: int(v * 0.7)),
                               refl.getchannel(1).point(lambda v: int(v * 0.85)), refl.getchannel(2)))
    base = Image.new("RGB", (320, 200), (0, 0, 0))
    base.paste(top, (0, 0))
    base.paste(refl, (0, 120))
    base.paste(refl.crop((0, 0, 320, 80)), (0, 120))
    s = Screen(wad, base)
    big = logo_image.resize((int(logo_image.width * 1.5), int(logo_image.height * 1.5)), Image.NEAREST)
    s.patch(big, (320 - big.width) // 2, 14)
    s.text("A KUALA LUMPUR ADVENTURE", (320 - 8 * 24) // 2 + 4, 170)
    s.text("MAP DATA (C) OPENSTREETMAP CONTRIBUTORS", 12, 186)
    return s.quantise()
