#!/usr/bin/env bash
# What cave-viewer builds the 3D views from (web/caves.json), made from the survey data here:
#   the whole project, compiled as its own thconfig compiles it (cavern for the Survex caves, then
#   Therion for the whole): web/registry.3d and .lox, the area page's; each Survex cave's part of
#   it (tools/split3d.py); Rod's and Bath's walls cut from it, Goatchurch's from its LRUD;
#   Goatchurch's 2012 resurvey drawn as a plan, tied to the 2006 survey; and the UBSS's printed
#   surveys of Drunkard's, Pierre's and Bos as pictures, for their fits in web/drawn/.
#   (Read's, Tween Twins and Bos are Therion projects, which cave-viewer builds itself.)
# Needs survex (cavern), therion, pdftoppm (poppler) and Python with cave-viewer.
#   tools/build_inputs.sh
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
W="$ROOT/web"
PY=${PYTHON:-python3}

echo "cavern + therion: the whole project"
(cd "$ROOT" && cavern -o Burrington.3d Burrington.svx > "$W/registry.log" 2>&1 &&
  printf 'encoding utf-8\nsource Burrington.th\nexport model -fmt survex -o web/registry.3d\nexport model -o web/registry.lox\n' > thconfig.web-all &&
  therion thconfig.web-all >> "$W/registry.log" 2>&1) || { tail -20 "$W/registry.log"; exit 1; }

cave() {         # <name> <prefix>...: web/<name>.3d, its part of the whole
  local name=$1; shift
  echo "cavern: $name"
  (cd "$W" && "$PY" "$ROOT/tools/split3d.py" registry.3d "$name.svx" "$@" &&
    cavern -o "$name.3d" "$name.svx" > "$name.log" 2>&1) || { tail -20 "$W/$name.log"; exit 1; }
}
B=Burrington.burrington
cave goatchurch $B.westtwin.goatchurch
cave sidcot $B.westtwin.sidcot
cave rodsbath $B.swallets.rodsbath Burrington.BathEnt
cave drunkards $B.swallets.drunkards
cave avelines $B.avelines
cave pierres Burrington.PierresPot
cave lionels $B.lionels
cave easttwin $B.easttwinsparpot

# Rod's and Bath's walls: theirs out of the whole model (given it all, a cave's page shows its
# neighbours' walls too)
"$PY" "$ROOT/tools/loxclip.py" "$W/registry.lox" "$W/rodsbath.3d" "$W/rodsbath-walls.lox"
# Goatchurch's walls, from the LRUD in its Compass file (the Survex leaves them out)
"$PY" "$ROOT/tools/compass.py" "$W/goatchurch-walls.lox" "$W/goatchurch.3d" goatchurch. \
  "$ROOT/Goatchurch/Original_Data/Goatchurch.dat"
# Goatchurch's 2012 resurvey, tied to the 2006 survey and drawn as a plan on the grid
echo "therion: goatchurch 2012 plan"
"$ROOT/tools/goatchurch2012.sh" "$ROOT/Goatchurch" "$W/drawn/goatchurch2012.svg" > /dev/null
# Drunkard's, Pierre's and Bos's printed surveys (the UBSS's, CC BY-NC-SA 4.0), as pictures for
# their fits, their pen lines thickened (cave-viewer looks for ink at a quarter of the size)
echo "pdftoppm: Drunkard's, Pierre's and Bos's surveys"
pdftoppm -r 150 -png -singlefile "$W/drawn/Drunkards_Hole.pdf" "$W/drawn/drunkards"
pdftoppm -r 200 -png -singlefile "$W/drawn/Pierres_Pot_2013.pdf" "$W/drawn/pierres"
pdftoppm -r 150 -png -singlefile "$W/drawn/Bos_Swallet_1997.pdf" "$W/drawn/bos"
"$PY" -c 'import sys; from PIL import Image, ImageFilter
for f in sys.argv[1:]: Image.open(f).convert("RGB").filter(ImageFilter.MinFilter(5)).save(f)' "$W"/drawn/{drunkards,pierres,bos}.png
echo "Inputs built in web/"
