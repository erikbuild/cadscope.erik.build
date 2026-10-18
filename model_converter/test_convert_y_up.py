#!/usr/bin/env python3
# ABOUTME: End-to-end tests for convert.sh axis handling using a probe box STEP, plus the shared
# ABOUTME: FreeCAD probe-script runner; runs FreeCAD and Blender for real, skipped when missing.

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from glb import read_glb_json  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CONVERT = os.path.join(HERE, "convert.sh")
FREECADCMD = "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"

MAKE_BOX = """
import FreeCAD, Part, Import
doc = FreeCAD.newDocument("probe")
part = doc.addObject("App::Part", "Probe")
box = doc.addObject("Part::Box", "Box")
box.Length = 10; box.Width = 20; box.Height = 30
part.addObject(box)
doc.recompute()
Import.export([part], {path!r})
"""


def run_freecad_script(script, workdir):
    """Run a FreeCAD script from a file in workdir; raise if it fails.

    freecadcmd also opens its command-line text as files, so the script goes
    in a file rather than through -c, and it reports a script's exception
    without a failing exit code, so its output is checked too.
    """
    path = os.path.join(workdir, "make_probe.py")
    with open(path, "w") as f:
        f.write(script)
    result = subprocess.run([FREECADCMD, path], capture_output=True, text=True)
    output = result.stdout + result.stderr
    if result.returncode != 0 or "Exception while processing file" in output:
        raise RuntimeError(f"FreeCAD script failed:\n{output}")


def _node_matrix(node):
    """Column-major glTF node transform as a row-major 4x4 list."""
    if "matrix" in node:
        m = node["matrix"]
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    t = node.get("translation", [0, 0, 0])
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    s = node.get("scale", [1, 1, 1])
    rot = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
           [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
           [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[rot[r][c] * s[c] for c in range(3)] + [t[r]] for r in range(3)] + [[0, 0, 0, 1]]


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def gltf_world_extents_mm(glb_path):
    """World-space (min, max) over every mesh in the GLB, in millimetres."""
    g = read_glb_json(glb_path)
    lo, hi = [float("inf")] * 3, [float("-inf")] * 3

    def walk(index, parent):
        node = g["nodes"][index]
        m = _mul(parent, _node_matrix(node))
        if "mesh" in node:
            for prim in g["meshes"][node["mesh"]]["primitives"]:
                a = g["accessors"][prim["attributes"]["POSITION"]]
                for x in (a["min"][0], a["max"][0]):
                    for y in (a["min"][1], a["max"][1]):
                        for z in (a["min"][2], a["max"][2]):
                            w = [m[r][0] * x + m[r][1] * y + m[r][2] * z + m[r][3] for r in range(3)]
                            for k in range(3):
                                lo[k] = min(lo[k], w[k])
                                hi[k] = max(hi[k], w[k])
        for child in node.get("children", []):
            walk(child, m)

    identity = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    for root in g["scenes"][g.get("scene", 0)]["nodes"]:
        walk(root, identity)
    return ([round(v * 1000) for v in lo], [round(v * 1000) for v in hi])


@unittest.skipUnless(os.path.isfile(FREECADCMD), "FreeCAD required")
class TestRunFreeCADScript(unittest.TestCase):
    """Probe scripts run as files and fail the test when they raise."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_long_lines_run(self):
        # freecadcmd treats command-line text as file names, and a run of more
        # than 255 characters without a slash crashes it.
        marker = os.path.join(self.tmp, "marker.txt")
        run_freecad_script("# " + "a" * 300 + "\n" + f"open({marker!r}, 'w').write('ok')\n", self.tmp)
        with open(marker) as f:
            self.assertEqual(f.read(), "ok")

    def test_script_errors_fail_loudly(self):
        # freecadcmd exits 0 after an exception in a script file.
        with self.assertRaises(RuntimeError) as cm:
            run_freecad_script('raise RuntimeError("probe failed")\n', self.tmp)
        self.assertIn("probe failed", str(cm.exception))


@unittest.skipUnless(os.path.isfile(FREECADCMD) and os.path.isfile(BLENDER),
                     "FreeCAD and Blender required")
class TestConvertAxes(unittest.TestCase):
    """A 10x20x30 (X,Y,Z) box shows which STEP axis lands where in glTF."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.step = os.path.join(cls.tmp, "box.step")
        run_freecad_script(MAKE_BOX.format(path=cls.step), cls.tmp)
        assert os.path.isfile(cls.step)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _convert(self, *flags):
        out = os.path.join(self.tmp, "out.glb")
        if os.path.exists(out):
            os.remove(out)
        result = subprocess.run(
            [CONVERT, *flags, self.step, out],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return gltf_world_extents_mm(out)

    def test_default_treats_step_z_as_up(self):
        lo, hi = self._convert()
        self.assertEqual((lo, hi), ([0, 0, -20], [10, 30, 0]))

    def test_y_up_flag_treats_step_y_as_up(self):
        lo, hi = self._convert("--y-up")
        self.assertEqual((lo, hi), ([0, 0, 0], [10, 20, 30]))


@unittest.skipUnless(os.path.isfile(FREECADCMD) and os.path.isfile(BLENDER),
                     "FreeCAD and Blender required")
class TestConvertStageFailures(unittest.TestCase):
    """convert.sh exits non-zero whenever a stage or the script itself fails."""

    LEFTOVER = "/tmp/convert_step_XXXXXX.glb"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.step = os.path.join(cls.tmp, "box.step")
        run_freecad_script(MAKE_BOX.format(path=cls.step), cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_blender_failure_fails(self):
        # Blender creates missing output folders, but not under a file.
        blocker = os.path.join(self.tmp, "blocker")
        open(blocker, "w").close()
        result = subprocess.run([CONVERT, self.step, os.path.join(blocker, "out.glb")],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_leftover_temp_file_does_not_block(self):
        if os.path.exists(self.LEFTOVER):
            self.skipTest(f"{self.LEFTOVER} already exists")
        open(self.LEFTOVER, "w").close()
        self.addCleanup(os.remove, self.LEFTOVER)
        out = os.path.join(self.tmp, "leftover.glb")
        result = subprocess.run([CONVERT, self.step, out], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(os.path.isfile(out))

    def test_script_error_after_trap_fails(self):
        # macOS bash 3.2 exits with the EXIT trap's status after an
        # unbound-variable error, so the trap has to report failure itself.
        with open(CONVERT) as f:
            lines = f.readlines()
        trap = next(i for i, line in enumerate(lines) if line.startswith("trap "))
        lines.insert(trap + 1, ': "$UNSET_PROBE"\n')
        broken = os.path.join(self.tmp, "convert_broken.sh")
        with open(broken, "w") as f:
            f.writelines(lines)
        result = subprocess.run(["/bin/bash", broken, self.step, os.path.join(self.tmp, "b.glb")],
                                capture_output=True, text=True)
        self.assertIn("UNSET_PROBE", result.stderr)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
