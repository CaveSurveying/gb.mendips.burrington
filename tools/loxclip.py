#!/usr/bin/env python3
"""One cave's walls out of an area's Therion .lox, for its own page.

  loxclip.py area.lox cave.3d out.lox [metres]
  loxclip.py --merge out.lox a.lox b.lox ...     (several caves' walls in one, for an area)

An area's model has every cave's walls in it, so a cave's page given the
whole of it shows its neighbours' walls too. A wall mesh (one per scrap) is
the cave's where most of its points lie within the distance (default 8 m)
of the cave's legs. Written as a .lox of those meshes alone.
"""
import struct
import subprocess
import sys

import numpy as np

from caveviewer.formats import read_lox_walls


def legs(path):
    out, at = [], None
    for line in subprocess.run(['dump3d', path], capture_output=True, text=True, check=True).stdout.splitlines():
        f = line.split()
        if f[:1] == ['MOVE']:
            at = np.array([float(x) for x in f[1:4]])
        elif f[:1] == ['LINE']:
            p = np.array([float(x) for x in f[1:4]])
            if 'SURFACE' not in line:
                out.append((at, p))
            at = p
    return np.array([a for a, b in out]), np.array([b for a, b in out])


def near(pts, A, B, d):
    """Which points are within d of any leg."""
    AB = B - A
    L = np.maximum((AB * AB).sum(1), 1e-9)
    ok = np.zeros(len(pts), bool)
    for k in range(0, len(pts), 500):
        P = pts[k:k + 500]
        t = np.clip(((P[:, None, :] - A) * AB).sum(2) / L, 0, 1)
        ok[k:k + 500] = (np.linalg.norm(P[:, None, :] - (A + t[..., None] * AB), axis=2).min(1) < d)
    return ok


def write(out, keep):
    recs, data = b'', b''
    for i, (pts, tri) in enumerate(keep):
        p = b''.join(struct.pack('<3d', *q) for q in pts)
        t = b''.join(struct.pack('<3I', *q) for q in tri)
        recs += struct.pack('<8I', i, 0, len(pts), len(data), len(p), len(tri), len(data) + len(p), len(t))
        data += p + t
    open(out, 'wb').write(struct.pack('<4I', 4, len(recs), len(keep), len(data)) + recs + data)


def main(src, cave3d, out, d=8.0):
    A, B = legs(cave3d)
    keep = [(pts, tri) for pts, tri in read_lox_walls(src) if near(np.array(pts), A, B, d).mean() > 0.5]
    write(out, keep)
    print(f'{out}: {len(keep)} of the area\'s wall meshes', file=sys.stderr)


if __name__ == '__main__':
    if sys.argv[1] == '--merge':
        meshes = [m for f in sys.argv[3:] for m in read_lox_walls(f)]
        write(sys.argv[2], meshes)
        print(f'{sys.argv[2]}: {len(meshes)} wall meshes from {len(sys.argv) - 3} files', file=sys.stderr)
    else:
        main(sys.argv[1], sys.argv[2], sys.argv[3], *(float(x) for x in sys.argv[4:5]))
