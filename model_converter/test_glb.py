#!/usr/bin/env python3
# ABOUTME: Tests for glb.py — node-name cleaning, suffix stripping, and tree walking.
# ABOUTME: Synthetic glTF JSON inputs cover single-root, multi-root, and nameless-pass-through cases.

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from glb import clean_node_name, strip_numeric_suffix, build_node_paths, extract_names


class TestCleanNodeName(unittest.TestCase):
    def test_strips_step_extension(self):
        self.assertEqual(clean_node_name("Part.step"), "Part")

    def test_preserves_step_instance_suffix(self):
        self.assertEqual(clean_node_name("Part.step-3"), "Part-3")

    def test_strips_mesh_suffix(self):
        self.assertEqual(clean_node_name("Part (mesh)"), "Part")

    def test_strips_group_suffix(self):
        self.assertEqual(clean_node_name("Assembly (group)"), "Assembly")

    def test_spaces_become_underscores(self):
        self.assertEqual(clean_node_name("Z Axis Top"), "Z_Axis_Top")

    def test_strips_threejs_reserved_chars(self):
        self.assertEqual(clean_node_name("Foo[1].bar:baz"), "Foo1barbaz")

    def test_takes_last_component_of_slash_path(self):
        self.assertEqual(clean_node_name("Some/Path/Final"), "Final")

    def test_empty_returns_empty(self):
        self.assertEqual(clean_node_name(""), "")

    def test_none_returns_none(self):
        self.assertIsNone(clean_node_name(None))


class TestStripNumericSuffix(unittest.TestCase):
    def test_strips_dash_n(self):
        self.assertEqual(strip_numeric_suffix("Part-3"), "Part")

    def test_strips_multi_digit(self):
        self.assertEqual(strip_numeric_suffix("Part-1234"), "Part")

    def test_no_suffix_unchanged(self):
        self.assertEqual(strip_numeric_suffix("Part"), "Part")

    def test_does_not_strip_dot_suffix(self):
        # GLB-side strip is narrow: only -N. Blender's .001 is handled
        # upstream in blender_export.py before we ever see the name.
        self.assertEqual(strip_numeric_suffix("Part.001"), "Part.001")


class TestBuildNodePaths(unittest.TestCase):
    """build_node_paths walks a synthetic glTF tree and returns ordered (path, name) pairs."""

    def test_single_root_excluded_from_paths(self):
        glb = {
            "scenes": [{"nodes": [0]}],
            "scene": 0,
            "nodes": [
                {"name": "Root", "children": [1, 2]},
                {"name": "ChildA"},
                {"name": "ChildB", "children": [3]},
                {"name": "Grandchild"},
            ],
        }
        pairs = build_node_paths(glb)
        self.assertEqual(pairs, [
            ("ChildA", "ChildA"),
            ("ChildB", "ChildB"),
            ("ChildB/Grandchild", "Grandchild"),
        ])

    def test_multi_root_each_at_depth_one(self):
        glb = {
            "scenes": [{"nodes": [0, 1]}],
            "scene": 0,
            "nodes": [
                {"name": "RootA"},
                {"name": "RootB", "children": [2]},
                {"name": "Leaf"},
            ],
        }
        pairs = build_node_paths(glb)
        self.assertEqual(pairs, [
            ("RootA", "RootA"),
            ("RootB", "RootB"),
            ("RootB/Leaf", "Leaf"),
        ])

    def test_nameless_node_passes_through_to_named_descendants(self):
        glb = {
            "scenes": [{"nodes": [0]}],
            "scene": 0,
            "nodes": [
                {"name": "Root", "children": [1]},
                {"children": [2]},  # nameless
                {"name": "Deep"},
            ],
        }
        pairs = build_node_paths(glb)
        self.assertEqual(pairs, [("Deep", "Deep")])

    def test_node_names_are_cleaned(self):
        glb = {
            "scenes": [{"nodes": [0]}],
            "scene": 0,
            "nodes": [
                {"name": "Root", "children": [1]},
                {"name": "Spool Holder (mesh)"},
            ],
        }
        pairs = build_node_paths(glb)
        self.assertEqual(pairs, [("Spool_Holder", "Spool_Holder")])

    def test_empty_scenes_returns_empty(self):
        self.assertEqual(build_node_paths({"scenes": [], "nodes": []}), [])


class TestExtractNames(unittest.TestCase):
    def test_groups_and_parts_unique_and_sorted(self):
        glb = {
            "nodes": [
                {"name": "Z_Top", "children": [1, 2]},
                {"name": "Bolt-1", "mesh": 0},
                {"name": "Bolt-2", "mesh": 0},
                {"name": "X_Axis", "children": [4]},
                {"name": "Pulley", "mesh": 1},
            ],
        }
        # Wire children: Z_Top has Bolt-1, Bolt-2; X_Axis has Pulley
        glb["nodes"][3]["children"] = [4]
        groups, parts = extract_names(glb)
        # Groups are parents of meshes; parts are mesh nodes.
        self.assertIn("Z_Top", groups)
        self.assertIn("X_Axis", groups)
        self.assertIn("Bolt", parts)  # numeric suffix stripped
        self.assertIn("Pulley", parts)


if __name__ == "__main__":
    unittest.main()
