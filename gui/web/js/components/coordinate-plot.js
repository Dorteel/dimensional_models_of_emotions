// Coordinate plot for labelled points. Generic: knows nothing about OWL or emotions.
//
//   setData({axes: [{id, label, min?, max?, stated?}], points: [{id, label, values: [number], raw?: [string]}],
//            emptyMessage?})
//
//   0 axes  -> empty state (emptyMessage)
//   1 axis  -> number line
//   2 axes  -> scatterplot
//   3 axes  -> 3D view (drag to rotate, wheel to zoom, double-click to reset)
//
// Axis bounds: [min, max] when given (stated), widened only if a point lies outside; otherwise the data
// extent with padding. Events: "select" {detail: {id | null}}.

const SVG = "http://www.w3.org/2000/svg";
const el = (name, attrs = {}, text) => {
  const node = document.createElementNS(SVG, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  return node;
};
const textWidth = (s) => String(s).length * 6.4 + 4;
const DEFAULT_VIEW = { yaw: -0.65, pitch: 0.42, zoom: 1 };

export function niceTicks(min, max, count = 6) {
  const span = max - min;
  if (!(span > 0)) return [min];
  const raw = span / count, mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count) || 10 * mag;
  const ticks = [];
  for (let t = Math.ceil(min / step - 1e-9) * step; t <= max + 1e-9; t += step) ticks.push(+t.toPrecision(12));
  return ticks;
}

export function axisDomain(axis, values) {
  const lo = Math.min(...values), hi = Math.max(...values);
  if (axis.stated && axis.min !== null && axis.max !== null) {
    return { min: Math.min(axis.min, lo), max: Math.max(axis.max, hi), stated: true };
  }
  if (!values.length) return { min: -1, max: 1, stated: false };
  if (hi === lo) return { min: lo - 1, max: hi + 1, stated: false };
  const pad = (hi - lo) * 0.08;
  return { min: lo - pad, max: hi + pad, stated: false };
}

export class CoordinatePlot extends EventTarget {
  constructor(container) {
    super();
    this.container = container;
    this.svg = el("svg", { class: "coord-plot", tabindex: "0", role: "img", "aria-label": "Coordinate plot" });
    container.append(this.svg);
    this.data = null;
    this.selected = null;
    this.showLabels = true;
    this.view = { ...DEFAULT_VIEW };
    this._bind();
    new ResizeObserver(() => this.render()).observe(container);
  }

  setData(data) {
    this.data = data;
    this.selected = data.points.some((p) => p.id === this.selected) ? this.selected : null;
    this.render();
  }

  get mode() {
    const n = this.data?.axes.length ?? 0;
    return n === 0 || !this.data.points.length ? "empty" : n === 1 ? "1d" : n === 2 ? "2d" : "3d";
  }

  select(id, { emit = true } = {}) {
    this.selected = this.data?.points.some((p) => p.id === id) ? id : null;
    for (const g of this.svg.querySelectorAll(".pt")) g.classList.toggle("selected", g.dataset.id === this.selected);
    this.svg.classList.toggle("has-selection", !!this.selected);
    const sel = this.svg.querySelector(".pt.selected");
    if (sel) sel.parentNode.append(sel);
    if (emit) this.dispatchEvent(new CustomEvent("select", { detail: { id: this.selected } }));
  }

  setLabels(on) { this.showLabels = on; this.svg.classList.toggle("no-labels", !on); }

  setView(view) { this.view = { ...this.view, ...view }; if (this.mode === "3d") this.render(); }

  resetView() { this.view = { ...DEFAULT_VIEW }; this.render(); }

  size() {
    const r = this.container.getBoundingClientRect();
    return { w: Math.max(r.width, 200), h: Math.max(r.height, 160) };
  }

  render() {
    this.svg.replaceChildren();
    this.svg.dataset.mode = this.mode;
    if (!this.data) return;
    const { w, h } = this.size();
    this.svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    if (this.mode === "empty") {
      const msg = this.data.emptyMessage || "Nothing to plot.";
      msg.split("\n").forEach((line, i) =>
        this.svg.append(el("text", { x: w / 2, y: h / 2 - 10 + i * 20, class: "plot-empty" }, line)));
      return;
    }
    if (this.mode === "1d") this._render1D(w, h);
    else if (this.mode === "2d") this._render2D(w, h);
    else this._render3D(w, h);
    this.svg.classList.toggle("no-labels", !this.showLabels);
    this.select(this.selected, { emit: false });
  }

  _point(p, x, y, r = 5) {
    const g = el("g", { class: "pt", "data-id": p.id, "data-values": JSON.stringify(p.raw ?? p.values.map(String)) });
    g.append(el("circle", { cx: x, cy: y, r }));
    g.append(el("title", {}, `${p.label}\n${this.data.axes.map((a, i) => `${a.label}: ${(p.raw ?? p.values)[i]}`).join("\n")}`));
    return g;
  }

  _placeLabels(items, bounds) {
    // Greedy label placement: try a few offsets per point and keep the first that collides with nothing.
    const boxes = [];
    const overlaps = (b) => boxes.some((o) => b.x < o.x + o.w && o.x < b.x + b.w && b.y < o.y + o.h && o.y < b.y + b.h);
    for (const it of items) boxes.push({ x: it.x - 5, y: it.y - 5, w: 10, h: 10 });
    const out = [];
    for (const it of items) {
      const tw = textWidth(it.label), th = 12;
      const options = [[8, -4], [-8 - tw, -4], [-tw / 2, -10], [-tw / 2, 14], [8, -14], [8, 10], [-8 - tw, -14], [-8 - tw, 10]];
      let chosen = null;
      for (const [dx, dy] of options) {
        const b = { x: it.x + dx, y: it.y + dy - th + 3, w: tw, h: th };
        if (b.x < bounds.x0 || b.x + b.w > bounds.x1 || b.y < bounds.y0 || b.y + b.h > bounds.y1) continue;
        if (!overlaps(b)) { chosen = [dx, dy, b]; break; }
      }
      const [dx, dy, b] = chosen || [8, -4, null];
      if (b) boxes.push(b);
      out.push({ ...it, lx: it.x + dx, ly: it.y + dy, crowded: !chosen });
    }
    return out;
  }

  _label(g, item) {
    g.append(el("text", { x: item.lx, y: item.ly, class: `pt-label${item.crowded ? " crowded" : ""}` }, item.label));
  }

  // ---------------------------------------------------------------- 1D
  _render1D(w, h) {
    const axis = this.data.axes[0];
    const vals = this.data.points.map((p) => p.values[0]);
    const dom = axisDomain(axis, vals);
    const x0 = 60, x1 = w - 60, y = h / 2;
    const sx = (v) => x0 + ((v - dom.min) / (dom.max - dom.min)) * (x1 - x0);
    this._scales = { x: sx };
    const axisG = el("g", { class: "axis" });
    axisG.append(el("line", { x1: x0, y1: y, x2: x1, y2: y, class: "axis-line" }));
    for (const t of niceTicks(dom.min, dom.max)) {
      axisG.append(el("line", { x1: sx(t), y1: y - 4, x2: sx(t), y2: y + 4, class: "tick" }));
      axisG.append(el("text", { x: sx(t), y: y + 20, class: "tick-label" }, String(t)));
    }
    axisG.append(el("text", { x: (x0 + x1) / 2, y: y + 46, class: "axis-title" },
                    `${axis.label}${dom.stated ? "" : "  (range not stated; data extent)"}`));
    this.svg.append(axisG);
    const pts = el("g", { class: "points" });
    const sorted = this.data.points.map((p) => ({ p, x: sx(p.values[0]) })).sort((a, b) => a.x - b.x);
    const levels = { up: [], down: [] };
    sorted.forEach(({ p, x }, i) => {
      const g = this._point(p, x, y, 6);
      const side = i % 2 ? "down" : "up", tw = textWidth(p.label);
      let level = levels[side].findIndex((end) => end < x - tw / 2);
      if (level < 0) { level = levels[side].length; levels[side].push(0); }
      levels[side][level] = x + tw / 2 + 4;
      const ly = side === "up" ? y - 22 - level * 15 : y + 62 + level * 15;
      g.append(el("line", { x1: x, y1: y + (side === "up" ? -6 : 6), x2: x, y2: ly + (side === "up" ? 3 : -11), class: "leader" }));
      g.append(el("text", { x, y: ly, class: "pt-label centered" }, p.label));
      pts.append(g);
    });
    this.svg.append(pts);
  }

  // ---------------------------------------------------------------- 2D
  _render2D(w, h) {
    const [ax, ay] = this.data.axes;
    const dx = axisDomain(ax, this.data.points.map((p) => p.values[0]));
    const dy = axisDomain(ay, this.data.points.map((p) => p.values[1]));
    const m = { l: 64, r: 24, t: 20, b: 56 };
    const side = Math.min(w - m.l - m.r, h - m.t - m.b);   // square plot area: equal units when ranges match
    const x0 = m.l + (w - m.l - m.r - side) / 2, y1 = m.t + side, x1 = x0 + side, y0 = m.t;
    const sx = (v) => x0 + ((v - dx.min) / (dx.max - dx.min)) * (x1 - x0);
    const sy = (v) => y1 - ((v - dy.min) / (dy.max - dy.min)) * (y1 - y0);
    this._scales = { x: sx, y: sy };
    const g = el("g", { class: "axis" });
    g.append(el("rect", { x: x0, y: y0, width: x1 - x0, height: y1 - y0, class: "plot-area" }));
    for (const t of niceTicks(dx.min, dx.max)) {
      g.append(el("line", { x1: sx(t), y1: y0, x2: sx(t), y2: y1, class: t === 0 ? "zero" : "grid" }));
      g.append(el("text", { x: sx(t), y: y1 + 16, class: "tick-label" }, String(t)));
    }
    for (const t of niceTicks(dy.min, dy.max)) {
      g.append(el("line", { x1: x0, y1: sy(t), x2: x1, y2: sy(t), class: t === 0 ? "zero" : "grid" }));
      g.append(el("text", { x: x0 - 8, y: sy(t) + 4, class: "tick-label end" }, String(t)));
    }
    g.append(el("text", { x: (x0 + x1) / 2, y: y1 + 40, class: "axis-title" },
                `${ax.label}${dx.stated ? "" : " (range not stated)"}`));
    g.append(el("text", { x: 0, y: 0, class: "axis-title", transform: `translate(${x0 - 46},${(y0 + y1) / 2}) rotate(-90)` },
                `${ay.label}${dy.stated ? "" : " (range not stated)"}`));
    this.svg.append(g);
    const items = this.data.points.map((p) => ({ p, label: p.label, x: sx(p.values[0]), y: sy(p.values[1]) }));
    const pts = el("g", { class: "points" });
    for (const it of this._placeLabels(items, { x0, x1: w, y0: 0, y1 })) {
      const pg = this._point(it.p, it.x, it.y);
      this._label(pg, it);
      pts.append(pg);
    }
    this.svg.append(pts);
  }

  // ---------------------------------------------------------------- 3D
  project(n) { // n: normalised [-1, 1]^3 -> {x, y, depth}
    const { yaw, pitch, zoom } = this.view;
    const { w, h } = this.size();
    const s = Math.min(w, h) * 0.3 * zoom;
    const rx = n[0] * Math.cos(yaw) - n[1] * Math.sin(yaw);
    const ry = n[0] * Math.sin(yaw) + n[1] * Math.cos(yaw);
    const depth = ry * Math.cos(pitch) + n[2] * Math.sin(pitch);
    const up = -ry * Math.sin(pitch) + n[2] * Math.cos(pitch);
    return { x: w / 2 + s * rx, y: h / 2 - s * up, depth };
  }

  _render3D(w, h) {
    const axes = this.data.axes.slice(0, 3);
    const doms = axes.map((a, i) => axisDomain(a, this.data.points.map((p) => p.values[i])));
    const norm = (v, i) => (2 * (v - doms[i].min)) / (doms[i].max - doms[i].min) - 1;
    this._scales = { norm };
    const frame = el("g", { class: "axis" });
    const corners = [];
    for (const a of [-1, 1]) for (const b of [-1, 1]) for (const c of [-1, 1]) corners.push([a, b, c]);
    for (let i = 0; i < 8; i++) {
      for (let j = i + 1; j < 8; j++) {
        const diff = corners[i].filter((v, k) => v !== corners[j][k]).length;
        if (diff !== 1) continue;
        const p = this.project(corners[i]), q = this.project(corners[j]);
        frame.append(el("line", { x1: p.x, y1: p.y, x2: q.x, y2: q.y, class: "grid" }));
      }
    }
    axes.forEach((axis, i) => {
      const start = [-1, -1, -1], end = [-1, -1, -1];
      end[i] = 1;
      const p = this.project(start), q = this.project(end);
      frame.append(el("line", { x1: p.x, y1: p.y, x2: q.x, y2: q.y, class: `axis-line axis-${i}` }));
      for (const t of niceTicks(doms[i].min, doms[i].max, 4)) {
        const at = [-1, -1, -1]; at[i] = norm(t, i);
        const tp = this.project(at);
        frame.append(el("circle", { cx: tp.x, cy: tp.y, r: 1.5, class: "tick-dot" }));
        frame.append(el("text", { x: tp.x - 4, y: tp.y + 13, class: "tick-label small" }, String(t)));
      }
      // Title: pushed outward (in screen space) from the cube centre past the axis end, kept inside the view,
      // so it never covers the point at the cube corner.
      const text = `${axis.label}${doms[i].stated ? "" : " (range not stated)"}`;
      const centre = this.project([0, 0, 0]);
      let ux = q.x - centre.x, uy = q.y - centre.y;
      const len = Math.hypot(ux, uy) || 1;
      ux /= len; uy /= len;
      const tw = textWidth(text);
      const tx = Math.max(tw / 2 + 6, Math.min(w - tw / 2 - 6, q.x + ux * 34));
      const ty = Math.max(16, Math.min(h - 26, q.y + uy * 34 + 4));
      frame.append(el("text", { x: tx, y: ty, class: `axis-title axis-${i}` }, text));
    });
    this.svg.append(frame);
    const items = this.data.points.map((p) => {
      const pr = this.project(p.values.slice(0, 3).map((v, i) => norm(v, i)));
      return { p, label: p.label, x: pr.x, y: pr.y, depth: pr.depth };
    }).sort((a, b) => b.depth - a.depth);
    const pts = el("g", { class: "points" });
    const placed = this._placeLabels([...items].reverse(), { x0: 0, x1: w, y0: 0, y1: h });
    const byId = new Map(placed.map((it) => [it.p.id, it]));
    for (const it of items) {
      const r = 5.5 - it.depth * 1.5;
      const g = this._point(it.p, it.x, it.y, Math.max(3, r));
      g.style.opacity = String(Math.min(1, 0.75 - it.depth * 0.25));
      this._label(g, byId.get(it.p.id));
      pts.append(g);
    }
    this.svg.append(pts);
    this.svg.append(el("text", { x: 12, y: h - 12, class: "plot-hint" }, "Drag to rotate · wheel to zoom · double-click to reset"));
  }

  // ---------------------------------------------------------------- input
  _bind() {
    let drag = null;
    this.svg.addEventListener("pointerdown", (ev) => {
      if (ev.button !== 0) return;
      drag = { x: ev.clientX, y: ev.clientY, x0: ev.clientX, y0: ev.clientY, moved: false,
               id: ev.target.closest?.(".pt")?.dataset.id ?? null };
      try { this.svg.setPointerCapture(ev.pointerId); } catch { /* synthetic events */ }
    });
    this.svg.addEventListener("pointermove", (ev) => {
      if (!drag) return;
      const dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
      drag.x = ev.clientX; drag.y = ev.clientY;
      if (Math.hypot(ev.clientX - drag.x0, ev.clientY - drag.y0) > 4) drag.moved = true;
      if (drag.moved && this.mode === "3d") {
        this.view.yaw += dx * 0.01;
        this.view.pitch = Math.max(-1.5, Math.min(1.5, this.view.pitch + dy * 0.01));
        this.render();
      }
    });
    this.svg.addEventListener("pointerup", (ev) => {
      if (!drag) return;
      const { moved, id } = drag;
      drag = null;
      try { this.svg.releasePointerCapture(ev.pointerId); } catch { /* synthetic events */ }
      if (!moved) this.select(id);
    });
    this.svg.addEventListener("wheel", (ev) => {
      if (this.mode !== "3d") return;
      ev.preventDefault();
      this.view.zoom = Math.max(0.3, Math.min(5, this.view.zoom * Math.exp(-ev.deltaY * 0.0015)));
      this.render();
    }, { passive: false });
    this.svg.addEventListener("dblclick", () => { if (this.mode === "3d") this.resetView(); });
    this.svg.addEventListener("keydown", (ev) => {
      if (this.mode !== "3d") return;
      const k = { ArrowLeft: [-0.1, 0], ArrowRight: [0.1, 0], ArrowUp: [0, -0.1], ArrowDown: [0, 0.1] }[ev.key];
      if (k) { ev.preventDefault(); this.setView({ yaw: this.view.yaw + k[0], pitch: this.view.pitch + k[1] }); }
    });
  }
}
