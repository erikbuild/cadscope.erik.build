#!/usr/bin/env python3
# ABOUTME: End-to-end tests for convert.sh on FreeCAD document (.FCStd) input using a probe assembly.
# ABOUTME: Runs FreeCAD and Blender for real; skipped when either app is missing.

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from glb import read_glb_json  # noqa: E402
from test_convert_y_up import BLENDER, CONVERT, FREECADCMD, gltf_world_extents_mm  # noqa: E402

# A visible group holding a 10x20x30 box, a hidden group whose only child is
# a hidden box (inside the first box's extents), and a shapeless top-level
# helper holding a coordinate system — the shape of an A2plus LCS_Collection.
MAKE_DOC = """
import FreeCAD
doc = FreeCAD.newDocument("probe")
frame = doc.addObject("App::DocumentObjectGroup", "Group")
frame.Label = "Frame"
box = doc.addObject("Part::Box", "Box")
box.Length = 10; box.Width = 20; box.Height = 30
frame.addObject(box)
optional = doc.addObject("App::DocumentObjectGroup", "Group001")
optional.Label = "Optional"
tucked = doc.addObject("Part::Box", "Tucked")
tucked.Length = 5; tucked.Width = 5; tucked.Height = 5
optional.addObject(tucked)
helper = doc.addObject("Part::FeaturePython", "Helper")
helper.addExtension("App::GeoFeatureGroupExtensionPython")
helper.addObject(doc.addObject("PartDesign::CoordinateSystem", "LCS"))
doc.recompute()
tucked.Visibility = False
optional.Visibility = False
doc.saveAs({path!r})
"""


def node_paths(glb_path):
    """Slash-joined name path of every node in the GLB's default scene."""
    g = read_glb_json(glb_path)
    paths = []

    def walk(index, prefix):
        node = g["nodes"][index]
        path = f"{prefix}/{node.get('name')}" if prefix else str(node.get("name"))
        paths.append(path)
        for child in node.get("children", []):
            walk(child, path)

    for root in g["scenes"][g.get("scene", 0)]["nodes"]:
        walk(root, "")
    return paths


@unittest.skipUnless(os.path.isfile(FREECADCMD) and os.path.isfile(BLENDER),
                     "FreeCAD and Blender required")
class TestConvertFreeCADDocument(unittest.TestCase):
    """convert.sh reads a .FCStd directly, exporting every part it holds."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.doc = os.path.join(cls.tmp, "probe.FCStd")
        subprocess.run(
            [FREECADCMD, "-c", MAKE_DOC.format(path=cls.doc)],
            capture_output=True, text=True, check=True,
        )
        assert os.path.isfile(cls.doc)
        cls.glb = os.path.join(cls.tmp, "probe.glb")
        cls.result = subprocess.run(
            [CONVERT, cls.doc, cls.glb],
            capture_output=True, text=True,
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout + self.result.stderr)

    def test_groups_keep_their_labels(self):
        self.assertTrue(any(p.endswith("Frame/Box") for p in node_paths(self.glb)),
                        node_paths(self.glb))

    def test_group_with_only_hidden_parts_is_exported(self):
        self.assertTrue(any(p.endswith("Optional/Tucked") for p in node_paths(self.glb)),
                        node_paths(self.glb))

    def test_shapeless_helpers_are_not_exported(self):
        names = {p.split("/")[-1] for p in node_paths(self.glb)}
        self.assertNotIn("Helper", names)
        self.assertNotIn("LCS", names)

    def test_document_z_is_up(self):
        self.assertEqual(gltf_world_extents_mm(self.glb), ([0, 0, -20], [10, 30, 0]))


@unittest.skipUnless(os.path.isfile(FREECADCMD) and os.path.isfile(BLENDER),
                     "FreeCAD and Blender required")
class TestConvertFreeCADDocumentYUp(unittest.TestCase):
    """--y-up is refused for .FCStd input rather than producing a half-rotated model."""

    def test_y_up_is_rejected(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        doc = os.path.join(tmp, "probe.FCStd")
        subprocess.run(
            [FREECADCMD, "-c", MAKE_DOC.format(path=doc)],
            capture_output=True, text=True, check=True,
        )
        glb = os.path.join(tmp, "probe.glb")
        result = subprocess.run(
            [CONVERT, "--y-up", doc, glb],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(os.path.exists(glb))


if __name__ == "__main__":
    unittest.main()
