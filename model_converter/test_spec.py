#!/usr/bin/env python3
# ABOUTME: Tests for spec.py — parsing, validation, and the visibility DSL evaluator.
# ABOUTME: Skipped when PyYAML is not installed so scaffold-only environments still test green.

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
    from spec import (
        parse,
        SpecError,
        NodeSpec,
        evaluate_visible,
        default_config,
        validate_against_tree,
        compute_coverage,
    )


@unittest.skipUnless(YAML_AVAILABLE, "PyYAML not installed")
class TestParse(unittest.TestCase):
    def test_minimal_spec(self):
        text = textwrap.dedent("""
            model:
              name: Test
              glb: foo.glb
            palette:
              Main: { color: "#ff0000" }
        """).strip()
        s = parse(text)
        self.assertEqual(s.model_name, "Test")
        self.assertEqual(s.glb_path, "foo.glb")
        self.assertEqual(s.palette["Main"]["color"], "#ff0000")

    def test_missing_model_block_raises(self):
        with self.assertRaises(SpecError):
            parse("palette: { Main: { color: '#fff' } }")

    def test_missing_glb_in_model_raises(self):
        with self.assertRaises(SpecError):
            parse("model: { name: T }\npalette: { Main: { color: '#fff' } }")

    def test_missing_palette_raises(self):
        with self.assertRaises(SpecError):
            parse("model: { name: T, glb: f.glb }")

    def test_empty_palette_raises(self):
        with self.assertRaises(SpecError):
            parse("model: { name: T, glb: f.glb }\npalette: {}")

    def test_invalid_yaml_raises(self):
        with self.assertRaises(SpecError):
            parse("not: valid: yaml: [")

    def test_auto_assign_unknown_category_raises(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            autoAssign:
              - { match: '*', category: Bogus }
        """).strip()
        with self.assertRaises(SpecError):
            parse(text)

    def test_node_unknown_category_raises(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            nodes:
              Foo: { category: Bogus }
        """).strip()
        with self.assertRaises(SpecError):
            parse(text)

    def test_node_visible_parses_when_and_unless(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            nodes:
              Foo:
                visible:
                  when: { carriage: xol }
                  unless: { hexCowl: true }
        """).strip()
        s = parse(text)
        node = s.nodes["Foo"]
        self.assertEqual(node.visible_when, {"carriage": "xol"})
        self.assertEqual(node.visible_unless, {"hexCowl": True})

    def test_node_stl_string_normalized_to_list(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            nodes:
              Foo: { stl: a/b.stl }
        """).strip()
        s = parse(text)
        self.assertEqual(s.nodes["Foo"].stl, ["a/b.stl"])

    def test_node_stl_list_preserved(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            nodes:
              Foo: { stl: [a.stl, b.stl] }
        """).strip()
        s = parse(text)
        self.assertEqual(s.nodes["Foo"].stl, ["a.stl", "b.stl"])

    def test_options_choices_parsed(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              carriage:
                label: Carriage
                choices:
                  - { id: xol, label: Xol, default: true }
                  - { id: omron, label: Omron }
        """).strip()
        s = parse(text)
        self.assertIn("carriage", s.options)
        self.assertEqual(s.options["carriage"]["label"], "Carriage")
        self.assertEqual(len(s.options["carriage"]["choices"]), 2)

    def test_bool_option_parsed(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              hexCowl: { label: Hex, type: bool, default: true }
        """).strip()
        s = parse(text)
        self.assertEqual(s.options["hexCowl"]["type"], "bool")
        self.assertIs(s.options["hexCowl"]["default"], True)

    def test_option_description_parsed(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              carriage:
                label: Carriage
                description: "Pick the carriage variant."
                choices:
                  - { id: xol, label: Xol, default: true }
        """).strip()
        s = parse(text)
        self.assertEqual(s.options["carriage"]["description"], "Pick the carriage variant.")

    def test_choice_description_parsed(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              carriage:
                label: Carriage
                choices:
                  - { id: xol, label: Xol, description: "Original.", default: true }
                  - { id: omron, label: Omron }
        """).strip()
        s = parse(text)
        choices = s.options["carriage"]["choices"]
        self.assertEqual(choices[0]["description"], "Original.")
        self.assertNotIn("description", choices[1])

    def test_bool_option_description_parsed(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              hexCowl:
                label: Hex
                description: "Optional patterned top cowl."
                type: bool
                default: false
        """).strip()
        s = parse(text)
        self.assertEqual(s.options["hexCowl"]["description"], "Optional patterned top cowl.")

    def test_selection_type_defaults_to_radio(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              carriage:
                choices:
                  - { id: xol, default: true }
        """).strip()
        s = parse(text)
        self.assertEqual(s.options["carriage"]["type"], "radio")

    def test_selection_type_dropdown_passes_through(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              carriage:
                type: dropdown
                choices:
                  - { id: xol, default: true }
        """).strip()
        s = parse(text)
        self.assertEqual(s.options["carriage"]["type"], "dropdown")

    def test_selection_type_unknown_passes_through(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              carriage:
                type: image_grid
                choices:
                  - { id: xol, default: true }
        """).strip()
        s = parse(text)
        self.assertEqual(s.options["carriage"]["type"], "image_grid")

    def test_option_description_must_be_string(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              carriage:
                description: 42
                choices:
                  - { id: xol, default: true }
        """).strip()
        with self.assertRaises(SpecError):
            parse(text)

    def test_choice_description_must_be_string(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              carriage:
                choices:
                  - { id: xol, description: 42, default: true }
        """).strip()
        with self.assertRaises(SpecError):
            parse(text)

    def test_option_type_must_be_string(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              carriage:
                type: 42
                choices:
                  - { id: xol, default: true }
        """).strip()
        with self.assertRaises(SpecError):
            parse(text)

    def test_choice_when_clause_parsed(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              bearing:
                choices:
                  - { id: big, default: true, when: { rod: [ten, eleven] } }
                  - { id: small, when: { rod: eight } }
                  - { id: any }
        """).strip()
        s = parse(text)
        choices = s.options["bearing"]["choices"]
        self.assertEqual(choices[0]["when"], {"rod": ["ten", "eleven"]})
        self.assertEqual(choices[1]["when"], {"rod": "eight"})
        self.assertNotIn("when", choices[2])

    def test_choice_when_must_be_mapping(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              bearing:
                choices:
                  - { id: big, when: nope }
        """).strip()
        with self.assertRaises(SpecError):
            parse(text)

    def test_palette_show_in_tree_false_preserved(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette:
              Main:   { color: '#fff' }
              Hidden: { color: '#222', showInTree: false }
        """).strip()
        s = parse(text)
        self.assertIs(s.palette["Hidden"]["showInTree"], False)
        self.assertNotIn("showInTree", s.palette["Main"])

    def test_palette_show_in_tree_must_be_bool(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette:
              Hidden: { color: '#222', showInTree: "no" }
        """).strip()
        with self.assertRaises(SpecError):
            parse(text)

    def test_node_show_in_tree_false_parsed(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            nodes:
              Foo: { showInTree: false }
        """).strip()
        s = parse(text)
        self.assertIs(s.nodes["Foo"].show_in_tree, False)

    def test_node_show_in_tree_default_true(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            nodes:
              Foo: { displayName: "Foo Display" }
        """).strip()
        s = parse(text)
        self.assertIs(s.nodes["Foo"].show_in_tree, True)

    def test_node_show_in_tree_must_be_bool(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            nodes:
              Foo: { showInTree: "no" }
        """).strip()
        with self.assertRaises(SpecError):
            parse(text)

    def test_downloads_parsed(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
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
                  files: [ "X/b.stl", "X/c.stl" ]
        """).strip()
        s = parse(text)
        self.assertEqual(s.downloads["base"], "https://example.com/STLs/")
        self.assertEqual(s.downloads["always"], ["Tools/a.stl"])
        self.assertEqual(s.downloads["groups"][0]["when"], {"pulley": "b"})
        self.assertEqual(s.downloads["groups"][0]["files"], ["X/b.stl", "X/c.stl"])

    def test_downloads_absent_is_none(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
        """).strip()
        self.assertIsNone(parse(text).downloads)

    def test_downloads_when_accepts_list_values(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            downloads:
              base: "https://example.com/"
              groups:
                - when: { pulley: [a, b] }
                  files: [ "f.stl" ]
        """).strip()
        s = parse(text)
        self.assertEqual(s.downloads["groups"][0]["when"], {"pulley": ["a", "b"]})

    def test_downloads_requires_base(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            downloads:
              always: [ "a.stl" ]
        """).strip()
        with self.assertRaises(SpecError):
            parse(text)

    def test_downloads_always_must_be_strings(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            downloads:
              base: "https://example.com/"
              always: [ 42 ]
        """).strip()
        with self.assertRaises(SpecError):
            parse(text)

    def test_downloads_group_requires_files(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            downloads:
              base: "https://example.com/"
              groups:
                - when: { pulley: a }
        """).strip()
        with self.assertRaises(SpecError):
            parse(text)

    def test_downloads_group_requires_when(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            downloads:
              base: "https://example.com/"
              groups:
                - files: [ "f.stl" ]
        """).strip()
        with self.assertRaises(SpecError):
            parse(text)


@unittest.skipUnless(YAML_AVAILABLE, "PyYAML not installed")
class TestEvaluateVisible(unittest.TestCase):
    def _n(self, **kw):
        defaults = dict(display_name=None, category=None, hidden=False,
                        visible_when=None, visible_unless=None,
                        stl=None, visual_only=False, show_in_tree=True)
        defaults.update(kw)
        return NodeSpec(**defaults)

    def test_no_rules_visible(self):
        self.assertTrue(evaluate_visible(self._n(), {}))

    def test_when_equality(self):
        n = self._n(visible_when={"carriage": "xol"})
        self.assertTrue(evaluate_visible(n, {"carriage": "xol"}))
        self.assertFalse(evaluate_visible(n, {"carriage": "omron"}))

    def test_when_list_is_or(self):
        n = self._n(visible_when={"extruder": ["a", "b"]})
        self.assertTrue(evaluate_visible(n, {"extruder": "a"}))
        self.assertTrue(evaluate_visible(n, {"extruder": "b"}))
        self.assertFalse(evaluate_visible(n, {"extruder": "c"}))

    def test_when_multi_key_is_and(self):
        n = self._n(visible_when={"carriage": "xol", "hotend": "dragon"})
        self.assertTrue(evaluate_visible(n, {"carriage": "xol", "hotend": "dragon"}))
        self.assertFalse(evaluate_visible(n, {"carriage": "xol", "hotend": "rapido"}))

    def test_unless_hides_when_match(self):
        n = self._n(visible_unless={"hexCowl": True})
        self.assertFalse(evaluate_visible(n, {"hexCowl": True}))
        self.assertTrue(evaluate_visible(n, {"hexCowl": False}))

    def test_when_and_unless_combined(self):
        n = self._n(visible_when={"hotend": "dragon"}, visible_unless={"hexCowl": True})
        self.assertTrue(evaluate_visible(n, {"hotend": "dragon", "hexCowl": False}))
        self.assertFalse(evaluate_visible(n, {"hotend": "dragon", "hexCowl": True}))
        self.assertFalse(evaluate_visible(n, {"hotend": "rapido", "hexCowl": False}))

    def test_hidden_flag_overrides_visible(self):
        n = self._n(hidden=True)
        self.assertFalse(evaluate_visible(n, {}))


@unittest.skipUnless(YAML_AVAILABLE, "PyYAML not installed")
class TestDefaultConfig(unittest.TestCase):
    def test_picks_up_default_true(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              carriage:
                label: Carriage
                choices:
                  - { id: xol, label: Xol, default: true }
                  - { id: omron, label: Omron }
        """).strip()
        s = parse(text)
        self.assertEqual(default_config(s), {"carriage": "xol"})

    def test_first_choice_when_none_marked_default(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              carriage:
                label: Carriage
                choices:
                  - { id: a, label: A }
                  - { id: b, label: B }
        """).strip()
        s = parse(text)
        self.assertEqual(default_config(s), {"carriage": "a"})

    def test_bool_default(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            options:
              hexCowl: { label: Hex, type: bool, default: true }
              foo:    { label: Foo, type: bool }
        """).strip()
        s = parse(text)
        self.assertEqual(default_config(s), {"hexCowl": True, "foo": False})


@unittest.skipUnless(YAML_AVAILABLE, "PyYAML not installed")
class TestValidateAgainstTree(unittest.TestCase):
    def test_warns_on_missing_node_path(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            nodes:
              Real/Path: { displayName: A }
              Bogus/Path: { displayName: B }
        """).strip()
        s = parse(text)
        warnings = validate_against_tree(s, ["Real/Path"])
        self.assertTrue(any("Bogus/Path" in w for w in warnings))
        self.assertFalse(any("Real/Path" in w for w in warnings))

    def test_warns_on_zero_match_glob(self):
        text = textwrap.dedent("""
            model: { name: T, glb: f.glb }
            palette: { Main: { color: '#fff' } }
            autoAssign:
              - { match: 'NeverMatches*', category: Main }
              - { match: 'Real*',         category: Main }
        """).strip()
        s = parse(text)
        warnings = validate_against_tree(s, ["RealThing", "RealOther"])
        self.assertTrue(any("NeverMatches" in w for w in warnings))
        self.assertFalse(any("Real*" in w for w in warnings))


@unittest.skipUnless(YAML_AVAILABLE, "PyYAML not installed")
class TestComputeCoverage(unittest.TestCase):
    def _spec(self, text):
        return parse(textwrap.dedent(text).strip())

    def test_empty_spec_all_uncovered(self):
        s = self._spec("""
            model: { name: T, glb: f.glb }
            palette: { A: { color: '#aaa' } }
        """)
        cov = compute_coverage(s, ["X", "Y", "Z"])
        self.assertEqual(cov.total_nodes, 3)
        self.assertEqual(cov.covered_via_autoAssign, 0)
        self.assertEqual(cov.covered_via_overrides, 0)
        self.assertEqual(cov.uncovered, 3)
        self.assertEqual(cov.rule_counts, [])

    def test_single_rule_matches_all(self):
        s = self._spec("""
            model: { name: T, glb: f.glb }
            palette: { A: { color: '#aaa' } }
            autoAssign:
              - { match: '*', category: A }
        """)
        cov = compute_coverage(s, ["X", "Y", "Z"])
        self.assertEqual(cov.covered_via_autoAssign, 3)
        self.assertEqual(cov.uncovered, 0)
        self.assertEqual(cov.rule_counts, [3])

    def test_first_match_wins_among_overlapping_rules(self):
        s = self._spec("""
            model: { name: T, glb: f.glb }
            palette: { A: { color: '#aaa' }, B: { color: '#bbb' } }
            autoAssign:
              - { match: 'Foo*', category: A }
              - { match: '*Bar*', category: B }
        """)
        cov = compute_coverage(s, ["FooBar", "Bar", "Foo"])
        self.assertEqual(cov.rule_counts, [2, 1])

    def test_per_node_override_excluded_from_autoAssign_count(self):
        s = self._spec("""
            model: { name: T, glb: f.glb }
            palette: { A: { color: '#aaa' } }
            autoAssign:
              - { match: '*', category: A }
            nodes:
              Special: { category: A }
        """)
        cov = compute_coverage(s, ["A", "Special"])
        self.assertEqual(cov.covered_via_overrides, 1)
        self.assertEqual(cov.covered_via_autoAssign, 1)
        self.assertEqual(cov.rule_counts, [1])
        self.assertEqual(cov.uncovered, 0)

    def test_per_node_entry_without_category_is_not_covered_override(self):
        """A node entry with displayName but no category isn't counted as override-covered."""
        s = self._spec("""
            model: { name: T, glb: f.glb }
            palette: { A: { color: '#aaa' } }
            nodes:
              Decorative: { displayName: "Pretty" }
        """)
        cov = compute_coverage(s, ["Decorative"])
        self.assertEqual(cov.covered_via_overrides, 0)
        self.assertEqual(cov.uncovered, 1)

    def test_zero_match_rule_has_zero_count(self):
        s = self._spec("""
            model: { name: T, glb: f.glb }
            palette: { A: { color: '#aaa' } }
            autoAssign:
              - { match: 'NeverMatch*', category: A }
              - { match: '*', category: A }
        """)
        cov = compute_coverage(s, ["X", "Y"])
        self.assertEqual(cov.rule_counts, [0, 2])

    def test_matches_leaf_not_full_path(self):
        """Rules match against the bare leaf name only, mirroring viewer.js."""
        s = self._spec("""
            model: { name: T, glb: f.glb }
            palette: { A: { color: '#aaa' } }
            autoAssign:
              - { match: 'Leaf*', category: A }
        """)
        cov = compute_coverage(s, ["Path/To/Leaf1", "Path/To/Other"])
        self.assertEqual(cov.rule_counts, [1])
        self.assertEqual(cov.uncovered, 1)

    def test_path_prefix_pattern_does_not_match(self):
        """Slash-containing patterns are dead at runtime — leaves have no slashes."""
        s = self._spec("""
            model: { name: T, glb: f.glb }
            palette: { A: { color: '#aaa' } }
            autoAssign:
              - { match: 'Group/*', category: A }
        """)
        cov = compute_coverage(s, ["Group/Child", "Group/Other"])
        self.assertEqual(cov.rule_counts, [0])
        self.assertEqual(cov.uncovered, 2)

    def test_effective_coverage_via_cascade(self):
        """A leaf-name match on the top-level group covers descendants via inheritance."""
        s = self._spec("""
            model: { name: T, glb: f.glb }
            palette: { A: { color: '#aaa' } }
            autoAssign:
              - { match: 'Frame', category: A }
        """)
        paths = ["Frame", "Frame/Sub", "Frame/Sub/Leaf"]
        cov = compute_coverage(s, paths)
        # Direct: only "Frame" matches (1)
        self.assertEqual(cov.covered_via_autoAssign, 1)
        self.assertEqual(cov.uncovered, 2)
        # Effective: all three covered (Sub and Leaf inherit from Frame)
        self.assertEqual(cov.effective_covered, 3)
        self.assertEqual(cov.truly_uncovered, 0)

    def test_truly_uncovered_when_no_ancestor_matches(self):
        """A subtree with no ancestor match shows up as truly_uncovered."""
        s = self._spec("""
            model: { name: T, glb: f.glb }
            palette: { A: { color: '#aaa' } }
            autoAssign:
              - { match: 'Frame', category: A }
        """)
        paths = ["Frame", "Frame/Sub", "Other", "Other/Stuff"]
        cov = compute_coverage(s, paths)
        self.assertEqual(cov.effective_covered, 2)
        self.assertEqual(cov.truly_uncovered, 2)
        self.assertIn("Other", cov.truly_uncovered_sample)
        self.assertIn("Other/Stuff", cov.truly_uncovered_sample)

    def test_per_node_override_propagates_through_cascade(self):
        """A per-node override on a group covers the whole subtree via cascade."""
        s = self._spec("""
            model: { name: T, glb: f.glb }
            palette: { A: { color: '#aaa' } }
            nodes:
              Group: { category: A }
        """)
        paths = ["Group", "Group/Inner", "Group/Inner/Deep"]
        cov = compute_coverage(s, paths)
        self.assertEqual(cov.covered_via_overrides, 1)
        self.assertEqual(cov.effective_covered, 3)
        self.assertEqual(cov.truly_uncovered, 0)

    def test_uncovered_sample_in_tree_order(self):
        s = self._spec("""
            model: { name: T, glb: f.glb }
            palette: { A: { color: '#aaa' } }
        """)
        nodes = [f"node_{i:02d}" for i in range(20)]
        cov = compute_coverage(s, nodes)
        self.assertEqual(cov.uncovered, 20)
        self.assertEqual(len(cov.uncovered_sample), 10)
        self.assertEqual(cov.uncovered_sample, nodes[:10])

    def test_rule_samples_capped(self):
        s = self._spec("""
            model: { name: T, glb: f.glb }
            palette: { A: { color: '#aaa' } }
            autoAssign:
              - { match: '*', category: A }
        """)
        nodes = [f"n{i}" for i in range(20)]
        cov = compute_coverage(s, nodes)
        self.assertLessEqual(len(cov.rule_samples[0]), 10)
        self.assertEqual(cov.rule_samples[0], nodes[:len(cov.rule_samples[0])])


if __name__ == "__main__":
    unittest.main()
