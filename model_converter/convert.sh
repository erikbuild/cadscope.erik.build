#!/bin/bash
# ABOUTME: Converts a STEP file or FreeCAD document (.FCStd) to a Draco-compressed GLB.
# ABOUTME: Runs color extraction, FreeCAD export, and Blender compression in sequence.
# Convert STEP files or FreeCAD documents to Draco-compressed GLB with per-part colors.
#
# Three-stage pipeline:
#   1. Extract colors from STEP text (Python; skipped for .FCStd)
#   2. Import geometry + hierarchy (FreeCAD)
#   3. Apply colors, compress, export (Blender)
#
# Usage:
#   ./convert.sh input.step output.glb
#   ./convert.sh input.FCStd output.glb             # FreeCAD document; all parts exported, no colors
#   ./convert.sh --no-draco input.step output.glb
#   ./convert.sh --keep-temp input.step output.glb   # saves FreeCAD intermediate as _temp.glb
#   ./convert.sh --y-up input.step output.glb       # STEP modeled with Y as vertical (Fusion "Y up" designs)

set -euo pipefail

BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"
FREECADCMD="/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Parse flags
NO_DRACO=""
KEEP_TEMP=""
Y_UP=""
POSITIONAL=()
for arg in "$@"; do
    case "$arg" in
        --no-draco) NO_DRACO="--no-draco" ;;
        --keep-temp) KEEP_TEMP=1 ;;
        --y-up) Y_UP="--y-up" ;;
        *) POSITIONAL+=("$arg") ;;
    esac
done

if [ ${#POSITIONAL[@]} -lt 2 ]; then
    echo "Usage: $0 [--no-draco] [--keep-temp] [--y-up] <input.step|input.FCStd> <output.glb>"
    exit 1
fi

INPUT="${POSITIONAL[0]}"
OUTPUT="${POSITIONAL[1]}"
EXT="${INPUT##*.}"
EXT_LOWER="$(echo "$EXT" | tr '[:upper:]' '[:lower:]')"

case "$EXT_LOWER" in
    step|stp|fcstd)
        ;;
    *)
        echo "Error: unsupported format '.$EXT_LOWER' (only .step/.stp/.FCStd supported)"
        exit 1
        ;;
esac

# The --y-up rotation is applied to App::Part children, which FreeCAD
# document group trees don't have.
if [ "$EXT_LOWER" = "fcstd" ] && [ -n "$Y_UP" ]; then
    echo "Error: --y-up is not supported for .FCStd input"
    exit 1
fi

if [ ! -x "$FREECADCMD" ]; then
    echo "Error: FreeCAD not found at $FREECADCMD"
    echo "Install FreeCAD from https://www.freecad.org/downloads.php"
    exit 1
fi
if [ ! -x "$BLENDER" ]; then
    echo "Error: Blender not found at $BLENDER"
    exit 1
fi

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/convert.XXXXXX")"
TMPGLB="$WORKDIR/freecad.glb"
TMPJSON="$WORKDIR/colors.json"
# macOS bash 3.2 exits with this trap's status even after an unbound-variable
# error, so the trap fails the run unless the script reached its last line.
trap 'rm -rf "$WORKDIR"; [ "${FINISHED:-}" = 1 ] || exit 1' EXIT

COLORS_ARGS=()
echo "=== Stage 1/3: Extract colors ==="
if [ "$EXT_LOWER" = "fcstd" ]; then
    echo "Skipped: FreeCAD documents keep colors in GUI data that headless FreeCAD can't read"
elif python3 "$SCRIPT_DIR/extract_step_colors.py" "$INPUT" "$TMPJSON"; then
    COLORS_ARGS=(--colors "$TMPJSON")
else
    echo "Warning: color extraction failed, continuing without colors"
fi

echo ""
echo "=== Stage 2/3: CAD → GLB (FreeCAD) ==="
"$FREECADCMD" "$SCRIPT_DIR/cad_to_glb.py" -- $Y_UP "$INPUT" "$TMPGLB"

if [ -n "$KEEP_TEMP" ]; then
    TEMP_DEST="$(dirname "$OUTPUT")/_temp.glb"
    cp "$TMPGLB" "$TEMP_DEST"
    echo "Intermediate GLB saved to $TEMP_DEST"
fi

echo ""
echo "=== Stage 3/3: GLB → Draco GLB (Blender) ==="
"$BLENDER" --background --python-exit-code 1 --python "$SCRIPT_DIR/blender_export.py" -- $NO_DRACO ${COLORS_ARGS[@]+"${COLORS_ARGS[@]}"} "$TMPGLB" "$OUTPUT"
FINISHED=1
