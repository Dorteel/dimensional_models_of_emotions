// Interactive SVG graph: zoom (wheel / buttons), pan (drag background), drag nodes, select nodes.
// Generic component — it renders whatever {nodes, edges} it is given and knows nothing about OWL.
//
//   nodes: [{id, label, shape: "rect" | "circle", className?, title?}]
//   edges: [{id, source, target, label?, className?, strength?}]
//
// Events (EventTarget): "select" {detail: {id | null}}, "transform" {detail: {x, y, k}}.

import { forceLayout } from "./force-layout.js";

const SVG = "http://www.w3.org/2000/svg";
const el = (name, attrs = {}) => {
  const node = document.createElementNS(SVG, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
};

export class GraphView extends EventTarget {
  constructor(container, { minZoom = 0.05, maxZoom = 6, labelZoom = 1.1 } = {}) {
    super();
    this.container = container;
    this.minZoom = minZoom;
    this.maxZoom = maxZoom;
    this.labelZoom = labelZoom;
    this.t = { x: 0, y: 0, k: 1 };
    this.nodes = new Map();
    this.edges = [];
    this.selected = null;
    this.focus = { on: false, depth: 1 };
    this.nodeFilter = () => true;
    this.edgeFilter = () => true;

    this.svg = el("svg", { class: "graph-svg", role: "img", "aria-label": "Graph view" });
    const defs = el("defs");
    const marker = el("marker", { id: "arrow", viewBox: "0 0 10 10", refX: "10", refY: "5",
                                  markerWidth: "4.5", markerHeight: "4.5", orient: "auto-start-reverse" });
    marker.append(el("path", { d: "M 0 0 L 10 5 L 0 10 z", class: "arrow-head" }));
    defs.append(marker);
    this.viewport = el("g", { class: "viewport" });
    this.edgeLayer = el("g", { class: "edges" });
    this.edgeLabelLayer = el("g", { class: "edge-labels" });
    this.nodeLayer = el("g", { class: "nodes" });
    this.viewport.append(this.edgeLayer, this.nodeLayer, this.edgeLabelLayer);
    this.svg.append(defs, this.viewport);
    container.append(this.svg);
    this._bindEvents();
  }

  // ------------------------------------------------------------------ data
  setData({ nodes, edges }, layoutOptions = {}) {
    this.nodeLayer.replaceChildren();
    this.edgeLayer.replaceChildren();
    this.edgeLabelLayer.replaceChildren();
    this.nodes = new Map();
    this.selected = null;
    const positions = forceLayout(nodes, edges, layoutOptions);
    for (const n of nodes) {
      const p = positions.get(n.id);
      const g = el("g", { class: `node ${n.shape} ${n.className || ""}`.trim(), "data-id": n.id, tabindex: "-1" });
      const shape = n.shape === "rect" ? el("rect", { x: -9, y: -9, width: 18, height: 18, rx: 3 })
                                       : el("circle", { r: 6 });
      const text = el("text", { x: 11, y: 4 });
      text.textContent = n.label;
      const title = el("title");
      title.textContent = n.title || n.label;
      g.append(shape, text, title);
      this.nodeLayer.append(g);
      this.nodes.set(n.id, { ...n, x: p.x, y: p.y, el: g, edges: [] });
    }
    this.edges = [];
    for (const e of edges) {
      const s = this.nodes.get(e.source), t = this.nodes.get(e.target);
      if (!s || !t) continue;
      const line = el("line", { class: `edge ${e.className || ""}`.trim(), "marker-end": "url(#arrow)",
                                "data-source": e.source, "data-target": e.target });
      const label = el("text", { class: "edge-label" });
      label.textContent = e.label || "";
      this.edgeLayer.append(line);
      this.edgeLabelLayer.append(label);
      const edge = { ...e, s, t, el: line, labelEl: label };
      s.edges.push(edge);
      t.edges.push(edge);
      this.edges.push(edge);
    }
    for (const n of this.nodes.values()) this._placeNode(n);
    for (const e of this.edges) this._placeEdge(e);
    this.applyVisibility();
    this.fit();
  }

  // ------------------------------------------------------------------ visibility
  setFilters({ node, edge } = {}) {
    if (node) this.nodeFilter = node;
    if (edge) this.edgeFilter = edge;
    this.applyVisibility();
  }

  setFocus(on, depth = this.focus.depth) {
    this.focus = { on, depth };
    this.applyVisibility();
    if (on && this.selected) this.fit();
  }

  neighbourhood(id, depth, visibleEdge = () => true) {
    const seen = new Set([id]);
    let frontier = [id];
    for (let d = 0; d < depth; d++) {
      const next = [];
      for (const nid of frontier) {
        for (const e of this.nodes.get(nid)?.edges || []) {
          if (!visibleEdge(e)) continue;
          const other = e.s.id === nid ? e.t.id : e.s.id;
          if (!seen.has(other)) { seen.add(other); next.push(other); }
        }
      }
      frontier = next;
    }
    return seen;
  }

  applyVisibility() {
    const baseNode = (n) => this.nodeFilter(n);
    const baseEdge = (e) => this.edgeFilter(e) && baseNode(e.s) && baseNode(e.t);
    let allowed = null;
    if (this.focus.on && this.selected) allowed = this.neighbourhood(this.selected, this.focus.depth, baseEdge);
    for (const n of this.nodes.values()) {
      n.visible = (baseNode(n) || n.id === this.selected) && (!allowed || allowed.has(n.id));
      n.el.classList.toggle("hidden", !n.visible);
    }
    for (const e of this.edges) {
      e.visible = this.edgeFilter(e) && e.s.visible && e.t.visible;
      e.el.classList.toggle("hidden", !e.visible);
      e.labelEl.classList.toggle("hidden", !e.visible);
    }
    this._highlight();
  }

  visibleNodeIds() {
    return [...this.nodes.values()].filter((n) => n.visible).map((n) => n.id);
  }

  // ------------------------------------------------------------------ selection
  select(id, { center = true, emit = true } = {}) {
    if (id !== null && !this.nodes.has(id)) id = null;
    this.selected = id;
    if (this.focus.on) this.applyVisibility(); else this._highlight();
    if (id && center) this.centerOn(id);
    if (id) this.nodes.get(id).el.focus({ preventScroll: true });
    if (emit) this.dispatchEvent(new CustomEvent("select", { detail: { id } }));
  }

  _highlight() {
    const sel = this.selected;
    this.svg.classList.toggle("has-selection", !!sel);
    for (const n of this.nodes.values()) n.el.classList.remove("selected", "hl");
    for (const e of this.edges) { e.el.classList.remove("hl"); e.labelEl.classList.remove("hl"); }
    if (!sel) return;
    const node = this.nodes.get(sel);
    node.el.classList.add("selected", "hl");
    for (const e of node.edges) {
      if (!e.visible) continue;
      e.el.classList.add("hl");
      e.labelEl.classList.add("hl");
      e.s.el.classList.add("hl");
      e.t.el.classList.add("hl");
    }
    node.el.parentNode.append(node.el); // draw on top
  }

  // ------------------------------------------------------------------ viewport
  _apply() {
    const { x, y, k } = this.t;
    this.viewport.setAttribute("transform", `translate(${x},${y}) scale(${k})`);
    this.svg.classList.toggle("show-all-labels", k >= this.labelZoom);
    this.svg.style.setProperty("--inv-zoom", String(1 / k));
    this.dispatchEvent(new CustomEvent("transform", { detail: { ...this.t } }));
  }

  get transform() { return { ...this.t }; }

  size() {
    const r = this.svg.getBoundingClientRect();
    return { w: r.width || 800, h: r.height || 600 };
  }

  zoomBy(factor, cx, cy) {
    const { w, h } = this.size();
    cx ??= w / 2; cy ??= h / 2;
    const k = Math.min(this.maxZoom, Math.max(this.minZoom, this.t.k * factor));
    const f = k / this.t.k;
    this.t = { x: cx - (cx - this.t.x) * f, y: cy - (cy - this.t.y) * f, k };
    this._apply();
  }

  panBy(dx, dy) {
    this.t = { ...this.t, x: this.t.x + dx, y: this.t.y + dy };
    this._apply();
  }

  centerOn(id) {
    const n = this.nodes.get(id);
    if (!n) return;
    const { w, h } = this.size();
    const k = Math.max(this.t.k, 0.8);
    this.t = { x: w / 2 - n.x * k, y: h / 2 - n.y * k, k };
    this._apply();
  }

  fit(padding = 40) {
    const vis = [...this.nodes.values()].filter((n) => n.visible);
    if (!vis.length) { this.t = { x: 0, y: 0, k: 1 }; return this._apply(); }
    const xs = vis.map((n) => n.x), ys = vis.map((n) => n.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const { w, h } = this.size();
    const k = Math.min(this.maxZoom, Math.max(this.minZoom,
      Math.min((w - 2 * padding) / Math.max(maxX - minX, 1), (h - 2 * padding) / Math.max(maxY - minY, 1), 1.5)));
    this.t = { x: w / 2 - ((minX + maxX) / 2) * k, y: h / 2 - ((minY + maxY) / 2) * k, k };
    this._apply();
  }

  screenPosition(id) { // position of a node in the SVG's own pixel coordinates
    const n = this.nodes.get(id);
    return n ? { x: n.x * this.t.k + this.t.x, y: n.y * this.t.k + this.t.y } : null;
  }

  // ------------------------------------------------------------------ geometry
  _placeNode(n) { n.el.setAttribute("transform", `translate(${n.x},${n.y})`); }

  _placeEdge(e) {
    const { s, t } = e;
    const dx = t.x - s.x, dy = t.y - s.y, d = Math.hypot(dx, dy) || 1;
    const pad = t.shape === "rect" ? 12 : 8;
    e.el.setAttribute("x1", s.x); e.el.setAttribute("y1", s.y);
    e.el.setAttribute("x2", t.x - (dx / d) * pad); e.el.setAttribute("y2", t.y - (dy / d) * pad);
    e.labelEl.setAttribute("x", (s.x + t.x) / 2);
    e.labelEl.setAttribute("y", (s.y + t.y) / 2 - 3);
  }

  // ------------------------------------------------------------------ input
  _bindEvents() {
    this.svg.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      const r = this.svg.getBoundingClientRect();
      this.zoomBy(Math.exp(-ev.deltaY * 0.0015), ev.clientX - r.left, ev.clientY - r.top);
    }, { passive: false });

    let drag = null;
    this.svg.addEventListener("pointerdown", (ev) => {
      if (ev.button !== 0) return;
      const g = ev.target.closest?.(".node");
      drag = { id: g?.dataset.id || null, x0: ev.clientX, y0: ev.clientY, x: ev.clientX, y: ev.clientY, moved: false };
      try { this.svg.setPointerCapture(ev.pointerId); } catch { /* synthetic events */ }
      this.svg.classList.add("dragging");
    });
    this.svg.addEventListener("pointermove", (ev) => {
      if (!drag) return;
      const dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
      drag.x = ev.clientX; drag.y = ev.clientY;
      if (Math.hypot(ev.clientX - drag.x0, ev.clientY - drag.y0) > 4) drag.moved = true;
      if (!drag.moved) return;
      if (drag.id) {
        const n = this.nodes.get(drag.id);
        n.x += dx / this.t.k; n.y += dy / this.t.k;
        this._placeNode(n);
        n.edges.forEach((e) => this._placeEdge(e));
      } else {
        this.panBy(dx, dy);
      }
    });
    const end = (ev) => {
      if (!drag) return;
      const { id, moved } = drag;
      drag = null;
      this.svg.classList.remove("dragging");
      try { this.svg.releasePointerCapture(ev.pointerId); } catch { /* synthetic events */ }
      if (!moved) this.select(id, { center: false });
    };
    this.svg.addEventListener("pointerup", end);
    this.svg.addEventListener("pointercancel", () => { drag = null; this.svg.classList.remove("dragging"); });
    this.svg.addEventListener("keydown", (ev) => {
      const step = 60;
      const actions = { "+": () => this.zoomBy(1.25), "=": () => this.zoomBy(1.25), "-": () => this.zoomBy(0.8),
                        ArrowLeft: () => this.panBy(step, 0), ArrowRight: () => this.panBy(-step, 0),
                        ArrowUp: () => this.panBy(0, step), ArrowDown: () => this.panBy(0, -step),
                        Escape: () => this.select(null) };
      if (actions[ev.key]) { ev.preventDefault(); actions[ev.key](); }
    });
    this.svg.setAttribute("tabindex", "0");
    new ResizeObserver(() => this._apply()).observe(this.container);
  }
}
