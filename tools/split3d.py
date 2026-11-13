#!/usr/bin/env python3
"""One cave's part of an area's compiled .3d, as a Survex file to build alone.

  split3d.py area.3d out.svx PREFIX [PREFIX ...]
  split3d.py area.3d out.svx --list stations.json SURVEYS NAME_PREFIX
      (the cave's stations listed instead, as compass2svx.py --stations lists them: those of
      the surveys whose names start with SURVEYS, named NAME_PREFIX + station in the .3d)

The UBSS's Burrington Area Survey comes compiled: the whole combe in one .3d,
many of its legs with no survey of their own (Therion's import of an older
Survex build). So a leg belongs to the cave whose stations are at its ends:
a station is at a leg's end where the two share a position, and a leg is the
cave's if a station at either end has one of the prefixes. Written as
cartesian legs (east, north, up: the positions exactly as compiled), each
connected part fixed at one of its stations, with the entrances and the
splay, surface and duplicate flags kept. Station names keep their survey
path from below the prefix's parent, so a passage's survey still names it.
"""
import os
import re
import subprocess
import sys
from collections import defaultdict


def dump(path):
    """(legs, stations) from dump3d: a leg (a, b, flags), a station (name, pos, flags)."""
    legs, stations, at = [], [], None
    for line in subprocess.run(['dump3d', path], capture_output=True, text=True, check=True).stdout.splitlines():
        f = line.split()
        if f[:1] == ['MOVE']:
            at = tuple(float(x) for x in f[1:4])
        elif f[:1] == ['LINE']:
            p = tuple(float(x) for x in f[1:4])
            legs.append((at, p, set(line[line.index(']') + 1:].split())))
            at = p
        elif f[:1] == ['NODE']:
            name = line[line.index('[') + 1:line.index(']')]
            stations.append((name, tuple(float(x) for x in f[1:4]), set(line[line.index(']') + 1:].split())))
    return legs, stations


def main(src, out, prefixes):
    legs, stations = dump(src)
    names = defaultdict(list)
    for n, p, fl in stations:
        names[p].append(n)
    if prefixes[0] == '--list':
        import json
        lists, surveys, parent = json.load(open(prefixes[1])), prefixes[2], prefixes[3]
        listed = {parent + st for k, v in lists.items() if k.startswith(surveys) for st in v}
        mine = lambda n: n in listed
        prefixes = [f'the {surveys} surveys']
    else:
        mine = lambda n: any(n == x or n.startswith(x + '.') for x in prefixes)
        # names below the prefixes' common parent, in Survex's characters
        parent = os.path.commonprefix([x.rsplit('.', 1)[0] + '.' for x in prefixes])
        parent = parent[:parent.rfind('.') + 1]
    clean = lambda n: '.'.join(re.sub(r'[^A-Za-z0-9_-]', '_', s) for s in n[len(parent):].split('.'))
    keep, ids, anon = [], {}, 0

    def sid(p):
        nonlocal anon
        if p not in ids:
            ns = [n for n in names.get(p, []) if mine(n)]
            if ns:
                ids[p] = clean(min(ns, key=len))
            else:                                   # a splay's far end
                anon += 1
                ids[p] = f'splay{anon}'
        return ids[p]
    for a, b, fl in legs:
        if a is None or a == b:                     # (and a 0 m splay: nothing to draw)
            continue
        if any(mine(n) for n in names.get(a, []) + names.get(b, [])):
            keep.append((a, b, fl))
    if not keep:
        sys.exit(f'{src}: no legs under {", ".join(prefixes)}')
    # one fix for each connected part
    up = {}

    def find(p):
        while up.setdefault(p, p) != p:
            up[p] = up[up[p]]
            p = up[p]
        return p
    for a, b, fl in keep:
        up[find(a)] = find(b)
    roots = {}
    for a, b, fl in keep:
        for p in (a, b):
            if p in names and find(p) not in roots:
                roots[find(p)] = p
    lines = [f'; {os.path.basename(out)}: {", ".join(prefixes)} from {os.path.basename(src)} (made by split3d.py)',
             '*begin', '*case preserve', '*data cartesian from to easting northing altitude', '*units easting northing altitude metres']
    for p in roots.values():
        lines.append(f'*fix {sid(p)} {p[0]:.2f} {p[1]:.2f} {p[2]:.2f}')
    for n, p, fl in stations:
        if 'ENTRANCE' in fl and mine(n) and p in ids or 'ENTRANCE' in fl and mine(n) and any(p in (a, b) for a, b, _ in keep):
            lines.append(f'*entrance {sid(p)}')
    flags = None
    for a, b, fl in keep:
        want = ' '.join(x.lower() for x in ('SPLAY', 'SURFACE', 'DUPLICATE') if x in fl)
        if want != flags:
            lines.append('*flags not splay not surface not duplicate' + (f'\n*flags {want}' if want else ''))
            flags = want
        lines.append(f'{sid(a)} {sid(b)} {b[0] - a[0]:.2f} {b[1] - a[1]:.2f} {b[2] - a[2]:.2f}')
    lines.append('*end')
    open(out, 'w').write('\n'.join(lines) + '\n')
    print(f'{out}: {len(keep)} legs, {len(roots)} part(s)', file=sys.stderr)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
