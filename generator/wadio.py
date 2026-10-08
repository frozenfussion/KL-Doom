"""Minimal WAD reading/writing, and the resource lists we validate against."""
import struct


def read_wad(path):
    """Return (identification, [(name, bytes), ...]) for a WAD file."""
    data = open(path, "rb").read()
    ident, count, offset = struct.unpack("<4sii", data[:12])
    lumps = []
    for i in range(count):
        pos, size, name = struct.unpack("<ii8s", data[offset + 16 * i: offset + 16 * i + 16])
        lumps.append((name.rstrip(b"\0").decode("latin1"), data[pos:pos + size]))
    return ident.decode(), lumps


def write_wad(path, lumps, ident="PWAD"):
    """Write [(name, bytes), ...] as a WAD."""
    body = b""
    directory = b""
    offset = 12
    for name, blob in lumps:
        directory += struct.pack("<ii8s", offset + len(body), len(blob), name.encode("latin1"))
        body += blob
    header = struct.pack("<4sii", ident.encode(), len(lumps), 12 + len(body))
    with open(path, "wb") as f:
        f.write(header + body + directory)


class IwadResources:
    """What the IWAD offers: flats, wall textures (with sizes) and sprite names."""

    def __init__(self, path):
        _, lumps = read_wad(path)
        names = [n for n, _ in lumps]
        by_name = {}
        for n, b in lumps:
            by_name.setdefault(n, b)

        start, end = names.index("F_START"), names.index("F_END")
        self.flats = {n for n in names[start + 1:end] if not n.endswith("_START") and not n.endswith("_END")}

        tex = by_name["TEXTURE1"]
        count = struct.unpack("<i", tex[:4])[0]
        offsets = struct.unpack("<%di" % count, tex[4:4 + 4 * count])
        self.textures = {}
        for o in offsets:
            name = tex[o:o + 8].rstrip(b"\0").decode()
            width, height = struct.unpack("<hh", tex[o + 12:o + 16])
            self.textures[name] = (width, height)

        s0, s1 = names.index("S_START"), names.index("S_END")
        self.sprites = {n[:4] for n in names[s0 + 1:s1]}

    def check_flat(self, name):
        if name not in self.flats:
            raise SystemExit("flat %s is not in the IWAD" % name)
        return name

    def check_texture(self, name):
        if name not in self.textures:
            raise SystemExit("texture %s is not in the IWAD" % name)
        return name
