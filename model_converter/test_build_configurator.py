#!/usr/bin/env python3
# ABOUTME: Tests for build_configurator.py — scaffold-mode CLI behavior.
# ABOUTME: Runs the CLI as a subprocess against the Positron GLB fixture.

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
GLB_PATH = os.path.join(REPO_ROOT, "models", "Positron_v3.2.2.glb")
SCRIPT = os.path.join(os.path.dirname(__file__), "build_configurator.py")


@unittest.skipUnless(os.path.isfile(GLB_PATH), "Positron GLB fixture not present")
class TestScaffoldMode(unittest.TestCase):
    """Scaffold mode mirrors the legacy dump_parts.py behavior."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.glb_copy = os.path.join(self.tmp, "Positron.glb")
        shutil.copyfile(GLB_PATH, self.glb_copy)
        self.spec = os.path.join(self.tmp, "Positron.spec.yaml")
        self.scaffold = os.path.join(self.tmp, "Positron.scaffold.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *extra_args):
        return subprocess.run(
            [sys.executable, SCRIPT, self.glb_copy, *extra_args],
            capture_output=True, text=True, check=True,
        )

    def test_emits_scaffold_with_expected_shape(self):
        self._run()
        self.assertTrue(os.path.isfile(self.scaffold))
        with open(self.scaffold) as f:
            data = json.load(f)
        self.assertIn("_groups", data)
        self.assertIn("_parts", data)
        self.assertIn("_nodes", data)
        self.assertIsInstance(data["_groups"], list)
        self.assertIsInstance(data["_parts"], list)
        self.assertIsInstance(data["_nodes"], dict)
        # Positron has many parts; assert non-trivial.
        self.assertGreater(len(data["_nodes"]), 100)

    def test_emits_starter_spec_when_absent(self):
        self.assertFalse(os.path.isfile(self.spec))
        self._run()
        self.assertTrue(os.path.isfile(self.spec))
        import yaml
        with open(self.spec) as f:
            data = yaml.safe_load(f)
        self.assertIn("model", data)
        self.assertEqual(data["model"]["glb"], "Positron.glb")
        self.assertIn("palette", data)
        self.assertEqual(len(data["palette"]), 6)
        # autoAssign body is comments-only → parses as None.
        self.assertIn(data.get("autoAssign"), (None, []))
        self.assertEqual(data["nodes"], {})

    def test_does_not_overwrite_existing_spec(self):
        sentinel = "model: { name: Keep, glb: Positron.glb }\npalette: { X: { color: '#abcdef' } }\n"
        with open(self.spec, "w") as f:
            f.write(sentinel)
        self._run()
        with open(self.spec) as f:
            self.assertEqual(f.read(), sentinel)

    def test_stub_spec_parses_with_spec_module(self):
        """The emitted stub is a valid spec the parser accepts unchanged."""
        self._run()
        sys.path.insert(0, os.path.dirname(SCRIPT))
        try:
            from spec import parse_file
        finally:
            sys.path.pop(0)
        s = parse_file(self.spec)
        self.assertEqual(s.glb_path, "Positron.glb")
        self.assertIn("Main", s.palette)
        self.assertEqual(s.auto_assign, [])
        self.assertEqual(s.nodes, {})

    def test_overwrites_scaffold_each_run(self):
        """Scaffold is the reference dump — always regenerated."""
        self._run()
        with open(self.scaffold) as f:
            first = f.read()
        # Mutate
        with open(self.scaffold, "w") as f:
            f.write("{}\n")
        self._run()
        with open(self.scaffold) as f:
            second = f.read()
        self.assertEqual(first, second)

    def test_o_flag_overrides_output_base(self):
        custom = os.path.join(self.tmp, "alt.colors.json")
        subprocess.run(
            [sys.executable, SCRIPT, self.glb_copy, "-o", custom],
            capture_output=True, text=True, check=True,
        )
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "alt.scaffold.json")))
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "alt.spec.yaml")))

    def test_scaffold_only_flag_accepted(self):
        """--scaffold-only forces scaffold + spec-stub emission even with a spec present."""
        result = self._run("--scaffold-only")
        self.assertEqual(result.returncode, 0)
        self.assertTrue(os.path.isfile(self.scaffold))
        self.assertTrue(os.path.isfile(self.spec))

    def test_missing_glb_returns_nonzero(self):
        result = subprocess.run(
            [sys.executable, SCRIPT, "/nonexistent/foo.glb"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)


try:
    import yaml as _yaml  # noqa: F401
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


@unittest.skipUnless(YAML_AVAILABLE and os.path.isfile(GLB_PATH),
                     "PyYAML or GLB fixture not present")
class TestFullModeIntegration(unittest.TestCase):
    """Full mode: spec.yaml beside GLB drives generation of all three outputs."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.glb = os.path.join(self.tmp, "Model.glb")
        self.spec = os.path.join(self.tmp, "Model.spec.yaml")
        shutil.copyfile(GLB_PATH, self.glb)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_spec(self, body):
        with open(self.spec, "w") as f:
            f.write(body)

    def test_emits_three_output_files(self):
        self._write_spec("""
model:
  name: "Test"
  glb: Model.glb
palette:
  Main: { color: "#ff0000" }
""")
        subprocess.run([sys.executable, SCRIPT, self.glb],
                       capture_output=True, text=True, check=True)
        for ext in (".scaffold.json", ".colors.json", ".manifest.json"):
            self.assertTrue(os.path.isfile(os.path.join(self.tmp, "Model" + ext)),
                            f"missing Model{ext}")

    def test_full_mode_overwrites_colors(self):
        """In full mode, colors.json is regenerated each run (unlike scaffold mode)."""
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette: { A: { color: '#aaaaaa' } }
""")
        subprocess.run([sys.executable, SCRIPT, self.glb],
                       capture_output=True, text=True, check=True)
        with open(os.path.join(self.tmp, "Model.colors.json")) as f:
            first = json.load(f)
        # Edit the spec, regenerate
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette: { B: { color: '#bbbbbb' } }
""")
        subprocess.run([sys.executable, SCRIPT, self.glb],
                       capture_output=True, text=True, check=True)
        with open(os.path.join(self.tmp, "Model.colors.json")) as f:
            second = json.load(f)
        self.assertNotEqual(first, second)
        self.assertIn("B", second["palette"])
        self.assertNotIn("A", second["palette"])

    def test_manifest_contains_glb_and_options(self):
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette: { Main: { color: '#fff' } }
options:
  carriage:
    label: Carriage
    choices:
      - { id: a, label: A, default: true }
      - { id: b, label: B }
""")
        subprocess.run([sys.executable, SCRIPT, self.glb],
                       capture_output=True, text=True, check=True)
        with open(os.path.join(self.tmp, "Model.manifest.json")) as f:
            manifest = json.load(f)
        self.assertEqual(manifest["glb"], "Model.glb")
        self.assertIn("carriage", manifest["configOptions"])

    def test_manifest_carries_option_and_choice_descriptions(self):
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette: { Main: { color: '#fff' } }
options:
  carriage:
    label: Carriage
    description: "Which carriage variant ships."
    choices:
      - { id: a, label: A, description: "Original.", default: true }
      - { id: b, label: B }
  hexCowl:
    label: Hex
    description: "Patterned top cowl."
    type: bool
    default: false
""")
        subprocess.run([sys.executable, SCRIPT, self.glb],
                       capture_output=True, text=True, check=True)
        with open(os.path.join(self.tmp, "Model.manifest.json")) as f:
            manifest = json.load(f)
        carriage = manifest["configOptions"]["carriage"]
        self.assertEqual(carriage["description"], "Which carriage variant ships.")
        self.assertEqual(carriage["choices"][0]["description"], "Original.")
        self.assertNotIn("description", carriage["choices"][1])
        self.assertEqual(manifest["configOptions"]["hexCowl"]["description"],
                         "Patterned top cowl.")

    def test_manifest_default_selection_type_is_radio(self):
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette: { Main: { color: '#fff' } }
options:
  carriage:
    choices:
      - { id: a, default: true }
""")
        subprocess.run([sys.executable, SCRIPT, self.glb],
                       capture_output=True, text=True, check=True)
        with open(os.path.join(self.tmp, "Model.manifest.json")) as f:
            manifest = json.load(f)
        self.assertEqual(manifest["configOptions"]["carriage"]["type"], "radio")

    def test_manifest_propagates_dropdown_and_unknown_type(self):
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette: { Main: { color: '#fff' } }
options:
  short:
    type: dropdown
    choices:
      - { id: a, default: true }
  custom:
    type: image_grid
    choices:
      - { id: b, default: true }
""")
        subprocess.run([sys.executable, SCRIPT, self.glb],
                       capture_output=True, text=True, check=True)
        with open(os.path.join(self.tmp, "Model.manifest.json")) as f:
            manifest = json.load(f)
        self.assertEqual(manifest["configOptions"]["short"]["type"], "dropdown")
        self.assertEqual(manifest["configOptions"]["custom"]["type"], "image_grid")

    def test_manifest_omits_description_when_absent(self):
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette: { Main: { color: '#fff' } }
options:
  carriage:
    choices:
      - { id: a, default: true }
""")
        subprocess.run([sys.executable, SCRIPT, self.glb],
                       capture_output=True, text=True, check=True)
        with open(os.path.join(self.tmp, "Model.manifest.json")) as f:
            manifest = json.load(f)
        opt = manifest["configOptions"]["carriage"]
        self.assertNotIn("description", opt)
        self.assertNotIn("description", opt["choices"][0])

    def test_unknown_node_path_emits_warning(self):
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette: { Main: { color: '#fff' } }
nodes:
  Definitely_Does_Not_Exist: { displayName: "Ghost" }
""")
        result = subprocess.run([sys.executable, SCRIPT, self.glb],
                                capture_output=True, text=True, check=True)
        self.assertIn("Definitely_Does_Not_Exist", result.stderr)

    def test_manifest_carries_downloads(self):
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette: { Main: { color: '#fff' } }
options:
  pulley:
    choices:
      - { id: a, default: true }
      - { id: b }
downloads:
  base: "https://example.com/STLs/"
  always: [ "Tools/a.stl" ]
  groups:
    - when: { pulley: b }
      files: [ "X/b.stl" ]
""")
        subprocess.run([sys.executable, SCRIPT, self.glb],
                       capture_output=True, text=True, check=True)
        with open(os.path.join(self.tmp, "Model.manifest.json")) as f:
            manifest = json.load(f)
        self.assertEqual(manifest["downloads"]["base"], "https://example.com/STLs/")
        self.assertEqual(manifest["downloads"]["always"], ["Tools/a.stl"])
        self.assertEqual(manifest["downloads"]["groups"][0]["when"], {"pulley": "b"})

    def test_manifest_omits_downloads_when_absent(self):
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette: { Main: { color: '#fff' } }
""")
        subprocess.run([sys.executable, SCRIPT, self.glb],
                       capture_output=True, text=True, check=True)
        with open(os.path.join(self.tmp, "Model.manifest.json")) as f:
            manifest = json.load(f)
        self.assertNotIn("downloads", manifest)

    def test_palette_show_in_tree_round_trips_to_colors_json(self):
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette:
  Main:   { color: '#fff' }
  Hidden: { color: '#222', showInTree: false }
""")
        subprocess.run([sys.executable, SCRIPT, self.glb],
                       capture_output=True, text=True, check=True)
        with open(os.path.join(self.tmp, "Model.colors.json")) as f:
            colors = json.load(f)
        self.assertIs(colors["palette"]["Hidden"]["showInTree"], False)
        self.assertNotIn("showInTree", colors["palette"]["Main"])

    def test_node_show_in_tree_false_emitted_in_colors_json(self):
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette: { Main: { color: '#fff' } }
nodes:
  Some_Hidden_Path: { showInTree: false }
""")
        subprocess.run([sys.executable, SCRIPT, self.glb],
                       capture_output=True, text=True, check=True)
        with open(os.path.join(self.tmp, "Model.colors.json")) as f:
            colors = json.load(f)
        self.assertIn("Some_Hidden_Path", colors["nodes"])
        self.assertIs(colors["nodes"]["Some_Hidden_Path"]["showInTree"], False)

    def test_node_show_in_tree_default_not_emitted(self):
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette: { Main: { color: '#fff' } }
nodes:
  Some_Path: { displayName: "Visible" }
""")
        subprocess.run([sys.executable, SCRIPT, self.glb],
                       capture_output=True, text=True, check=True)
        with open(os.path.join(self.tmp, "Model.colors.json")) as f:
            colors = json.load(f)
        self.assertNotIn("showInTree", colors["nodes"]["Some_Path"])


@unittest.skipUnless(YAML_AVAILABLE and os.path.isfile(GLB_PATH),
                     "PyYAML or GLB fixture not present")
class TestCheckMode(unittest.TestCase):
    """--check parses + reports without writing any files."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.glb = os.path.join(self.tmp, "Model.glb")
        self.spec = os.path.join(self.tmp, "Model.spec.yaml")
        shutil.copyfile(GLB_PATH, self.glb)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_spec(self, body):
        with open(self.spec, "w") as f:
            f.write(body)

    def test_check_writes_no_files(self):
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette: { Frame: { color: '#444' } }
autoAssign:
  - { match: '*', category: Frame }
""")
        before = set(os.listdir(self.tmp))
        result = subprocess.run([sys.executable, SCRIPT, "--check", self.glb],
                                capture_output=True, text=True, check=True)
        after = set(os.listdir(self.tmp))
        self.assertEqual(before, after, "no new files should be written")
        self.assertIn("VALID", result.stdout)
        self.assertIn("direct:", result.stdout)
        self.assertIn("effective:", result.stdout)
        self.assertIn("autoAssign:", result.stdout)

    def test_check_missing_spec_exits_nonzero(self):
        result = subprocess.run([sys.executable, SCRIPT, "--check", self.glb],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires a sibling", result.stderr.lower())

    def test_check_invalid_spec_exits_nonzero(self):
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette: { Main: { color: '#fff' } }
autoAssign:
  - { match: '*', category: BogusCategory }
""")
        result = subprocess.run([sys.executable, SCRIPT, "--check", self.glb],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("INVALID", result.stdout)

    def test_check_zero_match_rule_flagged_in_output(self):
        self._write_spec("""
model: { name: T, glb: Model.glb }
palette: { Frame: { color: '#444' } }
autoAssign:
  - { match: 'NeverMatchesAnything*', category: Frame }
""")
        result = subprocess.run([sys.executable, SCRIPT, "--check", self.glb],
                                capture_output=True, text=True, check=True)
        self.assertIn("zero-match", result.stdout)


@unittest.skipUnless(YAML_AVAILABLE and os.path.isfile(GLB_PATH),
                     "PyYAML or GLB fixture not present")
class TestPositronColorsRegression(unittest.TestCase):
    """A spec matching the existing hand-written Positron sidecar produces the same content."""

    def test_structural_equivalence(self):
        """Generated colors.json is structurally equivalent to the committed hand-written one."""
        existing_path = os.path.join(REPO_ROOT, "models", "Positron_v3.2.2.colors.json")
        with open(existing_path) as f:
            existing = json.load(f)

        with tempfile.TemporaryDirectory() as tmp:
            glb = os.path.join(tmp, "Positron.glb")
            spec = os.path.join(tmp, "Positron.spec.yaml")
            shutil.copyfile(GLB_PATH, glb)
            with open(spec, "w") as f:
                f.write("""\
model:
  name: "Positron v3.2.2"
  glb: Positron.glb
palette:
  Main:               { color: "#FF6600" }
  Accent:             { color: "#00AAFF" }
  Extrusions:         { color: "#888888", metalness: 0.8, showInPicker: false }
  Opaque Panels:      { color: "#333333", showInPicker: false }
  Transparent Panels: { color: "#555555", showInPicker: false }
  Glass:              { color: "#ccddee", metalness: 0.1, opacity: 0.15, showInPicker: false }
autoAssign: []
""")
            subprocess.run([sys.executable, SCRIPT, glb],
                           capture_output=True, text=True, check=True)
            with open(os.path.join(tmp, "Positron.colors.json")) as f:
                generated = json.load(f)

        self.assertEqual(generated, existing)


@unittest.skipUnless(YAML_AVAILABLE and os.path.isfile(GLB_PATH),
                     "PyYAML or GLB fixture not present")
class TestShimForcesScaffoldOnly(unittest.TestCase):
    """The dump_parts.py shim runs scaffold-only even if a sibling .spec.yaml exists."""

    def test_shim_does_not_emit_manifest_when_spec_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            glb = os.path.join(tmp, "Model.glb")
            spec = os.path.join(tmp, "Model.spec.yaml")
            shutil.copyfile(GLB_PATH, glb)
            sentinel = ("model: { name: T, glb: Model.glb }\n"
                        "palette: { Solo: { color: '#abcdef' } }\n")
            with open(spec, "w") as f:
                f.write(sentinel)
            shim = os.path.join(os.path.dirname(__file__), "dump_parts.py")
            subprocess.run([sys.executable, shim, glb],
                           capture_output=True, text=True, check=True)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "Model.scaffold.json")))
            self.assertFalse(os.path.isfile(os.path.join(tmp, "Model.colors.json")))
            self.assertFalse(os.path.isfile(os.path.join(tmp, "Model.manifest.json")))
            # The existing spec is left alone — no stub emission overwrites it.
            with open(spec) as f:
                self.assertEqual(f.read(), sentinel)


@unittest.skipUnless(os.path.isfile(GLB_PATH), "Positron GLB fixture not present")
class TestLegacyDumpPartsShim(unittest.TestCase):
    """dump_parts.py is a shim that produces identical output to build_configurator."""

    def test_shim_matches_build_configurator(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            glb_a = os.path.join(a, "Positron.glb")
            glb_b = os.path.join(b, "Positron.glb")
            shutil.copyfile(GLB_PATH, glb_a)
            shutil.copyfile(GLB_PATH, glb_b)
            shim = os.path.join(os.path.dirname(__file__), "dump_parts.py")
            subprocess.run([sys.executable, SCRIPT, glb_a], capture_output=True, check=True)
            subprocess.run([sys.executable, shim, glb_b], capture_output=True, check=True)
            with open(os.path.join(a, "Positron.scaffold.json")) as fa, \
                 open(os.path.join(b, "Positron.scaffold.json")) as fb:
                self.assertEqual(fa.read(), fb.read())
            with open(os.path.join(a, "Positron.spec.yaml")) as fa, \
                 open(os.path.join(b, "Positron.spec.yaml")) as fb:
                self.assertEqual(fa.read(), fb.read())


if __name__ == "__main__":
    unittest.main()
