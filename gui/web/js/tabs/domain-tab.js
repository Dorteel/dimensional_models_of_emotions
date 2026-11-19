// "Domain Models" tab: Domain individuals of the populated ontology, their quality dimensions and the
// prototypes' coordinates. Composes the data API, the domain adapter and the generic TreeView,
// CoordinatePlot and Inspector components.

import { listOntologies, loadOntology } from "../api.js";
import { CoordinatePlot } from "../components/coordinate-plot.js";
import { Inspector } from "../components/inspector.js";
import { TreeView } from "../components/tree-view.js";
import { axisBounds, describeDimension, describeDomain, describePrototype, extractDomains, toDomainTree,
         toPlotData } from "../ontology/domains.js";

const TEMPLATE = `
  <div class="toolbar" role="toolbar" aria-label="Domain controls">
    <label>Domain <select data-role="domain"></select></label>
    <span data-role="axes" class="axis-pickers" hidden>
      <label>X <select data-axis="0"></select></label>
      <label>Y <select data-axis="1"></select></label>
      <label>Z <select data-axis="2"></select></label>
    </span>
    <label><input type="checkbox" data-role="labels" checked> Labels</label>
    <button type="button" data-role="reset-view" title="Reset the 3D view">Reset view</button>
    <button type="button" data-role="reload" title="Re-read the ontology from disk">Reload</button>
  </div>
  <div class="panes">
    <aside class="pane left" aria-label="Domains">
      <h3>Domains</h3>
      <div data-role="tree"></div>
    </aside>
    <section class="pane plot-pane" aria-label="Prototype coordinates">
      <header class="domain-summary" data-role="summary"></header>
      <div class="plot-host" data-role="plot"></div>
      <div class="omitted" data-role="omitted"></div>
      <div class="graph-message" data-role="message" hidden></div>
    </section>
    <aside class="pane right" data-role="inspector" aria-label="Inspector"></aside>
  </div>
  <footer class="status" data-role="status"></footer>`;

export class DomainTab {
  constructor(container, context = {}) {
    this.el = container;
    this.context = context;
    this.el.classList.add("domain-tab");
    this.el.innerHTML = TEMPLATE;
    const q = (role) => this.el.querySelector(`[data-role="${role}"]`);
    this.ui = { domain: q("domain"), axes: q("axes"), labels: q("labels"), summary: q("summary"),
                omitted: q("omitted"), status: q("status"), message: q("message"),
                axisSelects: [...this.el.querySelectorAll("select[data-axis]")] };
    this.tree = new TreeView(q("tree"));
    this.plot = new CoordinatePlot(q("plot"));
    this.inspector = new Inspector(q("inspector"));
    this.domains = [];
    this.domain = null;
    this._bind();
    this.ready = this._init();
  }

  _bind() {
    this.ui.domain.addEventListener("change", () => this.showDomain(this.ui.domain.value));
    this.ui.labels.addEventListener("change", () => this.plot.setLabels(this.ui.labels.checked));
    this.el.querySelector('[data-role="reset-view"]').addEventListener("click", () => this.plot.resetView());
    this.el.querySelector('[data-role="reload"]').addEventListener("click", () => this.load(this.domain?.id));
    this.ui.axisSelects.forEach((s) => s.addEventListener("change", () => this._plot()));
    this.plot.addEventListener("select", (ev) => this.select(ev.detail.id, "plot"));
    this.tree.addEventListener("select", (ev) => this.select(ev.detail.id, "tree"));
    this.inspector.addEventListener("navigate", (ev) => this.select(ev.detail.id, "inspector"));
  }

  async _init() {
    try {
      const params = new URLSearchParams(location.search);
      await this.load(null, params.get("domain"));
      const wanted = params.get("prototype");
      const hit = wanted && this.domain?.prototypes.find((p) => [p.id, p.name, p.label].includes(wanted));
      if (hit) this.select(hit.id, "url");
    } catch (err) {
      this._message(`Could not load domain models: ${err.message}`, true);
      throw err;
    }
  }

  async load(keepDomainId = null, wanted = null) {
    const list = await listOntologies();
    this.source = { file: list.domain_source, directory: list.directory_relative, fallback: list.fallback,
                    searched: list.searched };
    if (!list.files.some((f) => f.name === list.domain_source)) {
      this.domains = [];
      this.ui.domain.replaceChildren();
      this.tree.setData([]);
      this.plot.setData({ axes: [], points: [], emptyMessage: `${list.domain_source} not found in ${list.directory_relative}/` });
      this.inspector.clear(`The Domain Models tab reads only ${list.domain_source}, which was not found ` +
                           `(searched: ${(list.searched || []).join(", ") || list.directory_relative}).`);
      this._status(null);
      return;
    }
    this._message(`Reading ${list.directory_relative}/${list.domain_source}…`);
    this.model = await loadOntology(list.domain_source);
    this.domains = extractDomains(this.model);
    this.ui.domain.replaceChildren(...this.domains.map((d) =>
      new Option(`${d.label} — ${d.dimensions.length}D, ${d.prototypes.length} prototypes`, d.id)));
    this.tree.setData(toDomainTree(this.domains), { expandDepth: 0 });
    this._status(this.model);
    this._message("");
    const byWanted = wanted && this.domains.find((d) => [d.id, d.name, d.label].includes(wanted));
    const first = byWanted || this.domains.find((d) => d.id === keepDomainId) ||
      this.domains.find((d) => d.prototypes.length) || this.domains[0];
    if (first) this.showDomain(first.id);
    else {
      this.plot.setData({ axes: [], points: [], emptyMessage: "The ontology contains no Domain individuals." });
      this.inspector.clear("No Domain individuals were found in the ontology.");
    }
  }

  showDomain(id) {
    const d = this.domains.find((x) => x.id === id);
    if (!d) return;
    this.domain = d;
    this.ui.domain.value = id;
    // Axis pickers: only needed for more than three dimensions (projection onto a chosen subset).
    const many = d.dimensions.length > 3;
    this.ui.axes.hidden = !many;
    this.ui.axisSelects.forEach((s, i) => {
      const opts = d.dimensions.map((dim) => new Option(dim.label, dim.id));
      if (i === 2) opts.unshift(new Option("— none (2D)", ""));
      s.replaceChildren(...opts);
      s.value = i === 2 ? (d.dimensions[2]?.id ?? "") : d.dimensions[i]?.id ?? "";
    });
    this.el.querySelector('[data-role="reset-view"]').hidden = d.dimensions.length !== 3 && !many;
    this._summary(d);
    this._plot();
    this.tree.select(d.id, { emit: false });
    this.tree.reveal(`group:protos:${d.id}`);
    this.inspector.show(describeDomain(d));
    this.selected = d.id;
  }

  axisIds() {
    const d = this.domain;
    if (d.dimensions.length <= 3) return d.dimensions.map((x) => x.id);
    const ids = this.ui.axisSelects.map((s) => s.value).filter(Boolean);
    return [...new Set(ids)];
  }

  _plot() {
    const d = this.domain;
    const data = toPlotData(d, this.axisIds());
    let empty = "";
    if (!d.dimensions.length) empty = "This domain has no quality dimensions in the ontology.";
    else if (!d.prototypes.length) empty = `No prototypical instances are linked to ${d.label} in the ontology,\nso there are no coordinates to plot.`;
    else if (!data.points.length) empty = `None of the ${d.prototypes.length} prototypes of ${d.label} has a value on every plotted dimension.`;
    this.plot.setData({ ...data, emptyMessage: empty });
    this.ui.omitted.replaceChildren();
    if (data.omitted.length && data.points.length) {
      this.ui.omitted.append(`Not plotted (${data.omitted.length}): `,
        ...data.omitted.flatMap((o, i) => [i ? ", " : "", Object.assign(document.createElement("a"),
          { href: "#", textContent: o.label, title: o.reason, onclick: (ev) => { ev.preventDefault(); this.select(o.id, "omitted"); } })]));
    }
  }

  _summary(d) {
    const s = this.ui.summary;
    s.replaceChildren();
    const h = document.createElement("h2");
    h.textContent = d.label;
    const dims = document.createElement("div");
    dims.className = "dim-chips";
    for (const dim of d.dimensions) {
      const b = axisBounds(dim);
      const chip = Object.assign(document.createElement("button"), { type: "button", className: "chip",
        textContent: `${dim.label} ${b.stated ? `[${b.min}, ${b.max}]` : "· range not stated"}` });
      chip.addEventListener("click", () => this.select(dim.id, "chip"));
      dims.append(chip);
    }
    const plotted = toPlotData(d, d.dimensions.map((x) => x.id)).points.length;
    const meta = document.createElement("div");
    meta.className = "muted";
    const desc = d.description.flatMap((x) => x.texts.map((t) => t.value));
    meta.textContent = `${d.dimensions.length} dimension${d.dimensions.length === 1 ? "" : "s"} · ` +
      `${d.prototypes.length} prototypes · ${plotted} with complete coordinates · ` +
      `description: ${desc.length ? desc.join(" / ") : "not stated in the ontology"}`;
    s.append(h, dims, meta);
  }

  select(id, source) {
    if (!id || !this.domain) {
      if (source === "plot") { this.inspector.show(describeDomain(this.domain)); this.tree.select(this.domain.id, { emit: false }); }
      return;
    }
    if (id.startsWith("ontology:")) return this.context.openInOntology?.(this.source.file, id.slice(9));
    if (id.startsWith("group:")) return;
    const domain = this.domains.find((d) => d.id === id);
    if (domain) { if (domain !== this.domain) this.showDomain(id); else this.inspector.show(describeDomain(domain)); return; }
    const owner = this.domains.find((d) => d.prototypes.some((p) => p.id === id) || d.dimensions.some((x) => x.id === id));
    if (!owner) return this.context.openInOntology?.(this.source.file, id);
    if (owner !== this.domain) this.showDomain(owner.id);
    const proto = owner.prototypes.find((p) => p.id === id);
    if (proto) {
      if (source !== "plot") this.plot.select(id, { emit: false });
      this.inspector.show(describePrototype(owner, proto));
    } else {
      this.plot.select(null, { emit: false });
      this.inspector.show(describeDimension(owner, owner.dimensions.find((x) => x.id === id)));
    }
    if (source !== "tree") this.tree.select(id, { emit: false });
    this.selected = id;
  }

  _status(model) {
    const src = this.source;
    const where = `${src.directory}/${src.file}`;
    const note = src.fallback ? ` (ontology/ has no .owl files yet; using ${src.directory}/)` : "";
    this.ui.status.textContent = model
      ? `${where}${note} · sha256 ${model.meta.sha256.slice(0, 12)}… · ${this.domains.length} domains · ` +
        `${this.domains.reduce((n, d) => n + d.prototypes.length, 0)} prototypes · read ${new Date().toLocaleTimeString()}`
      : `${where} not available${note}`;
  }

  _message(text, error = false) {
    this.ui.message.textContent = text;
    this.ui.message.classList.toggle("error", error);
    this.ui.message.hidden = !text;
  }
}
