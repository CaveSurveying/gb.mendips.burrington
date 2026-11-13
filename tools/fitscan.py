#!/usr/bin/env python3
"""Fitting a printed survey (a picture of it) to a cave's centreline, for cave-viewer's drawn
"scan": a fit is pixel x - i*y = A * (E + iN) + B, A and B complex (caveviewer/drawn/scan_geo.py).

  fitscan.py start cave.3d picture.png out.fit PX_PER_M  X,Y=E,N [TURN]
        a first fit: the scale, the station at E,N (full grid) drawn at pixel X,Y, and the
        drawing turned TURN degrees anticlockwise from grid north (default 0)
  fitscan.py search cave.3d picture.png in.fit out.fit [DEG] [SCALE%] [PX]
        search turn, scale and shift round a fit for the most ink under the survey legs
  fitscan.py solve cave.3d out.fit W,H STATION=X,Y ...
        a fit by least squares from stations matched on the drawing
  fitscan.py overlay cave.3d picture.png fit out.png
        the centreline drawn on the picture by the fit, to check it
OFFSET (env, "E,N"): what the .3d's coordinates add up to the full grid (default 0,0).
"""
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OFF = complex(*[float(v) for v in os.environ.get('OFFSET', '0,0').split(',')])


def legs(p, surface=False):
    out, at = [], None
    for line in subprocess.run(['dump3d', p], capture_output=True, text=True, check=True).stdout.splitlines():
        f = line.split()
        if f[:1] == ['MOVE']:
            at = complex(float(f[1]), float(f[2])) + OFF
        elif f[:1] == ['LINE']:
            q = complex(float(f[1]), float(f[2])) + OFF
            if 'SPLAY' not in line and (surface or 'SURFACE' not in line):
                out.append((at, q))
            at = q
    return out


def nodes(p):
    out = {}
    for line in subprocess.run(['dump3d', p], capture_output=True, text=True, check=True).stdout.splitlines():
        if line.startswith('NODE') and '[]' not in line:
            f = line.split()
            out[line[line.index('[') + 1:line.index(']')]] = complex(float(f[1]), float(f[2])) + OFF
    return out


def load(fit):
    t = json.load(open(fit))
    return complex(*t['global'][:2]), complex(*t['global'][2:]), t['drawing']


def save(fit, A, B, size):
    json.dump({'drawing': list(size), 'cell': 250.0, 'global': [A.real, A.imag, B.real, B.imag], 'local': {}}, open(fit, 'w'))
    print(f'{fit}: {abs(A):.3f} px/m, turned {math.degrees(math.angle(A)) if hasattr(math, "angle") else np.degrees(np.angle(A)):.2f} deg', file=sys.stderr)


def start(cave, pic, out, scale, at, turn='0'):
    xy, en = at.split('=')
    x, y = (float(v) for v in xy.split(','))
    e, n = (float(v) for v in en.split(','))
    A = float(scale) * np.exp(1j * np.radians(float(turn)))
    B = complex(x, -y) - A * complex(e, n)
    save(out, A, B, Image.open(pic).size)


def search(cave, pic, fit_in, out, deg='10', sc='8', px='150'):
    DEG, SC, PX = float(deg), float(sc), float(px)
    im = Image.open(pic).convert('L')
    W, H = im.size
    ink = im.point(lambda v: 255 if v < 140 else 0)
    blur = [np.asarray(ink.filter(ImageFilter.GaussianBlur(r)), float) for r in (12, 5, 2)]
    pts = []
    for a, b in legs(cave):
        k = max(2, int(abs(b - a) / 0.5))
        pts += [a + (b - a) * t for t in np.linspace(0, 1, k)]
    Z = np.array(pts)
    c0 = Z.mean()
    Z0 = Z - c0
    A0, B0, _ = load(fit_in)
    U0 = A0 * c0 + B0

    def score(b, A, U):
        u = A * Z0 + U
        x, y = u.real, -u.imag
        ok = (x >= 0) & (x < W - 1) & (y >= 0) & (y < H - 1)
        return b[y[ok].astype(int), x[ok].astype(int)].sum() / len(Z)
    best = (score(blur[0], A0, U0), A0, U0)
    for b, deg_, sc_, px_, step in ((blur[0], DEG, SC, PX, max(2, PX / 15)), (blur[1], DEG / 4, SC / 3, PX / 6, max(1, PX / 50)),
                                    (blur[2], DEG / 10, SC / 8, PX / 20, 1)):
        _, Ab, Ub = best
        best = (score(b, Ab, Ub), Ab, Ub)
        for dr in np.linspace(-deg_, deg_, 9):
            for ds in np.linspace(-sc_, sc_, 5):
                A = Ab * np.exp(1j * np.radians(dr)) * (1 + ds / 100)
                for dx in np.arange(-px_, px_ + 1e-9, step):
                    for dy in np.arange(-px_, px_ + 1e-9, step):
                        U = Ub + complex(dx, -dy)
                        s = score(b, A, U)
                        if s > best[0]:
                            best = (s, A, U)
        print(f'  pass: {abs(best[1]):.3f} px/m, turned {np.degrees(np.angle(best[1])):.2f} deg, score {best[0]:.1f}', file=sys.stderr)
    _, A, U = best
    save(out, A, U - A * c0, (W, H))


def solve(cave, out, size, *pairs):
    pos = nodes(cave)
    Z, U = [], []
    for p in pairs:
        st, xy = p.split('=')
        n = next(k for k in pos if k == st or k.endswith('.' + st))
        x, y = (float(v) for v in xy.split(','))
        Z.append(pos[n]); U.append(complex(x, -y))
    Z, U = np.array(Z), np.array(U)
    M = np.stack([Z, np.ones_like(Z)], 1)
    (A, B), *_ = np.linalg.lstsq(M, U, rcond=None)
    for p, m in zip(pairs, np.abs(M @ np.array([A, B]) - U) / abs(A)):
        print(f'  {p.split("=")[0]}: {m:.2f} m', file=sys.stderr)
    save(out, A, B, [int(v) for v in size.split(',')])


def overlay(cave, pic, fit, out):
    A, B, _ = load(fit)
    im = Image.open(pic).convert('RGB')
    d = ImageDraw.Draw(im)
    P = lambda z: ((A * z + B).real, -(A * z + B).imag)
    for a, b in legs(cave):
        d.line([P(a), P(b)], fill=(0, 140, 255), width=2)
    im.save(out)


if __name__ == '__main__':
    {'start': start, 'search': search, 'solve': solve, 'overlay': overlay}[sys.argv[1]](*sys.argv[2:])
