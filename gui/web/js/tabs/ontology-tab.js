// "Emotional Ontology" tab: composes the data API, the ontology adapter and the generic
// GraphView / TreeView / Inspector components. All selection syncing lives here.

import { listOntologies, loadOntology } from "../api.js";
import { GraphView } from "../components/graph-view.js";
import { Inspector } from "../components/inspector.js";
import { TreeView } from "../components/tree-view.js";
import { EDGE_KINDS, describe, relationPredicates, searchIndex, toGraphData, toPropertyItems,
         toTreeItems } from "../ontology/adapter.js";

const TEMPLATE = `
  <div class="toolbar" role="toolbar" aria-label="Ontology controls">
    <label>Ontology file <select data-role="file"></select></label>
    <button type="button" data-role="reload" title="Re-read the file from disk">Reload</button>
    <input type="search" data-role="search" list="ontology-search" placeholder="Search classes, individuals, properties…" aria-label="Search">
    <datalist id="ontology-search"></datalist>
    <details class="filters">
      <summary>Show</summary>
      <div class="filter-panel">
      <fieldset><legend>Nodes</legend>
        <label><input type="checkbox" data-node="class" checked> Classes</label>
        <label><input type="checkbox" data-node="individual" checked> Individuals</label>
        <label><input type="checkbox" data-node="resource" checked> Referenced, undeclared</label>
      </fieldset>
      <fieldset data-role="edge-kinds"><legend>Edges</legend></fieldset>
      <fieldset data-role="predicates"><legend>Relation properties</legend></fieldset>
      </div>
    </details>
    <label title="Show only the selected node and its neighbours"><input type="checkbox" data-role="focus"> Focus</label>
    <label>depth <select data-role="depth"><option>1</option><option>2</option><option>3</option></select></label>
    <span class="zoom">
      <button type="button" data-role="zoom-out" title="Zoom out" aria-label="Zoom out">−</button>
      <button type="button" data-role="zoom-in" title="Zoom in" aria-label="Zoom in">+</button>
      <button type="button" data-role="fit" title="Fit visible graph">Fit</button>
    </span>
  </div>
  <div class="panes">
    <aside class="pane left" aria-label="Hierarchy">
      <h3>Class hierarchy</h3>
      <div data-role="tree"></div>
      <h3>Properties</h3>
      <div data-role="props"></div>
    </aside>
    <section class="pane graph-pane" aria-label="Ontology graph">
      <div data-role="graph" class="graph-host"></div>
      <div class="legend">
        <span><i class="lg-class"></i>Class</span><span><i class="lg-individual"></i>Individual</span>
        <span><i class="lg-undeclared"></i>Undeclared</span>
        <span><b class="ln e-subclass"></b>subClassOf</span><span><b class="ln e-type"></b>rdf:type</span>
        <span><b class="ln e-relation"></b>relation</span><span><b class="ln e-domain_range"></b>domain→range</span>
      </div>
      <div class="graph-message" data-role="message"></div>
    </section>
    <aside class="pane right" data-role="inspector" aria-label="Inspector"></aside>
  </div>
  <footer class="status" data-role="status"></footer>`;

export class OntologyTab {
  constructor(container) {
    this.el = container;
    this.el.classList.add("ontology-tab");
    this.el.innerHTML = TEMPLATE;
    const q = (role) => this.el.querySelector(`[data-role="${role}"]`);
    this.ui = { file: q("file"), reload: q("reload"), search: q("search"), datalist: this.el.querySelector("datalist"),
                focus: q("focus"), depth: q("depth"), status: q("status"), message: q("message"),
                edgeKinds: q("edge-kinds"), predicates: q("predicates") };
    this.graph = new GraphView(q("graph"));
    this.tree = new TreeView(q("tree"));
    this.props = new TreeView(q("props"));
    this.inspector = new Inspector(q("inspector"));
    this.model = null;
    this._bind();
    this.ready = this._init();
  }

  _bind() {
    this.graph.addEventListener("select", (ev) => this.selectEntity(ev.detail.id, "graph"));
    this.tree.addEventListener("select", (ev) => this.selectEntity(ev.detail.id, "tree"));
    this.props.addEventListener("select", (ev) => this.selectEntity(ev.detail.id, "props"));
    this.inspector.addEventListener("navigate", (ev) => this.selectEntity(ev.detail.id, "inspector"));
    this.ui.file.addEventListener("change", () => this.load(this.ui.file.value));
    this.ui.reload.addEventListener("click", () => this.load(this.ui.file.value));
    this.ui.search.addEventListener("change", () => {
      const hit = this.index?.find((x) => x.text === this.ui.search.value) ||
        this.index?.find((x) => x.text.toLowerCase().includes(this.ui.search.value.trim().toLowerCase()));
      if (hit) this.selectEntity(hit.id, "search");
    });
    this.ui.focus.addEventListener("change", () => this.graph.setFocus(this.ui.focus.checked, +this.ui.depth.value));
    this.ui.depth.addEventListener("change", () => this.graph.setFocus(this.ui.focus.checked, +this.ui.depth.value));
    this.el.querySelector('[data-role="zoom-in"]').addEventListener("click", () => this.graph.zoomBy(1.25));
    this.el.querySelector('[data-role="zoom-out"]').addEventListener("click", () => this.graph.zoomBy(0.8));
    this.el.querySelector('[data-role="fit"]').addEventListener("click", () => this.graph.fit());
    this.el.querySelector(".filters").addEventListener("change", () => this._applyFilters());
  }

  async _init() {
    try {
      const list = await listOntologies();
      this.ui.file.replaceChildren(...list.files.map((f) => new Option(f.name, f.name, false, f.name === list.default)));
      if (!list.files.length) throw new Error(`No .owl files found in ${list.directory}`);
      // Optional deep links: ?file=<name in the ontology folder>&select=<local name, label or IRI>
      const params = new URLSearchParams(location.search);
      const file = list.files.some((f) => f.name === params.get("file")) ? params.get("file") : list.default;
      this.ui.file.value = file;
      await this.load(file);
      const wanted = params.get("select");
      if (wanted) {
        const hit = Object.values(this.model.entities).find((e) => [e.id, e.name, e.label].includes(wanted));
        if (hit) this.selectEntity(hit.id, "url");
      }
    } catch (err) {
      this._message(`Could not load the ontology: ${err.message}`, true);
      throw err;
    }
  }

  async load(file) {
    this._message(`Reading ${file} from disk…`);
    let model;
    try {
      model = await loadOntology(file);
    } catch (err) {
      this._message(`Could not load ${file}: ${err.message}`, true);
      throw err;
    }
    this.model = model;
    this._message(`Laying out ${Object.keys(model.entities).length} terms…`);
    await new Promise((r) => setTimeout(r, 30)); // let the message paint before the synchronous layout
    this.graph.setData(toGraphData(model));
    this.tree.setData(toTreeItems(model), { expandDepth: 1 });
    this.props.setData(toPropertyItems(model), { expandDepth: 0 });
    this.index = searchIndex(model);
    this.ui.datalist.replaceChildren(...this.index.map((x) => new Option(x.text)));
    this._buildFilters(model);
    this._applyFilters();
    this.inspector.clear();
    this._status(model);
    this._message("");
    return model;
  }

  _buildFilters(model) {
    const box = (attr, value, label, checked = true) => {
      const l = document.createElement("label");
      const i = Object.assign(document.createElement("input"), { type: "checkbox", checked });
      i.dataset[attr] = value;
      l.append(i, ` ${label}`);
      return l;
    };
    this.ui.edgeKinds.replaceChildren(this.ui.edgeKinds.querySelector("legend"),
      ...Object.entries(EDGE_KINDS).map(([k, v]) => box("edge", k, `${v.label} (${model.stats[`edges_${k}`] || 0})`)));
    this.ui.predicates.replaceChildren(this.ui.predicates.querySelector("legend"),
      ...relationPredicates(model).map(([p, n]) => box("predicate", p, `${p} (${n})`)));
  }

  _applyFilters() {
    const on = (sel) => new Set([...this.el.querySelectorAll(sel)].filter((i) => i.checked)
      .map((i) => i.dataset.node ?? i.dataset.edge ?? i.dataset.predicate));
    const nodes = on("input[data-node]"), edges = on("input[data-edge]"), preds = on("input[data-predicate]");
    this.graph.setFilters({
      node: (n) => nodes.has(n.kind),
      edge: (e) => edges.has(e.kind) && (e.kind !== "relation" || preds.has(e.label)),
    });
  }

  // Show a term from another tab: load the given file if another one is displayed, then select the term.
  async reveal(file, id) {
    await this.ready;
    if (file && this.model?.meta.file !== file) {
      this.ui.file.value = file;
      await this.load(file);
    }
    this.selectEntity(id, "external");
  }

  selectEntity(id, source) {
    if (!this.model) return;
    if (id && id.startsWith("group:")) return;
    if (source !== "graph") this.graph.select(id && this.graph.nodes.has(id) ? id : null, { emit: false });
    if (source !== "tree") this.tree.select(id, { emit: false });
    if (source !== "props") this.props.select(id && this.model.entities[id]?.kind === "property" ? id : null, { emit: false });
    if (!id) return this.inspector.clear();
    const desc = describe(this.model, id);
    if (desc) this.inspector.show(desc);
    this.selected = id;
  }

  _status(model) {
    const s = model.stats;
    const warn = model.warnings.length;
    this.ui.status.replaceChildren();
    const parts = [
      `${model.meta.file}`, `sha256 ${model.meta.sha256.slice(0, 12)}…`,
      `${s.class || 0} classes`, `${s.individual || 0} individuals`, `${s.property || 0} properties`,
      `${(s.edges_relation || 0)} relation assertions`, `${s.triples} triples`,
      `read ${new Date().toLocaleTimeString()}`,
    ];
    this.ui.status.append(parts.join(" · "));
    if (warn) {
      const a = Object.assign(document.createElement("a"), { href: "#", textContent: ` · ${warn} unsupported construct(s)` });
      a.addEventListener("click", (ev) => {
        ev.preventDefault();
        this.inspector.show({ title: "Reader warnings", sections: [{ title: "Not read",
          rows: model.warnings.map((w) => ({ key: `line ${w.line}`, value: w.message })) }] });
      });
      this.ui.status.append(a);
    }
  }

  _message(text, error = false) {
    this.ui.message.textContent = text;
    this.ui.message.classList.toggle("error", error);
    this.ui.message.hidden = !text;
  }
}
