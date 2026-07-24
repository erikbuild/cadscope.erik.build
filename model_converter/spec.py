# ABOUTME: Parses and validates Toolhead.spec.yaml — the source of truth for sidecar + manifest output.
# ABOUTME: Provides the visibility DSL evaluator and config defaults used by build_configurator.py.

"""
Spec format (Toolhead.spec.yaml):

    model:
      name: "Display Name"
      glb: relative/path/to/model.glb

    palette:
      Frame:  { color: "#444444", metalness: 0.2 }
      Accent: { color: "#A62C2B" }
      Hidden: { showInPicker: false }

    autoAssign:
      - { match: "*Cowling*", category: Frame }

    options:
      carriage:
        label: "Carriage"
        choices:
          - { id: xol,   label: "Xol",   default: true }
          - { id: omron, label: "Omron" }
      hexCowl: { label: "Hex multi-colour cowl?", type: bool, default: false }

    compatibility:
      - when: { hotend: rapido, extruder: sherpa }
        incompatible: true
        message: "..."

    nodes:
      Carriages/Xol-Carriage:
        displayName: "Xol Carriage"
        category: Frame
        visible: { when: { carriage: xol } }
        stl: Carriages/Xol-Carriage.stl
      Hotends/Dragon:
        visible: { when: { hotend: dragon } }
        visualOnly: true

    rules:
      - { hide: "Cowlings/*", when: { hexCowl: true } }

    stlBase: "https://..."

Visibility DSL:
  A node is visible iff its `when` clause matches AND its `unless` clause
  does not. Each clause is a dict where all keys must match the config (AND).
  A list value means OR within that key. Missing clause = trivially satisfied.
"""

import sys

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Any

try:
    import yaml
except ImportError as e:
    raise ImportError(
        "spec.py requires PyYAML. Install via "
        "model_converter/.venv/bin/pip install -r model_converter/requirements.txt"
    ) from e


class SpecError(ValueError):
    """Raised on any schema/validation problem in a spec file."""


@dataclass
class NodeSpec:
    display_name: str | None = None
    category: str | None = None
    hidden: bool = False
    visible_when: dict | None = None
    visible_unless: dict | None = None
    stl: list[str] | None = None
    visual_only: bool = False
    show_in_tree: bool = True


@dataclass
class Spec:
    model_name: str
    glb_path: str
    palette: dict[str, dict]
    auto_assign: list[dict] = field(default_factory=list)
    options: dict[str, dict] = field(default_factory=dict)
    compatibility: list[dict] = field(default_factory=list)
    nodes: dict[str, NodeSpec] = field(default_factory=dict)
    rules: list[dict] = field(default_factory=list)
    stl_base: str | None = None
    downloads: dict | None = None


def parse(text: str) -> Spec:
    """Parse and validate a spec YAML string. Raises SpecError on any issue."""
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise SpecError(f"YAML parse error: {e}") from e

    if not isinstance(raw, dict):
        raise SpecError("top-level spec must be a mapping")

    model = raw.get("model")
    if not isinstance(model, dict):
        raise SpecError("missing required 'model' block")
    glb_path = model.get("glb")
    if not isinstance(glb_path, str) or not glb_path:
        raise SpecError("'model.glb' is required and must be a string")
    model_name = model.get("name") or ""

    palette = raw.get("palette")
    if not isinstance(palette, dict) or not palette:
        raise SpecError("'palette' is required and must contain at least one category")
    for cat, entry in palette.items():
        if not isinstance(entry, dict):
            raise SpecError(f"palette.{cat}: expected a mapping")
        if "showInTree" in entry and not isinstance(entry["showInTree"], bool):
            raise SpecError(f"palette.{cat}: 'showInTree' must be a bool")
        if "showInPicker" in entry and not isinstance(entry["showInPicker"], bool):
            raise SpecError(f"palette.{cat}: 'showInPicker' must be a bool")

    auto_assign = _parse_auto_assign(raw.get("autoAssign"), palette)
    options = _parse_options(raw.get("options"))
    downloads = _parse_downloads(raw.get("downloads"), options)
    compatibility = _parse_compatibility(raw.get("compatibility"))
    nodes = _parse_nodes(raw.get("nodes"), palette)
    rules = _parse_rules(raw.get("rules"))
    stl_base = raw.get("stlBase")
    if stl_base is not None and not isinstance(stl_base, str):
        raise SpecError("'stlBase' must be a string")

    return Spec(
        model_name=model_name,
        glb_path=glb_path,
        palette=palette,
        auto_assign=auto_assign,
        downloads=downloads,
        options=options,
        compatibility=compatibility,
        nodes=nodes,
        rules=rules,
        stl_base=stl_base,
    )


def parse_file(path: str) -> Spec:
    with open(path, "r") as f:
        return parse(f.read())


def _parse_auto_assign(raw, palette):
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise SpecError("'autoAssign' must be a list")
    out = []
    for i, rule in enumerate(raw):
        if not isinstance(rule, dict):
            raise SpecError(f"autoAssign[{i}]: expected a mapping")
        match = rule.get("match")
        category = rule.get("category")
        if not isinstance(match, str):
            raise SpecError(f"autoAssign[{i}]: 'match' must be a string")
        if not isinstance(category, str):
            raise SpecError(f"autoAssign[{i}]: 'category' must be a string")
        if category not in palette:
            raise SpecError(
                f"autoAssign[{i}]: unknown category '{category}' (not in palette)")
        out.append({"match": match, "category": category})
    return out


def _parse_downloads(raw, options):
    """Parse the optional downloads section: a base URL, an always-included
    file list, and option-gated file groups sharing the visible.when clause
    grammar (AND across keys; list value = OR within a key)."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise SpecError("'downloads' must be a mapping")
    base = raw.get("base")
    if not isinstance(base, str) or not base:
        raise SpecError("downloads: 'base' must be a non-empty string")
    out = {"base": base}
    always = raw.get("always")
    if always is not None:
        if not isinstance(always, list) or not all(isinstance(f, str) for f in always):
            raise SpecError("downloads: 'always' must be a list of strings")
        out["always"] = list(always)
    groups_raw = raw.get("groups")
    if groups_raw is not None:
        if not isinstance(groups_raw, list):
            raise SpecError("downloads: 'groups' must be a list")
        groups = []
        for i, group in enumerate(groups_raw):
            if not isinstance(group, dict):
                raise SpecError(f"downloads.groups[{i}]: expected a mapping")
            when = group.get("when")
            if not isinstance(when, dict) or not when:
                raise SpecError(f"downloads.groups[{i}]: 'when' must be a non-empty mapping")
            for key, value in when.items():
                if key not in options:
                    print(f"warning: downloads.groups[{i}].when references unknown option '{key}'",
                          file=sys.stderr)
                values = value if isinstance(value, list) else [value]
                if not all(isinstance(v, (str, bool)) for v in values):
                    raise SpecError(
                        f"downloads.groups[{i}].when.{key}: values must be strings or bools")
            files = group.get("files")
            if (not isinstance(files, list) or not files
                    or not all(isinstance(f, str) for f in files)):
                raise SpecError(
                    f"downloads.groups[{i}]: 'files' must be a non-empty list of strings")
            groups.append({"when": dict(when), "files": list(files)})
        out["groups"] = groups
    return out


def _parse_options(raw):
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SpecError("'options' must be a mapping")
    out = {}
    for opt_id, body in raw.items():
        if not isinstance(body, dict):
            raise SpecError(f"options.{opt_id}: expected a mapping")

        description = body.get("description")
        if description is not None and not isinstance(description, str):
            raise SpecError(f"options.{opt_id}: 'description' must be a string")

        if body.get("type") == "bool":
            entry = {
                "label": body.get("label", opt_id),
                "type": "bool",
                "default": bool(body.get("default", False)),
            }
        else:
            raw_type = body.get("type")
            if raw_type is None:
                emitted_type = "radio"
            elif isinstance(raw_type, str):
                emitted_type = raw_type
            else:
                raise SpecError(f"options.{opt_id}: 'type' must be a string")

            choices = body.get("choices")
            if not isinstance(choices, list) or not choices:
                raise SpecError(
                    f"options.{opt_id}: 'choices' is required and must be a non-empty list")
            parsed_choices = []
            for j, choice in enumerate(choices):
                if not isinstance(choice, dict):
                    raise SpecError(f"options.{opt_id}.choices[{j}]: expected a mapping")
                cid = choice.get("id")
                if not isinstance(cid, str):
                    raise SpecError(
                        f"options.{opt_id}.choices[{j}]: 'id' must be a string")
                choice_out = {
                    "id": cid,
                    "label": choice.get("label", cid),
                    "default": bool(choice.get("default", False)),
                }
                c_desc = choice.get("description")
                if c_desc is not None:
                    if not isinstance(c_desc, str):
                        raise SpecError(
                            f"options.{opt_id}.choices[{j}]: 'description' must be a string")
                    choice_out["description"] = c_desc
                c_when = choice.get("when")
                if c_when is not None:
                    if not isinstance(c_when, dict) or not c_when:
                        raise SpecError(
                            f"options.{opt_id}.choices[{j}]: 'when' must be a non-empty mapping")
                    for key, value in c_when.items():
                        values = value if isinstance(value, list) else [value]
                        if not all(isinstance(v, (str, bool)) for v in values):
                            raise SpecError(
                                f"options.{opt_id}.choices[{j}].when.{key}: values must be strings or bools")
                    choice_out["when"] = dict(c_when)
                parsed_choices.append(choice_out)
            entry = {
                "label": body.get("label", opt_id),
                "type": emitted_type,
                "choices": parsed_choices,
            }

        if description is not None:
            entry["description"] = description
        out[opt_id] = entry
    return out


def _parse_compatibility(raw):
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise SpecError("'compatibility' must be a list")
    out = []
    for i, rule in enumerate(raw):
        if not isinstance(rule, dict):
            raise SpecError(f"compatibility[{i}]: expected a mapping")
        when = rule.get("when")
        if not isinstance(when, dict):
            raise SpecError(f"compatibility[{i}]: 'when' must be a mapping")
        out.append({
            "when": dict(when),
            "incompatible": bool(rule.get("incompatible", True)),
            "message": rule.get("message"),
        })
    return out


def _parse_nodes(raw, palette):
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SpecError("'nodes' must be a mapping")
    out = {}
    for path, body in raw.items():
        if not isinstance(body, dict):
            raise SpecError(f"nodes.{path}: expected a mapping")
        category = body.get("category")
        if category is not None and category not in palette:
            raise SpecError(
                f"nodes.{path}: unknown category '{category}' (not in palette)")
        visible = body.get("visible") or {}
        if not isinstance(visible, dict):
            raise SpecError(f"nodes.{path}.visible: must be a mapping")
        when = visible.get("when")
        if when is not None and not isinstance(when, dict):
            raise SpecError(f"nodes.{path}.visible.when: must be a mapping")
        unless = visible.get("unless")
        if unless is not None and not isinstance(unless, dict):
            raise SpecError(f"nodes.{path}.visible.unless: must be a mapping")
        stl_raw = body.get("stl")
        if stl_raw is None:
            stl = None
        elif isinstance(stl_raw, str):
            stl = [stl_raw]
        elif isinstance(stl_raw, list):
            for j, item in enumerate(stl_raw):
                if not isinstance(item, str):
                    raise SpecError(f"nodes.{path}.stl[{j}]: must be a string")
            stl = list(stl_raw)
        else:
            raise SpecError(f"nodes.{path}.stl: must be a string or list of strings")
        show_in_tree_raw = body.get("showInTree")
        if show_in_tree_raw is not None and not isinstance(show_in_tree_raw, bool):
            raise SpecError(f"nodes.{path}: 'showInTree' must be a bool")
        out[path] = NodeSpec(
            display_name=body.get("displayName"),
            category=category,
            hidden=bool(body.get("hidden", False)),
            visible_when=dict(when) if when else None,
            visible_unless=dict(unless) if unless else None,
            stl=stl,
            visual_only=bool(body.get("visualOnly", False)),
            show_in_tree=True if show_in_tree_raw is None else show_in_tree_raw,
        )
    return out


def _parse_rules(raw):
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise SpecError("'rules' must be a list")
    out = []
    for i, rule in enumerate(raw):
        if not isinstance(rule, dict):
            raise SpecError(f"rules[{i}]: expected a mapping")
        if "hide" not in rule and "show" not in rule:
            raise SpecError(f"rules[{i}]: must have 'hide' or 'show'")
        out.append(dict(rule))
    return out


def _matches(clause: dict, config: dict) -> bool:
    """Conjunction over keys; list value is disjunction within key."""
    for key, expected in clause.items():
        actual = config.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        else:
            if actual != expected:
                return False
    return True


def evaluate_visible(node: NodeSpec, config: dict) -> bool:
    """Resolve a node's effective visibility under a config map."""
    if node.hidden:
        return False
    if node.visible_when and not _matches(node.visible_when, config):
        return False
    if node.visible_unless and _matches(node.visible_unless, config):
        return False
    return True


def default_config(spec: Spec) -> dict:
    """Build the default config map from each option's default markings.

    Selection options pick the first choice flagged `default: true`, or the
    first choice if none are flagged. Bool options use their `default:`
    value (defaulting to False).
    """
    config = {}
    for opt_id, body in spec.options.items():
        if body.get("type") == "bool":
            config[opt_id] = bool(body.get("default", False))
        else:
            choices = body["choices"]
            picked = next((c["id"] for c in choices if c.get("default")), None)
            if picked is None:
                picked = choices[0]["id"]
            config[opt_id] = picked
    return config


@dataclass
class CoverageReport:
    """Per-node coverage of an autoAssign + per-node-override pass over the GLB tree.

    Two senses of "covered" are tracked:
    - Direct: the node itself matched a per-node override or an autoAssign rule.
    - Effective: direct, OR inherits a category from a directly-matched ancestor
      (mirrors the viewer's top-down cascade).
    A node is "truly uncovered" only when neither it nor any ancestor matched.
    """
    total_nodes: int
    covered_via_autoAssign: int
    covered_via_overrides: int
    uncovered: int
    uncovered_sample: list[str]
    rule_counts: list[int]
    rule_samples: list[list[str]]
    effective_covered: int = 0
    truly_uncovered: int = 0
    truly_uncovered_sample: list[str] = field(default_factory=list)


_COVERAGE_SAMPLE_LIMIT = 10


def _leaf_matches(path: str, pattern: str) -> bool:
    """Match a pattern against the bare leaf name of a path.

    Mirrors viewer.js:533, which tests `node.name` (the leaf) against each
    autoAssign rule. Patterns that only match via full-path syntax (e.g.
    `Group/*`) are dead at runtime — leaves never contain slashes.
    """
    return fnmatchcase(path.split("/")[-1], pattern)


def compute_coverage(spec: Spec, glb_node_paths: list[str]) -> CoverageReport:
    """Walk autoAssign rules in order; first-match-wins per node leaf name.

    Matches the viewer's runtime behavior: rules are tested against the bare
    leaf name (`node.name`), not the full path. Descendant inheritance is not
    modeled here; nodes uncovered by direct rules will still inherit their
    nearest matched ancestor's category at render time.

    Per-node `category` overrides bypass autoAssign matching for that node and
    count toward `covered_via_overrides`. Per-node entries without a category
    (e.g., displayName-only) are not treated as covered.

    Sample lists are capped at the first 10 paths in the input order so the
    report stays readable on large GLBs.
    """
    overrides = {p for p, n in spec.nodes.items() if n.category is not None}
    rule_counts = [0] * len(spec.auto_assign)
    rule_samples = [[] for _ in spec.auto_assign]
    covered_autoAssign = 0
    covered_overrides = 0
    uncovered_sample = []
    uncovered_count = 0

    direct_match = {}
    for path in glb_node_paths:
        if path in overrides:
            covered_overrides += 1
            direct_match[path] = True
            continue
        matched = False
        for i, rule in enumerate(spec.auto_assign):
            if _leaf_matches(path, rule["match"]):
                rule_counts[i] += 1
                if len(rule_samples[i]) < _COVERAGE_SAMPLE_LIMIT:
                    rule_samples[i].append(path)
                covered_autoAssign += 1
                matched = True
                break
        direct_match[path] = matched
        if not matched:
            uncovered_count += 1
            if len(uncovered_sample) < _COVERAGE_SAMPLE_LIMIT:
                uncovered_sample.append(path)

    # Effective coverage: walk the path tree top-down so each node inherits its
    # nearest matched ancestor (the same cascade viewer.js applies at render time).
    effective = {}
    truly_uncovered_sample = []
    truly_uncovered_count = 0
    for path in sorted(glb_node_paths, key=lambda p: p.count("/")):
        if direct_match[path]:
            effective[path] = True
            continue
        parent = "/".join(path.split("/")[:-1])
        effective[path] = effective.get(parent, False)
        if not effective[path]:
            truly_uncovered_count += 1
            if len(truly_uncovered_sample) < _COVERAGE_SAMPLE_LIMIT:
                truly_uncovered_sample.append(path)
    effective_count = sum(1 for v in effective.values() if v)

    return CoverageReport(
        total_nodes=len(glb_node_paths),
        covered_via_autoAssign=covered_autoAssign,
        covered_via_overrides=covered_overrides,
        uncovered=uncovered_count,
        uncovered_sample=uncovered_sample,
        rule_counts=rule_counts,
        rule_samples=rule_samples,
        effective_covered=effective_count,
        truly_uncovered=truly_uncovered_count,
        truly_uncovered_sample=truly_uncovered_sample,
    )


def validate_against_tree(spec: Spec, glb_node_paths: list[str]) -> list[str]:
    """Cross-validate the spec against the actual GLB tree.

    Returns a list of human-readable warning strings. Empty list = clean.
    """
    warnings = []
    path_set = set(glb_node_paths)

    for path in spec.nodes:
        if path not in path_set:
            warnings.append(f"nodes.{path}: no matching path in GLB tree")

    for rule in spec.auto_assign:
        match = rule["match"]
        if not any(fnmatchcase(p.split("/")[-1], match) for p in glb_node_paths):
            warnings.append(
                f"autoAssign match '{match}': zero leaf-name matches in GLB tree")

    for i, rule in enumerate(spec.rules):
        for key in ("hide", "show"):
            if key in rule:
                pat = rule[key]
                if not any(fnmatchcase(p, pat) for p in glb_node_paths) \
                        and not any(fnmatchcase(p.split("/")[-1], pat) for p in glb_node_paths):
                    warnings.append(
                        f"rules[{i}].{key} '{pat}': zero nodes in GLB tree")

    return warnings
