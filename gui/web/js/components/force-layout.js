// Deterministic force-directed layout (Fruchterman–Reingold with grid-limited repulsion).
// Generic: works on {id} nodes and {source, target, strength?} edges; knows nothing about ontologies.

export function seededRandom(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function forceLayout(nodes, edges, { iterations = 300, seed = 7, ideal = 70, gravity = 0.03 } = {}) {
  const n = nodes.length;
  const index = new Map(nodes.map((node, i) => [node.id, i]));
  const rand = seededRandom(seed);
  const radius = Math.sqrt(n + 1) * ideal * 0.6;
  const x = new Float64Array(n), y = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const angle = rand() * Math.PI * 2, r = Math.sqrt(rand()) * radius;
    x[i] = Math.cos(angle) * r;
    y[i] = Math.sin(angle) * r;
  }
  const links = [];
  for (const e of edges) {
    const s = index.get(e.source), t = index.get(e.target);
    if (s !== undefined && t !== undefined && s !== t) links.push([s, t, e.strength ?? 1]);
  }
  const k = ideal, k2 = k * k, cell = k * 3;
  const dx = new Float64Array(n), dy = new Float64Array(n);
  let temperature = radius / 3;
  const cool = temperature / (iterations + 1);

  for (let it = 0; it < iterations; it++) {
    dx.fill(0);
    dy.fill(0);
    // Repulsion between nodes in neighbouring grid cells.
    const grid = new Map();
    for (let i = 0; i < n; i++) {
      const key = `${Math.floor(x[i] / cell)},${Math.floor(y[i] / cell)}`;
      (grid.get(key) || grid.set(key, []).get(key)).push(i);
    }
    for (let i = 0; i < n; i++) {
      const cx = Math.floor(x[i] / cell), cy = Math.floor(y[i] / cell);
      for (let ox = -1; ox <= 1; ox++) {
        for (let oy = -1; oy <= 1; oy++) {
          const bucket = grid.get(`${cx + ox},${cy + oy}`);
          if (!bucket) continue;
          for (const j of bucket) {
            if (j <= i) continue;
            let ddx = x[i] - x[j], ddy = y[i] - y[j];
            let d2 = ddx * ddx + ddy * ddy;
            if (d2 < 0.01) { ddx = (rand() - 0.5); ddy = (rand() - 0.5); d2 = 0.5; }
            const f = k2 / d2;
            dx[i] += ddx * f; dy[i] += ddy * f;
            dx[j] -= ddx * f; dy[j] -= ddy * f;
          }
        }
      }
    }
    // Attraction along edges.
    for (const [s, t, strength] of links) {
      const ddx = x[s] - x[t], ddy = y[s] - y[t];
      const d = Math.sqrt(ddx * ddx + ddy * ddy) || 0.01;
      const f = (d / k) * strength;
      dx[s] -= ddx * f; dy[s] -= ddy * f;
      dx[t] += ddx * f; dy[t] += ddy * f;
    }
    // Gravity and capped displacement.
    for (let i = 0; i < n; i++) {
      dx[i] -= x[i] * gravity;
      dy[i] -= y[i] * gravity;
      const d = Math.sqrt(dx[i] * dx[i] + dy[i] * dy[i]) || 1;
      const step = Math.min(d, temperature);
      x[i] += (dx[i] / d) * step;
      y[i] += (dy[i] / d) * step;
    }
    temperature = Math.max(temperature - cool, 1);
  }
  const positions = new Map();
  nodes.forEach((node, i) => positions.set(node.id, { x: x[i], y: y[i] }));
  return positions;
}
