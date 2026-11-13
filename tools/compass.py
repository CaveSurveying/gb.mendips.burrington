#!/usr/bin/env python3
"""Passage walls from Compass .DAT files' LRUD, as a .lox for cave-viewer.

  compass.py out.lox cave.3d prefix a.DAT b.DAT ...

Survex reads Compass files but doesn't keep their LRUD (passage left, right, up and down at
each station), and Therion keeps them in a .lox only as numbers for Loch to make tubes of.
So the tubes are made here: an eight-sided section at each end of every leg whose from
station has LRUD (a Compass file's LRUD are at the shot's from station, in feet), square
to the leg, at the stations where cave.3d (Survex, loop-closed) puts them. The far end
takes its own station's LRUD where it has any, else the near end's. Written as Therion
.lox wall meshes in the 3d's coordinates, one per leg.
"""
import math
import re
import struct
import subprocess
import sys

FT = 0.3048
MAX_SIDE = 20.0     # metres: a wall further than this from its station is taken for a typing slip


def surveys(path):
    """(declination, corrections (compass, clino, length), [shot]) for each survey in a file:
    a shot is (from, to, length m, bearing, clino, (l, r, u, d) m or None, flags)."""
    text = open(path, encoding="latin-1").read().replace("\x1a", "")
    for block in text.split("\f"):
        lines = block.splitlines()
        decl, corr, shots, data = 0.0, (0.0, 0.0, 0.0), [], False
        for line in lines:
            m = re.search(r"DECLINATION:\s*(-?[\d.]+)", line)
            if m:
                decl = float(m.group(1))
                c = re.search(r"CORRECTIONS:\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)", line)
                if c:
                    corr = tuple(float(x) for x in c.groups())
                continue
            if line.split()[:2] == ["FROM", "TO"]:
                data = True
                continue
            f = line.split()
            if not data or len(f) < 9:
                continue
            frm, to = f[0], f[1]
            length, bearing, clino = (float(x) for x in f[2:5])
            left, up, down, right = (float(x) for x in f[5:9])
            flags = ""
            m = re.search(r"#\|([A-Z]*)#", line)
            if m:
                flags = m.group(1)
            lrud = None
            if min(left, right, up, down) >= 0 and left + right + up + down > 0:
                lrud = tuple(x * FT for x in (left, right, up, down))
                if max(lrud) > MAX_SIDE:     # a slip in the notes (Goatchurch's J4: 98 m to the left)
                    lrud = None
            shots.append((frm, to, (length + corr[2]) * FT, (bearing + corr[0]) % 360,
                          clino + corr[1] if abs(clino) != 90 else clino, lrud, flags))
        if shots:
            yield decl, shots


def read3d(path, prefix):
    """Station -> (E, N, Z) from a .3d (with dump3d), for stations under prefix."""
    out = {}
    for line in subprocess.run(["dump3d", path], capture_output=True, text=True, check=True).stdout.splitlines():
        if line.startswith("NODE") and "[" in line:
            p = line.split()
            st = line[line.index("[") + 1:line.index("]")]
            if st.startswith(prefix):
                out[st[len(prefix):]] = (float(p[1]), float(p[2]), float(p[3]))
    return out


def section(at, heading, lrud):
    """Eight points round a station: left, right, up, down (m) square to the heading."""
    l, r, u, d = lrud
    ex, ny = math.sin(heading), math.cos(heading)     # along the leg, in plan
    rx, ry = ny, -ex                                  # to its right
    pts = []
    for k in range(8):
        a = 2 * math.pi * k / 8
        side, up = math.sin(a), math.cos(a)           # 0: up, 90: right
        w = (r if side > 0 else l) * side
        h = (u if up > 0 else d) * up
        pts.append((at[0] + rx * w, at[1] + ry * w, at[2] + h))
    return pts


def tubes(out, cave3d, prefix, paths):
    pos = read3d(cave3d, prefix)
    # (a station's case as Survex left it: Compass's PSP is psp where the Survex had no *case)
    low = {k.lower(): v for k, v in pos.items()}
    for k, v in low.items():
        pos.setdefault(k, v)

    class Pos(dict):
        def __missing__(self, k):
            return low[k.lower()]

        def __contains__(self, k):
            return dict.__contains__(self, k) or k.lower() in low
    pos = Pos(pos)
    shots = [s for p in paths for _, ss in surveys(p) for s in ss if "P" not in s[6]]
    dims = {}
    for frm, to, length, bearing, clino, lrud, flags in shots:
        if lrud and frm not in dims:
            dims[frm] = lrud
    meshes, skipped = [], 0
    for frm, to, length, bearing, clino, lrud, flags in shots:
        if not lrud or frm == to or frm not in pos or to not in pos:
            continue
        a, b = pos[frm], pos[to]
        if abs(math.dist(a, b) - length) > max(1.0, 0.25 * length):
            skipped += 1        # (its stations aren't where its leg says: a name the Survex merged or renamed)
            continue
        if math.hypot(b[0] - a[0], b[1] - a[1]) < 0.2:   # a pitch: square to the passage it drops from
            heading = math.radians(bearing)
        else:
            heading = math.atan2(b[0] - a[0], b[1] - a[1])
        pts = section(a, heading, lrud) + section(b, heading, dims.get(to, lrud))
        tri = []
        for k in range(8):
            k2 = (k + 1) % 8
            tri += [(k, k2, 8 + k), (k2, 8 + k2, 8 + k)]
        tri += [(0, k + 1, k) for k in range(1, 7)] + [(8, 8 + k, 8 + k + 1) for k in range(1, 7)]   # the ends
        meshes.append((pts, tri))
    recs, data = b"", b""
    for i, (pts, tri) in enumerate(meshes):
        p = b"".join(struct.pack("<3d", *q) for q in pts)
        t = b"".join(struct.pack("<3I", *q) for q in tri)
        recs += struct.pack("<8I", i, 0, len(pts), len(data), len(p), len(tri), len(data) + len(p), len(t))
        data += p + t
    open(out, "wb").write(struct.pack("<4I", 4, len(recs), len(meshes), len(data)) + recs + data)
    print(f"{out}: {len(meshes)} legs with walls" + (f" ({skipped} left out, their stations not where their legs say)" if skipped else ""), file=sys.stderr)


if __name__ == "__main__":
    tubes(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
