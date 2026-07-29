// ABOUTME: Viewer settings store (localStorage-backed) and the SpaceMouse
// ABOUTME: axis-remapping math: signed-permutation matrices from mapping rows.

const STORAGE_KEY = 'cadscope-settings';

export const DEFAULT_SETTINGS = Object.freeze({
  spacemouse: {
    enabled: false,
    mapping: {
      lr: { pair: 'x', invert: false },   // Left/Right
      io: { pair: 'z', invert: false },   // In/Out
      ud: { pair: 'y', invert: false },   // Up/Down
    },
  },
  special: {
    filament: 'standard',   // 'standard' | 'coralwave' | 'coralwavehilbert'
  },
});

function isPlainObject(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function deepMerge(base, overlay) {
  const out = structuredClone(base);
  if (!isPlainObject(overlay)) return out;
  for (const [key, value] of Object.entries(overlay)) {
    if (!(key in out)) continue;
    if (isPlainObject(out[key]) && isPlainObject(value)) {
      out[key] = deepMerge(out[key], value);
    } else if (typeof value === typeof out[key]) {
      out[key] = value;
    }
  }
  return out;
}

export function loadSettings(storage) {
  let parsed = null;
  try {
    parsed = JSON.parse(storage.getItem(STORAGE_KEY));
  } catch {
    parsed = null;
  }
  return deepMerge(DEFAULT_SETTINGS, parsed);
}

export function saveSettings(storage, settings) {
  storage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

// Keeps the three rows a permutation: when changedRow takes a pair another
// row holds, that row receives changedRow's previous pair.
export function normalizeMapping(mapping, changedRow) {
  const out = structuredClone(mapping);
  const taken = out[changedRow].pair;
  const other = Object.keys(out).find((row) => row !== changedRow && out[row].pair === taken);
  if (other) {
    const pairs = new Set(['x', 'y', 'z']);
    for (const row of Object.keys(out)) {
      if (row !== other) pairs.delete(out[row].pair);
    }
    out[other].pair = [...pairs][0];
  }
  return out;
}

export function applySwapPreset(mapping) {
  const out = structuredClone(mapping);
  out.lr.pair = 'x';
  out.io.pair = 'y';
  out.ud.pair = 'z';
  return out;
}

export function isSwapPreset(mapping) {
  return mapping.lr.pair === 'x' && mapping.io.pair === 'y' && mapping.ud.pair === 'z';
}

export function isIdentityMapping(mapping) {
  const d = DEFAULT_SETTINGS.spacemouse.mapping;
  return Object.keys(d).every((row) =>
    mapping[row].pair === d[row].pair && mapping[row].invert === false);
}

// Puck directions ↔ signed halves of the three mapping rows. World axis
// halves are named after the motions they produce by default: ±X =
// right/left, ±Y = up/down, ±Z = out/in.
const DIRECTIONS = {
  right: { row: 'lr', sign: 1 },
  left:  { row: 'lr', sign: -1 },
  out:   { row: 'io', sign: 1 },
  in:    { row: 'io', sign: -1 },
  up:    { row: 'ud', sign: 1 },
  down:  { row: 'ud', sign: -1 },
};

const AXIS_ACTIONS = {
  x: { 1: 'right', [-1]: 'left' },
  y: { 1: 'up', [-1]: 'down' },
  z: { 1: 'out', [-1]: 'in' },
};

const ACTION_AXES = {
  right: { pair: 'x', sign: 1 },
  left:  { pair: 'x', sign: -1 },
  up:    { pair: 'y', sign: 1 },
  down:  { pair: 'y', sign: -1 },
  out:   { pair: 'z', sign: 1 },
  in:    { pair: 'z', sign: -1 },
};

// The motion action a puck direction currently performs, e.g. 'right'.
export function actionForDirection(mapping, direction) {
  const { row, sign } = DIRECTIONS[direction];
  const entry = mapping[row];
  return AXIS_ACTIONS[entry.pair][sign * (entry.invert ? -1 : 1)];
}

// Retargets a puck direction to a motion action. The opposite direction
// follows automatically (same physical axis); the row that owned the
// action's axis receives the displaced one via normalizeMapping.
export function setDirectionAction(mapping, direction, action) {
  const { row, sign } = DIRECTIONS[direction];
  const target = ACTION_AXES[action];
  const out = structuredClone(mapping);
  out[row].pair = target.pair;
  out[row].invert = target.sign * sign < 0;
  return normalizeMapping(out, row);
}

const AXIS_ROW = { x: 0, y: 1, z: 2 };

// Column-major signed permutation. Driver space convention: Left/Right is
// its X (column 0), Up/Down its Y (column 1), In/Out its Z (column 2);
// each column becomes the signed world axis the row is mapped to.
export function remapMatrixFromMapping(mapping) {
  const m = [0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,1];
  const columns = { lr: 0, ud: 1, io: 2 };
  for (const [row, col] of Object.entries(columns)) {
    m[col * 4 + AXIS_ROW[mapping[row].pair]] = mapping[row].invert ? -1 : 1;
  }
  return m;
}

export function mat4Multiply(a, b) {
  const out = new Array(16).fill(0);
  for (let col = 0; col < 4; col++) {
    for (let row = 0; row < 4; row++) {
      let s = 0;
      for (let k = 0; k < 4; k++) s += a[k * 4 + row] * b[col * 4 + k];
      out[col * 4 + row] = s + 0;   // normalize -0
    }
  }
  return out;
}

export function mat4Transpose(m) {
  const out = new Array(16);
  for (let col = 0; col < 4; col++) {
    for (let row = 0; row < 4; row++) out[row * 4 + col] = m[col * 4 + row];
  }
  return out;
}

export function applyMat4ToVec3(m, v) {
  return [
    m[0] * v[0] + m[4] * v[1] + m[8] * v[2] + m[12] + 0,
    m[1] * v[0] + m[5] * v[1] + m[9] * v[2] + m[13] + 0,
    m[2] * v[0] + m[6] * v[1] + m[10] * v[2] + m[14] + 0,
  ];
}
