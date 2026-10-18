# ABOUTME: GLB introspection helpers — read the JSON chunk and walk the node tree.
# ABOUTME: Names are normalized to match what the CADScope viewer sees at runtime.

"""
GLB introspection helpers shared by the model_converter tooling.

Names are cleaned and sanitized to match Three.js's view at runtime (see
PropertyBinding.sanitizeNodeName), so the paths produced here line up with
viewer-side node lookups. This is distinct from the cleaning that
blender_export.py does on FreeCAD/Blender object names during export.
"""

import json
import re
import struct


def clean_node_name(name):
    """Clean a glTF node name to match what the CADScope viewer sees.

    Strips .step / (mesh) / (group) suffixes (mirroring blender_export.py),
    then applies Three.js PropertyBinding.sanitizeNodeName(): converts spaces
    to underscores and strips characters reserved for animation paths
    ([ ] . : /).
    """
    if not name:
        return name
    clean = name.split("/")[-1]
    clean = re.sub(r"\.step(-\d+)$", r"\1", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\.step$", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*\(mesh\)\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*\(group\)\s*", "", clean, flags=re.IGNORECASE)
    # Three.js sanitizeNodeName: spaces → underscores, strip [ ] . : /
    clean = clean.replace(" ", "_")
    clean = re.sub(r'[\[\].:\/]', '', clean)
    return clean.strip()


def sanitize_node_name(name):
    """Apply Three.js PropertyBinding.sanitizeNodeName() to a raw glTF name.

    Whitespace becomes underscores and the animation-path characters
    [ ] . : / are stripped. GLTFLoader uses the result as the key when it
    makes node names unique.
    """
    return re.sub(r"[\[\].:\/]", "", re.sub(r"\s", "_", name))


def strip_numeric_suffix(name):
    """Strip a trailing -N suffix.

    Operates on already-cleaned GLB node names where the only surviving
    instance pattern is the STEP -N suffix.
    """
    return re.sub(r"-\d+$", "", name)


def read_glb_json(path):
    """Read and parse the JSON chunk from a GLB file."""
    with open(path, "rb") as f:
        magic = f.read(4)
        if magic != b"glTF":
            raise ValueError(f"Not a GLB file: {path}")
        version, total_length = struct.unpack("<II", f.read(8))
        chunk_length, chunk_type = struct.unpack("<II", f.read(8))
        if chunk_type != 0x4E4F534A:  # "JSON" in little-endian
            raise ValueError("First GLB chunk is not JSON")
        return json.loads(f.read(chunk_length))


def extract_names(glb_json):
    """Extract sorted unique group and part names from glTF nodes."""
    nodes = glb_json.get("nodes", [])

    # Build parent map
    parent_of = {}
    for i, n in enumerate(nodes):
        for child_idx in n.get("children", []):
            parent_of[child_idx] = i

    mesh_seen = set()
    mesh_names = []
    group_seen = set()
    group_names = []

    for i, n in enumerate(nodes):
        if "mesh" not in n:
            continue

        cleaned = clean_node_name(n.get("name", ""))
        if cleaned:
            key = strip_numeric_suffix(cleaned)
            if key not in mesh_seen:
                mesh_seen.add(key)
                mesh_names.append(key)

        if i in parent_of:
            parent_name = clean_node_name(nodes[parent_of[i]].get("name", ""))
            if parent_name:
                pkey = strip_numeric_suffix(parent_name)
                if pkey not in group_seen:
                    group_seen.add(pkey)
                    group_names.append(pkey)

    mesh_names.sort(key=str.casefold)
    group_names.sort(key=str.casefold)
    return group_names, mesh_names


def build_node_paths(glb_json):
    """Walk the default scene's node tree and return ordered (path, name) pairs.

    Mirrors the viewer's path logic: paths are slash-joined cleaned node names
    relative to the visual root, with the root itself excluded. When the scene
    has a single root node, that node IS the visual root (its children are
    depth 1, path = their own name). When it has multiple roots, the visual
    root is the synthetic Three.js Scene group, so each glTF root is depth 1.

    Nameless nodes are skipped from the output but are descended through, so
    their named descendants still appear at the right depth.

    Repeated names get the suffixes Three.js GLTFLoader gives them
    (createUniqueName): the scene name is reserved first, then each node's
    name in depth-first order, and every repeat of a sanitized name gains
    _1, _2, ... The viewer builds its paths from those names. This models a
    GLB with a single scene, which is what the converter exports.
    """
    nodes = glb_json.get("nodes", [])
    scenes = glb_json.get("scenes", [])
    if not scenes:
        return []
    scene_idx = glb_json.get("scene", 0)
    if scene_idx >= len(scenes):
        scene_idx = 0
    root_indices = scenes[scene_idx].get("nodes", [])

    pairs = []
    names_used = {}

    def loader_suffix(raw_name):
        """Reserve a name the way GLTFLoader does; return its _N suffix, if any."""
        key = sanitize_node_name(raw_name)
        if key in names_used:
            names_used[key] += 1
            return f"_{names_used[key]}"
        names_used[key] = 0
        return ""

    if scenes[scene_idx].get("name"):
        loader_suffix(scenes[scene_idx]["name"])

    def dfs(node_idx, ancestors):
        node = nodes[node_idx]
        raw_name = node.get("name")
        name = clean_node_name(raw_name) + loader_suffix(raw_name) if raw_name else ""
        if name:
            components = ancestors + [name]
            pairs.append(("/".join(components), name))
            child_ancestors = components
        else:
            child_ancestors = ancestors
        for child_idx in node.get("children", []):
            dfs(child_idx, child_ancestors)

    if len(root_indices) == 1:
        root = nodes[root_indices[0]]
        if root.get("name"):
            loader_suffix(root["name"])
        for child_idx in root.get("children", []):
            dfs(child_idx, [])
    else:
        for root_idx in root_indices:
            dfs(root_idx, [])

    return pairs
