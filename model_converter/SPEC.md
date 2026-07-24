# `<model>.spec.yaml` reference

The spec file is the source of truth for a configurable model. `build_configurator.py`
reads it and emits two artifacts:

- `<model>.colors.json` — the CADScope viewer sidecar (palette, autoAssign, nodes).
- `<model>.manifest.json` — the Prusawire-Configurator manifest (options, parts, STL paths).

Both outputs live next to the GLB:

```
models/Toolhead/
  Toolhead.glb              # composite GLB from the STEP→GLB pipeline
  Toolhead.spec.yaml        # this file (hand-edited)
  Toolhead.scaffold.json    # generated reference dump (gitignored)
  Toolhead.colors.json      # generated CADScope sidecar
  Toolhead.manifest.json    # generated Prusawire manifest
```

## Top-level structure

```yaml
model:
  name: "Display Name"     # optional; shown in UIs
  glb: relative/file.glb   # required; relative to the spec file

palette:                   # required; at least one category
  CategoryName: { color: "#rrggbb", metalness: 0.0, opacity: 1.0, showInPicker: true }

autoAssign:                # optional; in-order, first match wins
  - { match: "<glob>", category: CategoryName }

options:                   # optional; user-facing choices
  optionId:                # see "Option types" below
    label: "Label"
    description: "..."     # optional; help copy rendered beside the question
    type: radio            # bool|radio|dropdown; unknown values pass through
    choices: [...]

compatibility:             # optional; cross-option warnings (informational)
  - when: { optA: x, optB: y }
    incompatible: true
    message: "..."

nodes:                     # optional; per-node overrides keyed by GLB path
  Path/From/Visual/Root:
    displayName: "..."
    category: CategoryName
    visible: { when: {...}, unless: {...} }
    hidden: false
    visualOnly: false
    stl: "rel/path.stl"   # or [list, of, paths]

rules:                     # optional; cross-cutting glob rules
  - { hide: "Glob/*", when: { optionId: value } }
  - { show: "Other/*", when: { boolOption: true } }

stlBase: "https://..."     # optional; prepended to per-node `stl:` paths in the manifest
```

Required: `model.glb`, `palette` (non-empty). Everything else is optional.

## Palette entries

| Field          | Type    | Default | Notes                                             |
|----------------|---------|---------|---------------------------------------------------|
| `color`        | string  |         | `#RRGGBB`. Required for entries used for picking. |
| `metalness`    | number  | 0.0     | 0.0–1.0; passed to the viewer's MeshStandardMaterial. |
| `opacity`      | number  | 1.0     | 0.0–1.0; <1.0 enables transparent rendering.      |
| `showInPicker` | boolean | true    | Set `false` to hide this category from the sidebar color picker. |
| `showInTree`   | boolean | true    | Set `false` to drop every node whose effective category resolves to this one from the scene-hierarchy tree. Render and color application are unaffected; children whose own category resolves to a visible category promote up to the nearest non-hidden ancestor. |

## autoAssign rules

```yaml
autoAssign:
  - { match: "M3*",      category: Hardware }   # leaf-name glob
  - { match: "*Bearing*", category: Linear }
  - { match: "Frame",    category: Frame }      # bare top-level group
```

Each rule pairs a glob with a category. At runtime, every node in the GLB
walks the rules in declaration order and takes the **first** matching rule's
category — no fall-through, no overwrite. Per-node `category` overrides win
before any rule is tested.

### Matching: leaf names only

Globs match against the **bare leaf name** of a node (`node.name` in
`viewer.js:533`), not the full slash-joined path. Patterns like `Frame/*` or
`Electronics/*` are dead — leaves never contain `/`. To match a top-level
group, use the bare name (`Frame`) or a leaf-name glob that hits it
(`Frame*`).

### Descendant cascade

The viewer applies categories top-down: a node without its own match
inherits the nearest matched ancestor's category (`viewer.js:541-542`). One
rule that hits a top-level group leaf — e.g. `{ match: "Frame", category:
Frame }` — colors the entire `Frame` subtree, because every descendant
inherits.

This is why `--check` reports two coverage numbers:

- **direct**: nodes whose own leaf name fired a rule (or whose entry has an
  explicit `category` override). Tells you which rules are doing real
  matching work.
- **effective**: direct + everything covered by the cascade. Tells you what
  the viewer will actually render. A spec where a few group-level rules hit
  bare top-level group nodes typically reads as low direct / high
  effective — and that's fine.

A node is **truly uncovered** only when neither it nor any ancestor matched.
Truly-uncovered subtrees render with the default material; if you see them
in `--check`, that's where you need a new rule or override.

### Ordering

First-match-wins, so put **specific rules early** and broad fallbacks late:

```yaml
autoAssign:
  - { match: "M3*",       category: Hardware }   # specific, anywhere in tree
  - { match: "*Bearing*", category: Linear }
  - { match: "Frame",     category: Frame }      # group-level fallback
```

A `Frame/Foo/M3_Bolt` node matches `M3*` first (leaf is `M3_Bolt`) and gets
Hardware, even though it's inside a Frame subtree. The cascade only fills in
nodes that match nothing.

## Option types

Every option carries an optional `label:` (defaults to the option id), an
optional `description:` (free-text help copy the configurator UI may render
beside the question), and a `type:` that hints the desired widget. Recognized
`type:` values are listed below; unknown values pass through to `manifest.json`
verbatim so future configurator UIs can introduce new widgets (`tabs`,
`image_grid`, etc.) without bumping the spec schema.

### Selection option

```yaml
carriage:
  label: "Carriage"
  description: "Which carriage variant ships on the gantry."
  choices:
    - { id: xol,   label: "Xol Carriage",
        description: "Original design. Aluminium body, magnetic probe mount.",
        default: true }
    - { id: omron, label: "Omron Carriage",
        description: "Drop-in upgrade using the Omron TL-Q5MB1 inductive probe." }
```

`id` is required on each choice; `label` defaults to `id`; `description` is
optional. One choice may be `default: true`; if none is flagged, the first is
used. `type:` defaults to `radio`. Set `type: dropdown` to hint a collapsed
`<select>` widget — typical for long choice lists.

### Boolean option

```yaml
hexCowl:
  label: "Hex multi-colour cowl?"
  description: "Adds the optional patterned top cowl. Heavier; needs 4 extra M3x10 screws."
  type: bool
  default: false
```

`description:` is optional and renders the same way as on selection options.

## Node entries

Keys are slash-joined paths from the GLB visual root (the same path scheme the
CADScope viewer uses internally). Use `<model>.scaffold.json` (regenerated by
`build_configurator.py`) to find available paths.

| Field         | Effect on `colors.json`                | Effect on `manifest.json`                       |
|---------------|----------------------------------------|-------------------------------------------------|
| `displayName` | sets `nodes.<path>.displayName`        | (none)                                          |
| `category`    | sets `nodes.<path>.category`           | (none)                                          |
| `hidden`      | sets `hidden: true` if true            | adds the node to `parts[]` with `hidden: true` |
| `visible`     | hides if invisible under default config | becomes `parts[].visible.{when,unless}`        |
| `visualOnly`  | (none)                                 | sets `parts[].visualOnly: true` (excluded from STL zip) |
| `stl`         | (none)                                 | sets `parts[].stl: [...]`                      |
| `showInTree`  | sets `showInTree: false` when explicitly false (default true is not emitted) | (none) — render and download manifest are unaffected |

Setting `showInTree: false` on a per-node entry takes precedence over its
palette category. Descendants of a hidden node promote up to the nearest
visible ancestor in the tree.

A node entry is included in the generated `colors.json.nodes` map only when it
carries persistent metadata (a `displayName`, an explicit `category`, or is hidden
under the default config). Anything visible-by-default with no other metadata is
left out and falls through to `autoAssign`.

A node enters `manifest.json.parts[]` only when it has a visibility rule or an STL.

## Visibility DSL

```yaml
visible:
  when:    { optionId: value, ... }    # all keys must match the user's config
  unless:  { optionId: value, ... }    # any key matching hides the node
```

A node is visible iff its `when` clause matches AND its `unless` clause does not.

- A clause is a mapping of option-id → expected value(s).
- Within a clause, all keys are AND-conjoined.
- A list-valued entry is OR-disjoined within that one key.
- An empty clause is trivially satisfied.

Boolean options use Python booleans (`true` / `false`).

```yaml
visible:
  when:
    extruder: [wwbmg, sherpa]   # OR within key
    hotend: dragon              # AND across keys
  unless:
    filamentCutter: crossbow
```

## Cross-cutting `rules`

```yaml
rules:
  - { hide: "Cowlings/*", when: { hexCowl: true } }
  - { show: "HexCowlings/*", when: { hexCowl: true } }
```

Each rule has a `hide` or `show` glob (matched against full paths and bare leaf
names) and an optional `when` clause. At generate time, the rule is expanded
into synthetic `parts[]` entries for matched GLB paths that aren't already
declared under `nodes:`. Nodes already in `nodes:` are not modified by rules —
put your override in `nodes:` directly.

## Generator CLI

```
build_configurator.py path/to/model.glb           # auto-detect mode
build_configurator.py path/to/model.glb -o out.json
build_configurator.py --scaffold-only path/to/model.glb
```

Auto-detection: if `<model>.spec.yaml` is present alongside the GLB, runs full
build (scaffold + colors.json + manifest.json). Otherwise runs in scaffold mode
(scaffold.json + a starter colors.json that's never overwritten).

Validator warnings are written to stderr; missing node paths and zero-match
globs are flagged but do not fail the build.

## Setup

```
cd model_converter
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python build_configurator.py path/to/model.glb
```

Tests:

```
cd model_converter
.venv/bin/python -m unittest discover -p "test_*.py"
```
