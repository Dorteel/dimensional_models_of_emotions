// "Compare Domain Models" tab: two domains of the populated ontology side by side, with a summary of what they
// share. Data: GET /api/domains (the domain list) and GET /api/compare (both domains as in /api/domains, plus
// the comparison computed by the server from the SPARQL results). Nothing is read from YAML/ODS files.
// Composes the existing CoordinatePlot (one per domain) with the generic AxisPicker and plot-export helpers.

import { listOntologies, loadComparison, loadComparisonExport, loadDomains } from "../api.js";
import { AxisPicker } from "../components/axis-picker.js";
import { CoordinatePlot } from "../components/coordinate-plot.js";
import { download, standaloneSvg, svgToPng } from "../components/plot-export.js";
import { counterparts, exportName, figureText, other, rowKeys, selectionNote, SIDES } from "../ontology/compare.js";
import { toPlotData } from "../ontology/domains.js";

const FIGURES_MARKER = "<!-- figures -->";   // in the server's HTML summary (compare_report.FIGURES_MARKER)

const side = (s) => `
  <section class="compare-side" data-side="${s}" aria-label="Domain ${s.toUpperCase()}">
    <header class="compare-head">
      <div class="compare-title"><span class="side-badge">${s.toUpperCase()}</span><h2 data-role="title"></h2></div>
      <div class="muted iri" data-role="iri"></div>
      <div class="dim-chips" data-role="chips"></div>
    </header>
    <div class="compare-controls"><span data-role="axes"></span>
      <button type="button" data-role="reset-view" title="Reset the 3D view">Reset view</button></div>
    <div class="plot-host" data-role="plot"></div>
    <div class="omitted" data-role="omitted"></div>
  </section>`;

const TEMPLATE = `
  <div class="toolbar" role="toolbar" aria-label="Comparison controls">
    <label>A <select data-role="domain-a"></select></label>
    <button type="button" data-role="swap" title="Swap A and B">⇄</button>
    <label>B <select data-role="domain-b"></select></label>
    <label><input type="checkbox" data-role="labels" checked> Labels</label>
    <button type="button" data-role="reload" title="Re-read the ontology from disk">Reload</button>
    <span class="export-group" role="group" aria-label="Export">Export:
      <button type="button" data-export="svg-a">A SVG</button><button type="button" data-export="png-a">A PNG</button>
      <button type="button" data-export="svg-b">B SVG</button><button type="button" data-export="png-b">B PNG</button>
      <button type="button" data-export="csv">CSV table</button>
      <button type="button" data-export="html">HTML summary</button>
      <button type="button" data-export="md">Markdown</button>
    </span>
  </div>
  <div class="compare-body">
    <div class="compare-plots">${side("a")}${side("b")}</div>
    <div class="selection-note" data-role="selection" aria-live="polite"></div>
    <div class="graph-message" data-role="message" hidden></div>
    <div class="compare-summary" data-role="summary"></div>
  </div>
  <footer class="status" data-role="status"></footer>`;

function h(tag, { dataset = {}, ...props } = {}, ...children) {
  const n = Object.assign(document.createElement(tag), props);
  Object.assign(n.dataset, dataset);
  n.append(...children.flat().filter((c) => c !== null && c !== undefined && c !== false));
  return n;
}

export class CompareTab {
  constructor(container, context = {}) {
    this.el = container;
    this.context = context;
    this.el.classList.add("compare-tab");
    this.el.innerHTML = TEMPLATE;
    const q = (sel) => this.el.querySelector(sel);
    this.ui = { a: q('[data-role="domain-a"]'), b: q('[data-role="domain-b"]'), labels: q('[data-role="labels"]'),
                summary: q('[data-role="summary"]'), selection: q('[data-role="selection"]'),
                message: q('[data-role="message"]'), status: q('[data-role="status"]') };
    this.sides = {};
    this.plots = {};
    this.pickers = {};
    for (const s of SIDES) {
      const root = q(`.compare-side[data-side="${s}"]`);
      const r = (role) => root.querySelector(`[data-role="${role}"]`);
      this.sides[s] = { root, title: r("title"), iri: r("iri"), chips: r("chips"), omitted: r("omitted"), reset: r("reset-view") };
      this.plots[s] = new CoordinatePlot(r("plot"));
      this.pickers[s] = new AxisPicker(r("axes"));
    }
    this.domains = [];
    this.data = null;          // GET /api/compare response
    this.plotData = {};
    this.selection = null;     // {side, id}
    this.download = download;  // replaced by the self-test to capture files
    this._bind();
    this.ready = this._init();
  }

  get comparison() { return this.data?.comparison; }

  _bind() {
    this.ui.a.addEventListener("change", () => this.compare());
    this.ui.b.addEventListener("change", () => this.compare());
    this.el.querySelector('[data-role="swap"]').addEventListener("click", () => {
      [this.ui.a.value, this.ui.b.value] = [this.ui.b.value, this.ui.a.value];
      this.compare();
    });
    this.ui.labels.addEventListener("change", () => SIDES.forEach((s) => this.plots[s].setLabels(this.ui.labels.checked)));
    this.el.querySelector('[data-role="reload"]').addEventListener("click", () => this.load());
    for (const s of SIDES) {
      this.pickers[s].addEventListener("change", () => this._plot(s));
      this.sides[s].reset.addEventListener("click", () => this.plots[s].resetView());
      this.plots[s].addEventListener("select", (ev) => this.select(s, ev.detail.id));
    }
    for (const b of this.el.querySelectorAll("[data-export]")) {
      b.addEventListener("click", async () => {
        try { this.download(await this.exportFile(b.dataset.export)); } catch (err) { this._message(`Export failed: ${err.message}`, true); }
      });
    }
  }

  async _init() {
    try {
      const params = new URLSearchParams(location.search);
      await this.load(params.get("compareA"), params.get("compareB"));
    } catch (err) {
      this._message(`Could not load domain models: ${err.message}`, true);
      throw err;
    }
  }

  async load(wantedA = null, wantedB = null) {
    const list = await listOntologies();
    this.source = { file: list.domain_source, directory: list.directory_relative };
    if (!list.files.some((f) => f.name === list.domain_source)) {
      this.domains = [];
      this.data = null;
      this.ui.summary.replaceChildren();
      this._message(`${list.domain_source} not found in ${list.directory_relative}/: nothing to compare.`, true);
      return;
    }
    const keep = [this.ui.a.value, this.ui.b.value];
    this.domains = (await loadDomains()).domains;
    const find = (w) => w && this.domains.find((d) => [d.id, d.name, d.label].includes(w));
    const opts = () => this.domains.map((d) => new Option(`${d.label} — ${d.dimensions.length}D, ${d.prototypes.length} prototypes`, d.id));
    this.ui.a.replaceChildren(...opts());
    this.ui.b.replaceChildren(...opts());
    const withProtos = this.domains.filter((d) => d.prototypes.length);
    const a = find(wantedA) || find(keep[0]) || withProtos[0] || this.domains[0];
    const b = find(wantedB) || find(keep[1]) || withProtos.find((d) => d !== a) || this.domains.find((d) => d !== a) || a;
    if (!a) {
      this._message("The ontology contains no Domain individuals.", true);
      return;
    }
    this.ui.a.value = a.id;
    this.ui.b.value = b.id;
    await this.compare();
  }

  async compare(a = this.ui.a.value, b = this.ui.b.value) {
    this.ui.a.value = a;
    this.ui.b.value = b;
    const token = (this._token = (this._token || 0) + 1);
    this._message("Comparing…");
    const data = await loadComparison(a, b);
    if (token !== this._token) return this.data;
    this.data = data;
    this.selection = null;
    this._message("");
    this._summary();
    for (const s of SIDES) {
      const d = data.domains[s];
      this.pickers[s].setOptions(d.dimensions.map((x) => ({ id: x.id, label: x.label })));
      this.sides[s].reset.hidden = d.dimensions.length < 3;
      this._header(s);
      this._plot(s);
    }
    this.select(null, null);
    this._status();
    return data;
  }

  setAxes(s, ids) {
    this.pickers[s].set(ids);
    this._plot(s);
  }

  _plot(s) {
    const d = this.data.domains[s];
    const data = toPlotData(d, this.pickers[s].value);
    let empty = "";
    if (!d.dimensions.length) empty = `${d.label} has no quality dimensions in the ontology.`;
    else if (!d.prototypes.length) empty = `No prototypical instances are linked to ${d.label}\nin the ontology: nothing to plot.`;
    else if (!data.points.length) empty = `None of the ${d.prototypes.length} prototypes of ${d.label} has a value on every plotted dimension.`;
    this.plotData[s] = data;
    this.plots[s].setData({ ...data, emptyMessage: empty });
    const om = this.sides[s].omitted;
    om.textContent = data.omitted.length && data.points.length
      ? `Not plotted (${data.omitted.length}): ${data.omitted.map((o) => `${o.label} (${o.reason})`).join(", ")}` : "";
    if (this.selection) this.select(this.selection.side, this.selection.id);
  }

  _header(s) {
    const sum = this.comparison[s];
    const ui = this.sides[s];
    ui.title.textContent = sum.label;
    ui.iri.textContent = sum.id;
    ui.chips.replaceChildren(...sum.dimensions.map((d) => {
      const defs = d.definitions.map((t) => `${t.text}${t.placeholder ? " (placeholder)" : ""}` +
                                            (t.sources.length ? ` — ${t.sources.join(", ")}` : "")).join("\n");
      const missing = !d.rangeStated || d.definitionState !== "stated";
      return h("span", { className: `chip${missing ? " incomplete" : ""}`, title:
        `${d.label} (${d.id})\nrange: ${d.rangeStated ? d.range : d.rangeState}\ndefinition: ${defs || "not stated"}`,
        textContent: `${d.label} ${d.rangeStated ? `[${d.min}, ${d.max}]` : "· range not stated"}` +
                     (d.definitionState === "stated" ? "" : " · definition " + (d.definitionState === "missing" ? "missing" : "placeholder")) });
    }));
  }

  // Select prototype `id` in plot `s` and highlight the prototypes of the same emotion class in the other plot.
  select(s, id) {
    const c = this.comparison;
    if (!c) return;
    if (!s || !id) {
      this.selection = null;
      for (const x of SIDES) { this.plots[x].select(null, { emit: false }); this.plots[x].highlight([]); }
      this.ui.selection.textContent = c.emotions.shared.length
        ? "Select an emotion in either plot (or a table row) to highlight the prototype of the same emotion class in the other."
        : "No emotion class occurs in both domains: there are no counterparts to highlight.";
      this._markRows(new Set());
      return;
    }
    const o = other(s);
    const ids = counterparts(c, s, id);
    this.selection = { side: s, id, counterparts: ids };
    this.plots[s].highlight([]);
    this.plots[s].select(id, { emit: false });
    this.plots[o].select(null, { emit: false });
    this.plots[o].highlight(ids);
    this.ui.selection.textContent = selectionNote(c, s, id);
    this._markRows(new Set([`${s}:${id}`]));
  }

  _markRows(keys) {
    for (const tr of this.ui.summary.querySelectorAll("tr[data-row]")) {
      const row = this.comparison.rows[Number(tr.dataset.row)];
      tr.classList.toggle("selected", rowKeys(row).some((k) => keys.has(k)));
    }
  }

  // ---------------------------------------------------------------- summary panel
  _summary() {
    const c = this.comparison;
    const { a, b, dimensions: dims, emotions: emo } = c;
    const table = (header, rows, attrs = () => ({})) => h("table", { className: "compare-table" },
      h("thead", {}, h("tr", {}, header.map((x) => h("th", { textContent: x })))),
      h("tbody", {}, rows.map((r, i) => {
        const tr = h("tr", {}, r.map((x) => h("td", { textContent: x })));
        Object.entries(attrs(i)).forEach(([k, v]) => tr.setAttribute(k, v));
        return tr;
      })));
    const section = (title, ...content) => h("section", { className: "compare-section" }, h("h3", { textContent: title }), ...content);
    const dimList = (s) => s.dimensions.map((d) => `${d.label} ${d.rangeStated ? `[${d.min}, ${d.max}]` : "(range not stated)"}`).join(", ") || "none";
    const emotionLink = (e) => {
      const ids = [...(e.a || []), ...(e.b || [])];
      return h("a", { href: "#", textContent: e.label, title: e.id, onclick: (ev) => {
        ev.preventDefault();
        if (e.a?.length) this.select("a", e.a[0]); else if (e.b?.length) this.select("b", e.b[0]);
        else if (ids[0]) this.select("a", ids[0]);
      } });
    };
    const list = (items) => items.length ? items.flatMap((e, i) => [i ? ", " : "", emotionLink(e)]) : ["none"];
    const corr = { none: "None established in the ontology (no shared dimension and no sameAs statement). Structural comparison only: " +
                         "no numerical differences or distances are computed.",
                   partial: "Partial: some dimensions have a stated counterpart; no distance is computed.",
                   full: "Full: every dimension has exactly one stated counterpart." }[dims.equivalence];
    const onlyA = emo.onlyA.map((e) => ({ ...e, a: c.rows.filter((r) => r.class?.id === e.id && r.a).map((r) => r.a.id) }));
    const onlyB = emo.onlyB.map((e) => ({ ...e, b: c.rows.filter((r) => r.class?.id === e.id && r.b).map((r) => r.b.id) }));
    const content = [
      section("Overview", table(["", `A: ${a.label}`, `B: ${b.label}`], [
        ["IRI", a.id, b.id],
        ["dimensions", `${a.dimensions.length}: ${dimList(a)}`, `${b.dimensions.length}: ${dimList(b)}`],
        ["prototypes", String(a.prototypes), String(b.prototypes)],
        ["with complete coordinates", String(a.plotted), String(b.plotted)],
        ["emotion classes", String(a.emotionClasses), String(b.emotionClasses)],
        ["without emotion class", String(a.unclassified), String(b.unclassified)],
      ])),
      section("Dimension correspondence", h("p", { textContent: corr, dataset: { role: "equivalence" } }),
              dims.pairs.length ? table(["A dimension", "B dimension", "basis", "differences", "why not"],
                dims.pairs.map((p) => [p.aLabel, p.bLabel, p.basis, p.compatible ? "computed (B − A)" : "not computed",
                                       p.reasons.join("; ")])) : null),
      section(`Emotions: ${emo.shared.length} shared, ${emo.onlyA.length} only in A, ${emo.onlyB.length} only in B`,
              h("p", { className: "muted", textContent: "Matched by emotion class IRI only (not by name)." }),
              h("p", { dataset: { role: "shared" } }, h("b", { textContent: "Shared: " }), ...list(emo.shared)),
              h("p", {}, h("b", { textContent: "Only in A: " }), ...list(onlyA)),
              h("p", {}, h("b", { textContent: "Only in B: " }), ...list(onlyB))),
      section("Comparison table", c.table.rows.length
        ? h("div", { className: "table-scroll" }, table(c.table.header, c.table.rows, (i) => ({ "data-row": String(i) })))
        : h("p", { className: "muted", textContent: "Neither domain has prototypes." })),
      section(`Missing information and warnings (${c.warnings.length})`,
              h("ul", { className: "warnings" }, c.warnings.map((w) => h("li", { textContent: `[${w.scope}] ${w.text}` })))),
      section("Provenance", h("ul", {}, [
        `${c.provenance.file} · sha256 ${c.provenance.sha256} · ${c.provenance.parser}`,
        `SPARQL queries: ${c.provenance.queries.join(", ")}`, ...c.provenance.rules,
      ].map((t) => h("li", { textContent: t })))),
    ];
    this.ui.summary.replaceChildren(...content);
    for (const tr of this.ui.summary.querySelectorAll("tr[data-row]")) {
      tr.addEventListener("click", () => {
        const row = c.rows[Number(tr.dataset.row)];
        if (row.a) this.select("a", row.a.id); else if (row.b) this.select("b", row.b.id);
      });
    }
  }

  // ---------------------------------------------------------------- exports
  figureSvg(s) {
    const { title, footer } = figureText(this.comparison, s, this.plotData[s]);
    return standaloneSvg(this.plots[s].svg, { title, footer, omit: [".plot-hint"] });
  }

  async exportFile(kind) {
    const c = this.comparison;
    if (!c) throw new Error("nothing to export");
    const [what, s] = kind.split("-");
    if (what === "svg" || what === "png") {
      const name = exportName(c, `${s.toUpperCase()}_${c[s].name}`);
      const svg = this.figureSvg(s);
      return what === "svg" ? { filename: `${name}.svg`, type: "image/svg+xml", data: svg }
                            : { filename: `${name}.png`, type: "image/png", data: await svgToPng(svg) };
    }
    const text = await loadComparisonExport(c.a.id, c.b.id, kind);
    if (kind === "csv") return { filename: `${exportName(c, "table")}.csv`, type: "text/csv", data: text };
    if (kind === "md") return { filename: `${exportName(c, "summary")}.md`, type: "text/markdown", data: text };
    const figures = SIDES.map((x) => `<figure><figcaption>${x.toUpperCase()}: ${escapeHtml(c[x].label)}</figcaption>` +
      this.figureSvg(x).replace(/^<\?xml[^>]*\?>\s*/, "") + "</figure>").join("\n");
    return { filename: `${exportName(c, "summary")}.html`, type: "text/html", data: text.replace(FIGURES_MARKER, figures) };
  }

  _status() {
    const m = this.data.meta;
    this.ui.status.textContent = `${this.source.directory}/${m.file} · sha256 ${m.sha256.slice(0, 12)}… · ${m.parser} + SPARQL ` +
      `(${m.queries.length} queries) · read ${new Date().toLocaleTimeString()}`;
  }

  _message(text, error = false) {
    this.ui.message.textContent = text;
    this.ui.message.classList.toggle("error", error);
    this.ui.message.hidden = !text;
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[ch]);
}
