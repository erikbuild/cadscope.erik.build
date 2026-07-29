// ABOUTME: Coral Wave easter egg — renders Accent parts as dual-extruded
// ABOUTME: teal/magenta filament split about each part's centerline.

const hexToRgb = (hex) => [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);

export const CORAL_TEAL = hexToRgb('0177a1');
export const CORAL_MAGENTA = hexToRgb('c22376');

const BLEND_FRACTION = 0.08;     // blend band as a fraction of part width
const WAVE_CYCLES = 6;           // boundary undulations over the part's height
const WAVE_AMP_FRACTION = 0.35;  // wave amplitude relative to the blend half-width

export function coralWaveMode(urlParams) {
  const value = (urlParams.get('filament') || '').toLowerCase();
  return (value === 'coralwave' || value === 'coralwavehilbert') ? value : null;
}

export function splitUniformsForBox(box) {
  const width = box.max.x - box.min.x;
  const height = Math.max(box.max.y - box.min.y, box.max.z - box.min.z);
  const blendHalf = Math.max((width * BLEND_FRACTION) / 2, 1e-4);
  return {
    splitX: (box.min.x + box.max.x) / 2,
    blendHalf,
    waveFreq: height > 0 ? (WAVE_CYCLES * 2 * Math.PI) / height : 1,
    waveAmp: blendHalf * WAVE_AMP_FRACTION,
  };
}

// Hilbert d→(x,y) traversal; returns every cell center of the 2^order grid
// in curve order, scaled into the unit square.
export function hilbertCurve(order) {
  const n = 1 << order;
  const pts = [];
  for (let d = 0; d < n * n; d++) {
    let t = d, x = 0, y = 0;
    for (let s = 1; s < n; s *= 2) {
      const rx = 1 & Math.floor(t / 2);
      const ry = 1 & (t ^ rx);
      if (ry === 0) {
        if (rx === 1) { x = s - 1 - x; y = s - 1 - y; }
        const tmp = x; x = y; y = tmp;
      }
      x += s * rx;
      y += s * ry;
      t = Math.floor(t / 4);
    }
    pts.push([(x + 0.5) / n, (y + 0.5) / n]);
  }
  return pts;
}

// Draws the curve as a thick white polyline on black — the repeatable
// mask texture the shader samples for the bottom-layer pattern.
export function drawHilbertPattern(ctx, size, order = 6) {
  const pts = hilbertCurve(order);
  ctx.fillStyle = '#000000';
  ctx.fillRect(0, 0, size, size);
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = (size / (1 << order)) * 0.5;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.beginPath();
  ctx.moveTo(pts[0][0] * size, pts[0][1] * size);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0] * size, pts[i][1] * size);
  ctx.stroke();
}

// Injected into MeshStandardMaterial. The vertex chunk forwards world position
// and normal; the fragment chunk replaces the diffuse color with the
// two-filament mix, then stamps the hilbert bottom-layer pattern onto
// out-facing flats (|world normal · X| < 0.5) in the opposite color + relief.
export const CORAL_GLSL = `
  float boundary = uSplitX
    + uWaveAmp * sin(vCoralWorldPos.y * uWaveFreq)
    + uWaveAmp * 0.5 * sin(vCoralWorldPos.z * uWaveFreq * 1.7 + 1.3);
  float t = smoothstep(boundary - uBlendHalf, boundary + uBlendHalf, vCoralWorldPos.x);
  diffuseColor.rgb = mix(uCoralTeal, uCoralMagenta, t);
  vec3 coralN = normalize(vCoralWorldNormal);
  if (abs(coralN.x) < 0.5) {
    vec2 huv = (abs(coralN.y) > abs(coralN.z) ? vCoralWorldPos.xz : vCoralWorldPos.xy) / uHilbertScale;
    float hMask = texture2D(uHilbertTex, huv).r;
    float hShift = texture2D(uHilbertTex, huv + vec2(0.004, -0.004)).r;
    vec3 hOpposite = mix(uCoralMagenta, uCoralTeal, t);
    diffuseColor.rgb = mix(diffuseColor.rgb, hOpposite, hMask * uHilbertTint);
    diffuseColor.rgb *= clamp(1.0 + uHilbertRelief * (hMask - hShift), 0.6, 1.4);
  }
`;

export function patchMaterial(material, uniforms) {
  material._coralWave = true;
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uSplitX = { value: uniforms.splitX };
    shader.uniforms.uBlendHalf = { value: uniforms.blendHalf };
    shader.uniforms.uWaveFreq = { value: uniforms.waveFreq };
    shader.uniforms.uWaveAmp = { value: uniforms.waveAmp };
    shader.uniforms.uCoralTeal = { value: CORAL_TEAL };
    shader.uniforms.uCoralMagenta = { value: CORAL_MAGENTA };
    shader.uniforms.uHilbertTex = { value: uniforms.hilbertTex ?? null };
    shader.uniforms.uHilbertScale = { value: uniforms.hilbertScale ?? 0.025 };
    shader.uniforms.uHilbertTint = { value: uniforms.hilbertTint ?? 0.5 };
    shader.uniforms.uHilbertRelief = { value: uniforms.hilbertRelief ?? 0.6 };
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>',
        '#include <common>\nvarying vec3 vCoralWorldPos;\nvarying vec3 vCoralWorldNormal;')
      .replace('#include <begin_vertex>',
        `#include <begin_vertex>
         vCoralWorldPos = (modelMatrix * vec4(position, 1.0)).xyz;
         vCoralWorldNormal = normalize(mat3(modelMatrix) * objectNormal);`);
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>',
        `#include <common>
         varying vec3 vCoralWorldPos;
         varying vec3 vCoralWorldNormal;
         uniform float uSplitX; uniform float uBlendHalf;
         uniform float uWaveFreq; uniform float uWaveAmp;
         uniform vec3 uCoralTeal; uniform vec3 uCoralMagenta;
         uniform sampler2D uHilbertTex; uniform float uHilbertScale;
         uniform float uHilbertTint; uniform float uHilbertRelief;`)
      .replace('#include <color_fragment>', `#include <color_fragment>\n${CORAL_GLSL}`);
  };
  material.needsUpdate = true;
}
