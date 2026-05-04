#!/usr/bin/env python3
# ABOUTME: Tests for name normalization used to match STEP product names to GLB object names.
# ABOUTME: Covers spaces→underscores, version suffix stripping, and end-to-end matching.

"""
Tests for the name-matching logic in blender_export.py.

Runs standalone (no bpy dependency) to verify that STEP product names
are correctly normalized to match FreeCAD/Blender object names.
"""

import sys
import os
import unittest

# Make blender_export importable without bpy by mocking the import
# We only need the pure-Python functions, not the Blender API calls
sys.modules['bpy'] = type(sys)('bpy')

sys.path.insert(0, os.path.dirname(__file__))
from blender_export import normalize_for_matching, clean_node_name, strip_numeric_suffix


class TestNormalizeForMatching(unittest.TestCase):
    """Verify normalize_for_matching bridges STEP names → GLB names."""

    def test_spaces_to_underscores(self):
        self.assertEqual(
            normalize_for_matching('PV3 MAIN PCB'),
            'PV3_MAIN_PCB')

    def test_version_suffix_stripped(self):
        self.assertEqual(
            normalize_for_matching('PV3 Portable Spool Holder [3DP] v2'),
            'PV3_Portable_Spool_Holder_[3DP]')

    def test_version_suffix_with_minor(self):
        self.assertEqual(
            normalize_for_matching('Orbiter 2.0 v2.8'),
            'Orbiter_2.0')

    def test_no_version_suffix(self):
        self.assertEqual(
            normalize_for_matching('[a]_lip_spool_holder_inner'),
            '[a]_lip_spool_holder_inner')

    def test_already_underscored(self):
        self.assertEqual(
            normalize_for_matching('M3x8_BHCS'),
            'M3x8_BHCS')

    def test_version_suffix_with_instance(self):
        """Version suffix between part name and instance number."""
        result = normalize_for_matching('PV3 Portable Spool Holder [3DP] v2 (1)')
        self.assertEqual(result, 'PV3_Portable_Spool_Holder_[3DP]_(1)')


class TestEndToEndMatching(unittest.TestCase):
    """Verify that real STEP→GLB name pairs match after normalization + suffix stripping.

    Models the actual apply_colors lookup: build tables from ALL extraction entries,
    then check if a GLB name resolves to a color.
    """

    # Extraction entries from Positron_NEW.step (product_name → color)
    EXTRACTION = {
        'PV3 Portable Spool Holder [3DP] v2-3.step': 'Main Color',
        'PV3 Portable Spool Holder [3DP] v2-4.step': 'Main Color',
        'PV3 Portable Spool Holder [3DP] v2-5.step': 'Main Color',
        'PV3 Portable Spool Holder [3DP] v2 (1)-6.step': 'Main Color',
        'PV3 Portable Spool Holder [3DP] v2 (1)-7.step': 'Main Color',
        'PV3 Portable Spool Holder [3DP] v2 (1)-8.step': 'Main Color',
        'PV3_MAIN PCB.step': 'Opaque(160,160,160)',
        '[a]_lip_spool_holder_inner': 'Opaque(232,173,35)',
        '[a]_lip_spool_holder_outer': 'Main Color',
    }

    @classmethod
    def setUpClass(cls):
        """Build lookup tables the same way apply_colors does."""
        cls.name_to_color = {}
        for part_name, color_name in cls.EXTRACTION.items():
            cleaned = normalize_for_matching(clean_node_name(part_name))
            cls.name_to_color[cleaned] = color_name

        cls.stripped_to_color = {}
        for name, color_name in cls.name_to_color.items():
            stripped = strip_numeric_suffix(name)
            if stripped not in cls.stripped_to_color:
                cls.stripped_to_color[stripped] = color_name

    def _resolve(self, glb_name):
        """Simulate the color lookup from apply_colors. Returns color or None."""
        name = normalize_for_matching(glb_name)
        color = self.name_to_color.get(name)
        if not color:
            color = self.stripped_to_color.get(strip_numeric_suffix(name))
        return color

    def test_spool_holder_base(self):
        self.assertEqual(self._resolve('PV3_Portable_Spool_Holder_[3DP]'), 'Main Color')

    def test_spool_holder_instance_1(self):
        self.assertEqual(self._resolve('PV3_Portable_Spool_Holder_[3DP]_(1)'), 'Main Color')

    def test_spool_holder_higher_instances(self):
        """Instances (2)-(5) should fall back to the base part's color."""
        for i in range(2, 6):
            with self.subTest(instance=i):
                self.assertEqual(
                    self._resolve(f'PV3_Portable_Spool_Holder_[3DP]_({i})'),
                    'Main Color')

    def test_pcb(self):
        self.assertEqual(self._resolve('PV3_MAIN_PCB'), 'Opaque(160,160,160)')

    def test_lip_spool_exact(self):
        self.assertEqual(
            self._resolve('[a]_lip_spool_holder_inner'), 'Opaque(232,173,35)')


class TestStripNumericSuffix(unittest.TestCase):
    """Verify strip_numeric_suffix handles all instance numbering patterns."""

    def test_blender_duplicate(self):
        self.assertEqual(strip_numeric_suffix('Name.001'), 'Name')

    def test_freecad_duplicate(self):
        self.assertEqual(strip_numeric_suffix('Name001'), 'Name')

    def test_step_instance(self):
        self.assertEqual(strip_numeric_suffix('Name-1'), 'Name')

    def test_parenthesized_instance(self):
        """FreeCAD parenthesized instance: Name_(2) → Name"""
        self.assertEqual(strip_numeric_suffix('Name_(2)'), 'Name')

    def test_parenthesized_instance_with_spaces(self):
        self.assertEqual(
            strip_numeric_suffix('PV3_Portable_Spool_Holder_[3DP]_(4)'),
            'PV3_Portable_Spool_Holder_[3DP]')

    def test_no_suffix(self):
        self.assertEqual(strip_numeric_suffix('Name'), 'Name')


if __name__ == '__main__':
    unittest.main()
