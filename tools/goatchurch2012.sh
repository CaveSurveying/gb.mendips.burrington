#!/usr/bin/env bash
# Goatchurch's 2012 DistoX resurvey (the registry's Burrington/Goatchurch, three trips round the
# entrance series, drawn in Therion) as a plan on the grid, for Goatchurch's 2D plan: the
# resurvey has no fix of its own, so a copy of it is tied to the 2006 survey here.
#   goatchurch2012.sh <the registry's Goatchurch folder> <out.svg>
# The tie: its main entrance (1.0) at ST 47589.60 58232.27 152.28 and its bearings turned 5.5
# degrees anticlockwise (declination -5.5), where its legs lie closest to the 2006 survey's
# (median 0.7 m; found by search, see docs/notes.md).
set -euo pipefail
SRC=$1 OUT=$2
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cp -R "$SRC"/Goatchurch.th "$SRC"/GoatchurchMainEntrance1 "$SRC"/GoatchurchSecondJunction1 "$SRC"/GoatchurchSecondJunction2 "$WORK"/
# the turn, in each trip's centreline
for f in "$WORK"/Goatchurch*/Goatchurch*.th; do
  sed -i.bak -E 's/^([[:space:]]*)centreline[[:space:]]*$/\1centreline\n\1  declination -5.5 deg/' "$f"
done
cat > "$WORK/tied.th" <<'EOF'
encoding utf-8
survey Goatchurch2012 -title "Goatchurch Cavern, the 2012 resurvey"
input Goatchurch.th
centreline
  cs OSGB:ST
  fix 1.0@GoatchurchMainEntrance1.Goatchurch 47589.60 58232.27 152.28
endcentreline
endsurvey
EOF
# drawn as cave-viewer draws a Therion plan (north grid, 1:500, the grid's coordinates on it)
cat > "$WORK/thconfig" <<EOF
encoding utf-8
source tied.th
select GoatchurchM@Goatchurch.Goatchurch2012
export map -proj plan -fmt svg -layout web -o $OUT
layout web
  north grid
  scale 1 500
  colour map-bg transparent
  colour map-fg altitude
  debug off
  map-header 0 0 nw
  map-header-bg off
  colour-legend on
  legend off
  statistics explo off
  statistics topo all
  statistics carto all
  statistics copyright all
  map-comment "Goatchurch Cavern: the 2012 resurvey (Stuart Alldred, Simon Hadfield, Sarah Rae and others; Cave Registry Data Archive, Burrington/Goatchurch), tied to the 2006 survey"
  grid bottom
  grid-size 100 100 100 m
  grid-coords border
endlayout
EOF
(cd "$WORK" && therion thconfig > therion.log 2>&1) || { tail -20 "$WORK/therion.log"; exit 1; }
grep -E "average loop|warning" "$WORK/therion.log" | head -3 || true
echo "$OUT"
