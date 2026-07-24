#!/usr/bin/env python3
# ABOUTME: Tests for the colors.json and manifest.json builders called by build_configurator.py.
# ABOUTME: Skipped when PyYAML is unavailable so scaffold-only environments still test green.

import os
import sys
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(__file__))

try:
    import yaml as _yaml  # noqa: F401
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

if YAML_AVAILABLE:
    from spec import parse
    from build_configurator import build_colors_json, build_manifest_json


def _spec(yaml_text):
    return parse(textwrap.dedent(yaml_text).strip())


@unittest.skipUnless(YAML_AVAILABLE, "PyYAML not installed")
class TestBuildColorsJson(unittest.TestCase):
    def test_palette_passes_through(self):
        s = _spec("""
            model: { name: T, glb: f.glb }
            palette:
              Frame:  { color: '#444444', metalness: 0.2 }
              Hidden: { showInPicker: false }
        """)
        out = build_colors_json(s)
        self.assertEqual(out["palette"], s.palette)

    def test_auto_assign_passes_through(self):
        s = _spec("""
            model: { name: T, glb: f.glb }
            palette: { Frame: { color: '#444' } }
            autoAssign:
              - { match: '*Cowling*', category: Frame }
        """)
        out = build_colors_json(s)
        self.assertEqual(out["autoAssign"],
                         [{"match": "*Cowling*", "category": "Frame"}])

    def test_includes_node_with_display_name(self):
        s = _spec("""
            model: { name: T, glb: f.glb }
            palette: { Frame: { color: '#444' } }
            nodes:
              Foo: { displayName: 'Pretty Foo' }
        """)
        out = build_colors_json(s)
        self.assertIn("Foo", out["nodes"])
        self.assertEqual(out["nodes"]["Foo"], {"displayName": "Pretty Foo"})

    def test_includes_node_with_explicit_category(self):
        s = _spec("""
            model: { name: T, glb: f.glb }
            palette: { Frame: { color: '#444' }, Accent: { color: '#A00' } }
            nodes:
              Foo: { category: Accent }
        """)
        out = build_colors_json(s)
        self.assertEqual(out["nodes"]["Foo"], {"category": "Accent"})

    def test_marks_default_hidden_nodes(self):
        s = _spec("""
            model: { name: T, glb: f.glb }
            palette: { Frame: { color: '#444' } }
            options:
              carriage:
                label: C
                choices:
                  - { id: xol, label: Xol, default: true }
                  - { id: omron, label: Omron }
            nodes:
              Carriages/Omron-Carriage:
                visible: { when: { carriage: omron } }
        """)
        out = build_colors_json(s)
        self.assertIn("Carriages/Omron-Carriage", out["nodes"])
        self.assertEqual(out["nodes"]["Carriages/Omron-Carriage"], {"hidden": True})

    def test_omits_node_visible_under_default(self):
        """A node visible under the default config and lacking other metadata is omitted."""
        s = _spec("""
            model: { name: T, glb: f.glb }
            palette: { Frame: { color: '#444' } }
            options:
              carriage:
                label: C
                choices:
                  - { id: xol, label: Xol, default: true }
            nodes:
              Carriages/Xol-Carriage:
                visible: { when: { carriage: xol } }
        """)
        out = build_colors_json(s)
        self.assertNotIn("Carriages/Xol-Carriage", out["nodes"])

    def test_combines_displayname_and_hidden(self):
        s = _spec("""
            model: { name: T, glb: f.glb }
            palette: { Frame: { color: '#444' } }
            options:
              hexCowl: { label: Hex, type: bool, default: false }
            nodes:
              HexCowlings/A:
                displayName: "Hex Cowl A"
                visible: { when: { hexCowl: true } }
        """)
        out = build_colors_json(s)
        self.assertEqual(out["nodes"]["HexCowlings/A"],
                         {"displayName": "Hex Cowl A", "hidden": True})


@unittest.skipUnless(YAML_AVAILABLE, "PyYAML not installed")
class TestBuildManifestJson(unittest.TestCase):
    def test_glb_filename_passed(self):
        s = _spec("""
            model: { name: T, glb: Toolhead.glb }
            palette: { Frame: { color: '#444' } }
        """)
        out = build_manifest_json(s)
        self.assertEqual(out["glb"], "Toolhead.glb")

    def test_options_pass_through(self):
        s = _spec("""
            model: { name: T, glb: f.glb }
            palette: { Frame: { color: '#444' } }
            options:
              carriage:
                label: Carriage
                choices:
                  - { id: xol, label: Xol, default: true }
        """)
        out = build_manifest_json(s)
        self.assertIn("configOptions", out)
        self.assertIn("carriage", out["configOptions"])

    def test_part_for_node_with_visible_rule(self):
        s = _spec("""
            model: { name: T, glb: f.glb }
            palette: { Frame: { color: '#444' } }
            options:
              hotend:
                label: Hotend
                choices:
                  - { id: dragon, label: Dragon, default: true }
            nodes:
              Hotends/Dragon:
                visible: { when: { hotend: dragon } }
        """)
        out = build_manifest_json(s)
        ids = [p["id"] for p in out["parts"]]
        self.assertIn("Hotends/Dragon", ids)
        part = next(p for p in out["parts"] if p["id"] == "Hotends/Dragon")
        self.assertEqual(part["visible"], {"when": {"hotend": "dragon"}})
        self.assertEqual(part["nodes"], ["Hotends/Dragon"])

    def test_part_for_node_with_stl_only(self):
        """A node with STL but no visibility rule is still a downloadable part."""
        s = _spec("""
            model: { name: T, glb: f.glb }
            palette: { Frame: { color: '#444' } }
            nodes:
              Frame/Always: { stl: Frame/Always.stl }
        """)
        out = build_manifest_json(s)
        ids = [p["id"] for p in out["parts"]]
        self.assertIn("Frame/Always", ids)

    def test_omits_part_for_plain_node(self):
        """Nodes without visibility rules and without STLs aren't in parts[]."""
        s = _spec("""
            model: { name: T, glb: f.glb }
            palette: { Frame: { color: '#444' } }
            nodes:
              Frame/Decoration: { displayName: "Pretty" }
        """)
        out = build_manifest_json(s)
        ids = [p["id"] for p in out["parts"]]
        self.assertNotIn("Frame/Decoration", ids)

    def test_stl_resolves_against_base(self):
        s = _spec("""
            model: { name: T, glb: f.glb }
            palette: { Frame: { color: '#444' } }
            stlBase: "https://cdn.example.com/STL/"
            nodes:
              Foo: { stl: Foo.stl }
        """)
        out = build_manifest_json(s)
        self.assertEqual(out["stlBase"], "https://cdn.example.com/STL/")
        part = next(p for p in out["parts"] if p["id"] == "Foo")
        self.assertEqual(part["stl"], ["Foo.stl"])

    def test_visual_only_flag_pass_through(self):
        s = _spec("""
            model: { name: T, glb: f.glb }
            palette: { Frame: { color: '#444' } }
            options:
              hotend: { label: H, type: bool, default: false }
            nodes:
              Hotends/Visual:
                visible: { when: { hotend: true } }
                visualOnly: true
        """)
        out = build_manifest_json(s)
        part = next(p for p in out["parts"] if p["id"] == "Hotends/Visual")
        self.assertTrue(part["visualOnly"])

    def test_rule_expanded_for_unmatched_glob_paths(self):
        """A top-level hide-rule generates synthetic part entries for matched node paths
        not already declared in `nodes:`."""
        s = _spec("""
            model: { name: T, glb: f.glb }
            palette: { Frame: { color: '#444' } }
            options:
              hexCowl: { label: Hex, type: bool, default: false }
            rules:
              - { hide: "Cowlings/*", when: { hexCowl: true } }
        """)
        # Provide GLB node paths so rule expansion knows which paths to materialize.
        out = build_manifest_json(s, glb_node_paths=["Cowlings/A", "Cowlings/B", "Other"])
        ids = [p["id"] for p in out["parts"]]
        self.assertIn("Cowlings/A", ids)
        self.assertIn("Cowlings/B", ids)
        self.assertNotIn("Other", ids)
        a = next(p for p in out["parts"] if p["id"] == "Cowlings/A")
        self.assertEqual(a["visible"], {"unless": {"hexCowl": True}})

    def test_compatibility_pass_through(self):
        s = _spec("""
            model: { name: T, glb: f.glb }
            palette: { Frame: { color: '#444' } }
            compatibility:
              - { when: { a: x }, incompatible: true, message: nope }
        """)
        out = build_manifest_json(s)
        self.assertEqual(len(out["compatibility"]), 1)
        self.assertEqual(out["compatibility"][0]["message"], "nope")


if __name__ == "__main__":
    unittest.main()
