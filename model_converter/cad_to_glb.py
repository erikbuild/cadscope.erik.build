# ABOUTME: FreeCAD script that turns a STEP file or FreeCAD document into an uncompressed GLB.
# ABOUTME: Stage 2 of the CAD→GLB conversion pipeline (see convert.sh).
"""
FreeCAD Python script: Convert a STEP file or FreeCAD document (.FCStd) to GLB
with full assembly hierarchy.

Usage (run via FreeCAD's CLI):
    freecadcmd cad_to_glb.py -- [--y-up] input.step|input.FCStd output.glb

--y-up: the STEP was modeled with Y as the vertical axis; the assembly is
rotated so Y becomes Z before export, matching the Z-up convention the exporter assumes.

A .FCStd document is opened directly and every part in it is exported,
including parts saved hidden. Parts it links in from other files are exported
too, and conversion stops if a linked file can't be found.

Produces an uncompressed GLB that preserves the STEP assembly tree or the
document's group tree. Pipe through Blender for Draco compression (see convert.sh).
"""

import FreeCAD
import Import
import io
import sys
import os
import time
import traceback
import xml.etree.ElementTree as ET
import zipfile

USAGE = "Usage: freecadcmd cad_to_glb.py -- [--y-up] input.step|input.FCStd output.glb"


def fail(message):
    """Print message and exit with status 1."""
    print(message)
    # freecadcmd drops unflushed output when a script exits.
    sys.stdout.flush()
    sys.exit(1)


def parse_args():
    """Parse arguments after '--' in the command line."""
    try:
        sep = sys.argv.index("--")
    except ValueError:
        fail(f"Error: pass arguments after '--'\n{USAGE}")

    args = sys.argv[sep + 1:]
    paths = [a for a in args if not a.startswith("--")]
    y_up = "--y-up" in args

    if len(paths) < 2:
        fail(f"Error: need input and output paths\n{USAGE}")

    return os.path.abspath(paths[0]), os.path.abspath(paths[1]), y_up


def carries_geometry(obj):
    """True if obj, or anything grouped under it, has faces the glTF writer meshes.

    Datum features (coordinate systems, planes) report faces but are never
    triangulated, so on their own they export as empty nodes.
    """
    if obj.isDerivedFrom("Part::Datum"):
        return False
    shape = getattr(obj, "Shape", None)
    if shape is not None and not shape.isNull() and shape.Faces:
        return True
    return any(carries_geometry(child) for child in getattr(obj, "Group", []))


def links_to_something(obj):
    """True if obj's link names a target object, loaded or not.

    A link whose target file is missing still records the target's name; a
    link saved without a target, or a plain link (which can't point into
    another file), names nothing a missing file could hold.
    """
    content = zipfile.ZipFile(io.BytesIO(obj.dumpPropertyContent("LinkedObject")))
    xlink = ET.fromstring(content.read("Persistence.xml")).find("XLink")
    return xlink is not None and bool(xlink.get("name"))


def unresolved_links(documents):
    """Name each link in documents whose target wasn't loaded, as "Document/Label".

    A link into a file that isn't at its saved relative path opens with no
    target, and the exporter would silently leave its parts out. Links saved
    without a target are not counted.
    """
    return [f"{doc.Label}/{obj.Label}"
            for doc in documents for obj in doc.Objects
            if "LinkedObject" in obj.PropertiesList and obj.LinkedObject is None
            and links_to_something(obj)]


def main():
    input_path, output_path, y_up = parse_args()

    if not os.path.isfile(input_path):
        fail(f"Error: input file not found: {input_path}")

    print(f"\n--- CAD to GLB (FreeCAD) ---")
    print(f"Input:  {input_path}")
    print(f"Output: {output_path}\n")

    is_document = input_path.lower().endswith(".fcstd")
    t0 = time.time()
    if is_document:
        print("Opening FreeCAD document...")
        doc = FreeCAD.openDocument(input_path)
        # Opening a document also loads the documents it links to, and those
        # carry links of their own.
        broken = unresolved_links(FreeCAD.listDocuments().values())
        if broken:
            fail("Error: unresolved links (are the linked files at their saved relative paths?)\n"
                 + "\n".join(f"  {name}" for name in broken))
    else:
        print("Importing STEP...")
        doc = FreeCAD.newDocument("convert")
        Import.insert(input_path, "convert")
    t1 = time.time()
    print(f"Import took {t1 - t0:.1f}s, {len(doc.Objects)} objects")

    # Tessellate all shapes so glTF export includes geometry
    print("Tessellating...")
    count = 0
    for obj in doc.Objects:
        if hasattr(obj, "Shape") and obj.Shape.Faces:
            obj.Shape.tessellate(0.1)
            count += 1
    t2 = time.time()
    print(f"Tessellated {count} shapes in {t2 - t1:.1f}s")

    # Find root App::Part objects for export
    roots = [o for o in doc.Objects if o.TypeId == "App::Part" and not o.InList]
    if not roots:
        roots = [o for o in doc.Objects if not o.InList and carries_geometry(o)]
    print(f"Exporting roots: {[r.Label for r in roots]}")

    # The glTF exporter drops any group with no visible child, so every object
    # in a FreeCAD document is shown before export (the document is never
    # saved). Which parts start hidden is the model spec's job.
    if is_document:
        for obj in doc.Objects:
            obj.Visibility = True

    # The glTF exporter drops the Placement of the root containers it is
    # handed, so the upright rotation goes on each root's direct children.
    if y_up:
        print("Rotating so STEP Y becomes Z (--y-up)")
        upright = FreeCAD.Placement(FreeCAD.Vector(), FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90))
        for root in roots:
            for child in getattr(root, "Group", [root]):
                if child.TypeId != "App::Origin" and hasattr(child, "Placement"):
                    child.Placement = upright.multiply(child.Placement)
        doc.recompute()

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Export to GLB (uncompressed — Blender adds Draco later)
    print("Exporting GLB...")
    Import.export(roots, output_path)
    t3 = time.time()
    print(f"Export took {t3 - t2:.1f}s")

    input_mb = os.path.getsize(input_path) / (1024 * 1024)
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\nDone!")
    print(f"  Input:   {input_mb:.1f} MB")
    print(f"  Output:  {size_mb:.1f} MB")


# freecadcmd reports an uncaught script exception but still exits 0, and after
# the script it opens its trailing arguments as files; exiting explicitly
# avoids both.
try:
    main()
except Exception:
    fail("Error: conversion failed\n" + traceback.format_exc())
sys.stdout.flush()
sys.exit(0)
