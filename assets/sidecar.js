// ABOUTME: Turns a model's colors.json sidecar into lookup tables for its palette, autoAssign rules, and nodes.
// ABOUTME: Looks up a scene node's sidecar entry by its slash-joined path.

// Translate a shell-style glob (* and ?) to an anchored regex.
function globToRegExp(glob) {
  const escaped = glob.replace(/[.+^${}()|[\]\\]/g, '\\$&');
  const pattern = escaped.replace(/\*/g, '.*').replace(/\?/g, '.');
  return new RegExp('^' + pattern + '$');
}

// Resolve a sidecar into ready-to-query lookup tables.
// palette: name -> { color, metalness, opacity, showInPicker, showInTree }
// autoAssign: ordered [{ category, regex }] — first match wins
// nodesByPath: full slash-joined path -> entry (a top-level node's path is its bare name)
export function buildSidecarLookups(colorSet) {
  const palette = new Map();
  const autoAssign = [];
  const nodesByPath = new Map();

  if (colorSet?.palette) {
    for (const [name, raw] of Object.entries(colorSet.palette)) {
      palette.set(name, {
        color: raw.color,
        metalness: raw.metalness ?? 0.0,
        opacity: raw.opacity ?? 1.0,
        showInPicker: raw.showInPicker !== false,
        showInTree: raw.showInTree !== false,
      });
    }
  }

  if (Array.isArray(colorSet?.autoAssign)) {
    for (const rule of colorSet.autoAssign) {
      if (!rule || !rule.category || !rule.match) continue;
      if (!palette.has(rule.category)) {
        console.warn(`Sidecar autoAssign rule references category "${rule.category}" which is not defined in palette.`);
      }
      autoAssign.push({ category: rule.category, regex: globToRegExp(rule.match) });
    }
  }

  if (colorSet?.nodes) {
    for (const [key, entry] of Object.entries(colorSet.nodes)) {
      if (entry?.category && !palette.has(entry.category)) {
        console.warn(`Sidecar node "${key}" references category "${entry.category}" which is not defined in palette.`);
      }
      nodesByPath.set(key, entry);
    }
  }

  return { palette, autoAssign, nodesByPath };
}

// Look up the sidecar entry for a node by its path.
export function lookupNode(lookups, path) {
  if (!lookups) return null;
  return lookups.nodesByPath.get(path) || null;
}
