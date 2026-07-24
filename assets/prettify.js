// ABOUTME: Turns raw CAD node names into human-readable scene-tree labels.
// ABOUTME: Strips duplicate suffixes, converts underscores, capitalizes lowercase words.

// Prettify a raw node name for display: strip CAD duplicate suffixes
// ("(N)" copies, trailing runs of 3+ digits, "-N" dedup) and lowercase
// version markers ("v2"), turn underscores into spaces, and capitalize
// all-lowercase words. Words
// already containing a capital or digit are left untouched so acronyms
// and part codes (XZ, SHCS, M3x8) survive. Returns the raw name when
// stripping would leave nothing.
// Resolve the scene-tree label for a node: with prettify on, a sidecar
// displayName wins, otherwise the raw name is prettified; with prettify
// off, the raw name is returned untouched so the tree shows exactly what
// spec paths and autoAssign globs match against. Callers supply their own
// fallback for nameless nodes.
export function treeLabel(rawName, displayName, prettify) {
  if (!prettify) return rawName;
  return displayName || prettifyNodeName(rawName);
}

export function prettifyNodeName(name) {
  if (!name) return name;
  let s = name;
  let prev;
  do {
    prev = s;
    s = s.replace(/[_ ]?\(\d+\)$/, '');   // CAD duplicate "(N)"
    s = s.replace(/(\D)\d{3,}$/, '$1');   // trailing run of 3+ digits
    s = s.replace(/-\d+$/, '');           // pipeline dedup "-N"
    s = s.replace(/[_ -]v\d+$/, '');      // version marker "v2" (lowercase only)
    s = s.replace(/[_ -]+$/, '');         // dangling separators
  } while (s !== prev);                   // stacked suffixes strip until stable
  if (!s) return name;
  const out = s.split('_').filter(Boolean)
    .map(w => /^[a-z]+$/.test(w) ? w[0].toUpperCase() + w.slice(1) : w)
    .join(' ');
  return out || name;
}
