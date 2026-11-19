// "Create Domain Model" tab: the builder workbook's three-step workflow in the browser.
//   Step 1 Domain model (name, description, notes) · Step 2 Quality dimensions · Step 3 Prototypical emotions
// The server validates with the builder macros' rules and saves domains/<id>/<id>.yaml + .ods using the
// workbook's own BuildDomainYAML / CopyDomainModelValues. Saving never changes the ontology.

import { loadCatalogue, saveModel, validateModel } from "../api.js";
import { CoordinatePlot } from "../components/coordinate-plot.js";
import { MAX_DIMENSIONS, MAX_EMOTIONS, addDimension, addEmotion, definitionNote, emptyModel, moveDimension,
         previewPlotData, removeDimension, removeEmotion } from "../models/domain-form.js";

const DRAFT_KEY = "ecs.createDomainModel.draft";

const TEMPLATE = `
  <div class="toolbar" role="toolbar" aria-label="Create domain model">
    <button type="button" data-role="validate">Validate</button>
    <button type="button" data-role="save" class="primary">Save domain model</button>
    <button type="button" data-role="clear" title="Start a new, empty model">Clear form</button>
    <span class="muted" data-role="state"></span>
  </div>
  <div class="panes create-panes">
    <section class="pane form-pane" aria-label="Domain model form">
      <section class="step" data-step="1">
        <h2><span class="step-no">1</span> Domain model</h2>
        <label class="field">Model name <input data-field="name" data-bind="name" autocomplete="off"></label>
        <div class="hint" data-role="model-id"></div>
        <label class="field">Description <textarea data-field="description" data-bind="description" rows="2"></textarea></label>
        <label class="field">Notes <span class="muted">(optional: references, DOI, source)</span>
          <textarea data-field="notes" data-bind="notes" rows="2"></textarea></label>
      </section>
      <section class="step" data-step="2">
        <h2><span class="step-no">2</span> Quality dimensions</h2>
        <div data-role="dimensions" data-field="dimensions"></div>
        <button type="button" data-role="add-dimension">+ Add dimension</button>
      </section>
      <section class="step" data-step="3">
        <h2><span class="step-no">3</span> Prototypical emotions <span class="muted">(optional)</span></h2>
        <div class="add-emotion">
          <input type="search" data-role="catalogue-input" list="create-catalogue" placeholder="Emotion from the catalogue…"
                 aria-label="Emotion from the catalogue">
          <datalist id="create-catalogue"></datalist>
          <button type="button" data-role="add-catalogue">+ Add from catalogue</button>
          <button type="button" data-role="add-new">+ New emotion</button>
        </div>
        <div data-role="emotions" data-field="emotions"></div>
      </section>
    </section>
    <aside class="pane right create-side" aria-label="Validation and preview">
      <h3>Destination</h3>
      <div data-role="destination" class="mono small"></div>
      <h3>Validation</h3>
      <ul data-role="messages" class="messages"></ul>
      <h3>Preview</h3>
      <div class="preview-host" data-role="preview"></div>
      <div class="hint" data-role="preview-note"></div>
      <div data-role="result"></div>
    </aside>
  </div>
  <footer class="status" data-role="status"></footer>`;

const el = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "dataset") Object.assign(node.dataset, v);
    else if (k === "value") node.value = v ?? "";              // property: also fills <textarea>
    else if (k in node && typeof v !== "string") node[k] = v;
    else node.setAttribute(k, v);
  }
  node.append(...children);
  return node;
};

export class CreateTab {
  constructor(container, context = {}) {
    this.el = container;
    this.context = context;
    this.el.classList.add("create-tab");
    this.el.innerHTML = TEMPLATE;
    const q = (role) => this.el.querySelector(`[data-role="${role}"]`);
    this.ui = { dims: q("dimensions"), emotions: q("emotions"), messages: q("messages"), destination: q("destination"),
                modelId: q("model-id"), state: q("state"), status: q("status"), result: q("result"),
                catalogueInput: q("catalogue-input"), datalist: this.el.querySelector("datalist"),
                previewNote: q("preview-note"), save: q("save") };
    this.preview = new CoordinatePlot(q("preview"));
    this.state = this._loadDraft() || emptyModel();
    this.catalogue = [];
    this.lastCheck = null;
    this._timer = null;
    this._bind();
    this.render();
    this.ready = this._init();
  }

  async _init() {
    try {
      const data = await loadCatalogue();
      this.catalogue = data.emotions;
      this.byName = new Map(this.catalogue.map((e) => [e.name.toLowerCase(), e]));
      this.byConcept = new Map(this.catalogue.map((e) => [e.concept_id, e]));
      this.ui.datalist.replaceChildren(...this.catalogue.map((e) => new Option(e.name)));
      this.ui.status.textContent = `Catalogue: ${data.sources.catalogue.path} (${this.catalogue.length} emotions) · ` +
        `definitions: ${data.sources.dictionary?.path ?? "none"} · saving writes domains/<model_id>/ only; the ontology is not changed`;
      this.renderEmotions();
    } catch (err) {
      this.ui.status.textContent = `Could not load the emotion catalogue: ${err.message}`;
    }
    await this.validate();
  }

  // ---------------------------------------------------------------- events
  _bind() {
    this.el.addEventListener("input", (ev) => this._onInput(ev));
    this.el.addEventListener("change", (ev) => this._onInput(ev));
    this.el.addEventListener("click", (ev) => this._onClick(ev));
    this.ui.messages.addEventListener("click", (ev) => {
      const field = ev.target.closest("[data-target]")?.dataset.target;
      if (field) this.focusField(field);
    });
  }

  _onInput(ev) {
    const t = ev.target;
    if (!t.dataset.bind) return;
    const path = t.dataset.bind.split(".");
    let obj = this.state;
    for (const key of path.slice(0, -1)) obj = obj[key];
    obj[path[path.length - 1]] = t.type === "checkbox" ? t.checked : t.value;
    if (t.dataset.bind === "name" || /^dimensions\.\d+\.name$/.test(t.dataset.bind)) this._refreshLabels();
    this._changed();
  }

  _onClick(ev) {
    const b = ev.target.closest("button[data-action], button[data-role]");
    if (!b) return;
    const i = Number(b.dataset.index);
    const actions = {
      "add-dimension": () => this.update(addDimension(this.state)),
      "remove-dimension": () => this.update(removeDimension(this.state, i)),
      "dimension-up": () => this.update(moveDimension(this.state, i, -1)),
      "dimension-down": () => this.update(moveDimension(this.state, i, 1)),
      "add-catalogue": () => this.addFromCatalogue(this.ui.catalogueInput.value),
      "add-new": () => this.update(addEmotion(this.state)),
      "remove-emotion": () => this.update(removeEmotion(this.state, i)),
      validate: () => this.validate(),
      save: () => this.save(),
      clear: () => { if (confirm("Clear the form and start a new model?")) { this.ui.result.replaceChildren(); this.update(emptyModel()); } },
    };
    const action = actions[b.dataset.action || b.dataset.role];
    if (action) action();
  }

  addFromCatalogue(text) {
    const entry = this.byName?.get(String(text).trim().toLowerCase());
    if (!entry) {
      this._flash(`'${text}' is not in the catalogue. Use "New emotion" to define a new one.`);
      return false;
    }
    if (this.state.emotions.some((e) => e.concept_id === entry.concept_id)) {
      this._flash(`${entry.name} is already in this model.`);
      return false;
    }
    this.ui.catalogueInput.value = "";
    this.update(addEmotion(this.state, entry));
    return true;
  }

  update(state) {
    this.state = state;
    this.render();
    this._changed();
  }

  _changed() {
    this._saveDraft();
    this._preview();
    clearTimeout(this._timer);
    this._timer = setTimeout(() => this.validate(), 350);
  }

  // ---------------------------------------------------------------- rendering
  render() {
    for (const input of this.el.querySelectorAll('.step[data-step="1"] [data-bind]')) input.value = this.state[input.dataset.bind];
    this.renderDimensions();
    this.renderEmotions();
    this._refreshLabels();
    this._preview();
  }

  renderDimensions() {
    const s = this.state;
    this.ui.dims.replaceChildren(...s.dimensions.map((d, i) => {
      const card = el("div", { class: "entry dimension", dataset: { index: String(i) } });
      const head = el("div", { class: "entry-head" },
        el("strong", {}, `Dimension ${i + 1}`), el("span", { class: "muted id", dataset: { role: `dim-id-${i}` } }),
        el("span", { class: "spacer" }),
        el("button", { type: "button", dataset: { action: "dimension-up", index: String(i) }, title: "Move up", disabled: i === 0 }, "↑"),
        el("button", { type: "button", dataset: { action: "dimension-down", index: String(i) }, title: "Move down",
                       disabled: i === s.dimensions.length - 1 }, "↓"),
        el("button", { type: "button", dataset: { action: "remove-dimension", index: String(i) }, class: "danger" }, "Remove"));
      const f = (key, label, input) => el("label", { class: `field ${key}` }, label, input);
      const bind = (key) => ({ dataset: { bind: `dimensions.${i}.${key}`, field: `dimensions.${i}.${key}` }, value: d[key] });
      const circular = el("select", bind("circular"), new Option("No", "no"), new Option("Yes", "yes"));
      circular.value = d.circular;
      card.append(head,
        el("div", { class: "row" },
          f("name", "Name", el("input", { ...bind("name"), autocomplete: "off" })),
          f("min", "Minimum", el("input", { ...bind("min"), inputmode: "decimal" })),
          f("max", "Maximum", el("input", { ...bind("max"), inputmode: "decimal" })),
          f("circular", "Circular?", circular)),
        f("definition", "Definition / description", el("textarea", { ...bind("definition"), rows: 2 })),
        f("notes", "Notes (optional: source, assumptions)", el("textarea", { ...bind("notes"), rows: 1 })));
      return card;
    }));
    this.el.querySelector('[data-role="add-dimension"]').disabled = s.dimensions.length >= MAX_DIMENSIONS;
  }

  renderEmotions() {
    const s = this.state;
    if (!s.emotions.length) {
      this.ui.emotions.replaceChildren(el("p", { class: "muted" }, "No prototypes yet. Prototypes are optional; " +
        "each one needs a definition and a coordinate on every dimension."));
    } else {
      this.ui.emotions.replaceChildren(...s.emotions.map((e, j) => this._emotionCard(e, j)));
    }
    const full = s.emotions.length >= MAX_EMOTIONS;
    for (const role of ["add-catalogue", "add-new"]) this.el.querySelector(`[data-role="${role}"]`).disabled = full;
  }

  _emotionCard(e, j) {
    const s = this.state;
    const entry = e.concept_id ? this.byConcept?.get(e.concept_id) : null;
    const bind = (key) => ({ dataset: { bind: `emotions.${j}.${key}`, field: `emotions.${j}.${key}` }, value: e[key] });
    const card = el("div", { class: "entry emotion", dataset: { index: String(j) } });
    card.append(el("div", { class: "entry-head" },
      el("strong", {}, `Emotion ${j + 1}`),
      el("span", { class: "badge" }, e.concept_id ? `catalogue · ${e.concept_id}` : "new emotion"),
      el("span", { class: "spacer" }),
      el("button", { type: "button", dataset: { action: "remove-emotion", index: String(j) }, class: "danger" }, "Remove")));
    const name = el("input", { ...bind("name"), autocomplete: "off" });
    if (e.concept_id) name.readOnly = true;       // the catalogue fixes name and ID
    card.append(el("label", { class: "field" }, "Name", name));
    const defs = entry?.definitions ?? [];
    if (defs.length) {
      const pick = el("select", { dataset: { role: "dictionary-definition", index: String(j) }, "aria-label": "Dictionary definition" },
        new Option(`Use a definition from the emotion dictionary (${defs.length})…`, ""),
        ...defs.map((d, k) => new Option(`${d.source}: ${d.text.length > 90 ? `${d.text.slice(0, 90)}…` : d.text}`, String(k))));
      pick.addEventListener("change", () => {
        const def = defs[Number(pick.value)];
        if (!def) return;
        e.definition = def.text;                   // verbatim
        if (!e.notes.trim()) e.notes = definitionNote(def);
        this.renderEmotions();
        this._changed();
      });
      card.append(pick);
    } else if (e.concept_id) {
      card.append(el("p", { class: "hint" }, "The emotion dictionary has no definition for this emotion; enter one."));
    }
    card.append(el("label", { class: "field" }, "Definition", el("textarea", { ...bind("definition"), rows: 2 })),
                el("label", { class: "field" }, "Notes (optional: source, comments)", el("textarea", { ...bind("notes"), rows: 1 })));
    if (!s.dimensions.length) {
      card.append(el("p", { class: "hint" }, "Add quality dimensions (step 2) to enter coordinates."));
    } else {
      const coords = el("div", { class: "coords" });
      s.dimensions.forEach((d, i) => {
        const input = el("input", { inputmode: "decimal", value: e.coordinates[i] ?? "",
                                    dataset: { bind: `emotions.${j}.coordinates.${i}`, field: `emotions.${j}.coordinates.${i}`,
                                               coordFor: String(i) } });
        coords.append(el("label", { class: "field coord" }, el("span", { class: "coord-label", dataset: { coordLabel: String(i) } }), input));
      });
      card.append(el("div", { class: "coords-title muted" }, "Coordinates"), coords);
    }
    return card;
  }

  _refreshLabels() {
    const s = this.state;
    s.dimensions.forEach((d, i) => {
      const range = d.min !== "" || d.max !== "" ? ` [${d.min || "?"}, ${d.max || "?"}]` : "";
      for (const span of this.el.querySelectorAll(`[data-coord-label="${i}"]`)) span.textContent = `${d.name || `dimension ${i + 1}`}${range}`;
    });
  }

  _preview() {
    const data = previewPlotData(this.state);
    const n = this.state.dimensions.length;
    this.preview.setData({ ...data, emptyMessage: !n ? "Add quality dimensions to preview." :
      "Enter coordinates for an emotion\nto preview it." });
    this.ui.previewNote.textContent = n > 3 ? `Showing the first 3 of ${n} dimensions.` :
      data.points.length < this.state.emotions.length ? `${this.state.emotions.length - data.points.length} emotion(s) without complete coordinates are not shown.` : "";
  }

  // ---------------------------------------------------------------- validation and saving
  async validate() {
    let result;
    try {
      result = await validateModel(this.state);
    } catch (err) {
      this.ui.state.textContent = `Validation unavailable: ${err.message}`;
      return null;
    }
    this.lastCheck = result;
    this.showMessages(result);
    return result;
  }

  showMessages(result) {
    for (const node of this.el.querySelectorAll(".invalid")) node.classList.remove("invalid");
    for (const node of this.el.querySelectorAll(".field-error")) node.remove();
    for (const m of result.errors || []) {
      const field = this.el.querySelector(`.form-pane [data-field="${CSS.escape(m.field)}"]`);
      if (field) {
        field.classList.add("invalid");
        field.closest("label, [data-field]")?.append(el("span", { class: "field-error" }, m.message));
      }
    }
    const items = [
      ...(result.errors || []).map((m) => ({ ...m, kind: "error" })),
      ...(result.warnings || []).map((m) => ({ ...m, kind: "warning" })),
    ];
    this.ui.messages.replaceChildren(...(items.length ? items.map((m) =>
      el("li", { class: m.kind, dataset: { target: m.field } }, el("b", {}, m.kind === "error" ? "Error" : "Note"), ` ${m.message}`))
      : [el("li", { class: "ok" }, "Ready to save: the model satisfies the builder's validation rules.")]));
    const dest = result.destination;
    const id = result.model_id;
    this.ui.modelId.textContent = id ? `Model ID: ${id} (SafeID of the name; used for the folder and file names)` : "";
    // Dimension IDs as the builder derives them
    (result.model?.dimensions || []).forEach((d, i) => {
      const span = this.el.querySelector(`[data-role="dim-id-${i}"]`);
      if (span) span.textContent = d.id ? `id: ${d.id}` : "";
    });
    this.ui.destination.replaceChildren(dest && id
      ? el("div", {}, `${dest.yaml}`, el("br"), `${dest.ods}`,
           dest.exists.length ? el("div", { class: "warning" }, "Exists — saving will ask before replacing it.") : "")
      : el("span", { class: "muted" }, "Enter a model name."));
    const errors = (result.errors || []).length;
    this.ui.state.textContent = errors ? `${errors} problem${errors === 1 ? "" : "s"} to fix before saving` : "Valid";
    this.ui.save.disabled = errors > 0;
  }

  focusField(field) {
    const node = this.el.querySelector(`.form-pane [data-field="${CSS.escape(field)}"]`);
    if (node) { node.scrollIntoView({ block: "center" }); node.focus?.(); }
  }

  async save() {
    clearTimeout(this._timer);
    this.ui.save.disabled = true;
    this.ui.state.textContent = "Saving with the builder workbook (LibreOffice)…";
    try {
      let result = await saveModel(this.state, false);
      if (result.needs_confirmation) {
        const files = result.destination.exists.join("\n");
        if (!confirm(`Replace the existing model files?\n${files}`)) {
          this.ui.state.textContent = "Not saved: existing files kept.";
          this.ui.save.disabled = false;
          return result;
        }
        result = await saveModel(this.state, true);
      }
      this.showSaveResult(result);
      await this.validate();             // refresh messages and destination ("exists") for the saved state
      return result;
    } catch (err) {
      this.ui.state.textContent = `Save failed: ${err.message}`;
      return { ok: false, errors: [{ field: "", message: err.message }] };
    } finally {
      this.ui.save.disabled = (this.lastCheck?.errors || []).length > 0;
    }
  }

  showSaveResult(result) {
    if (!result.ok) {
      this.showMessages({ ...(this.lastCheck || {}), errors: result.errors, warnings: result.warnings || [] });
      this.ui.state.textContent = "Not saved.";
      return;
    }
    this.ui.state.textContent = `Saved ${result.model_id}.`;
    const pre = el("pre", { class: "yaml" }, result.yaml_text);
    this.ui.result.replaceChildren(el("div", { class: "save-result" },
      el("h3", {}, "Saved"),
      el("div", { class: "mono small" }, result.yaml, el("br"), result.ods),
      result.replaced.length ? el("p", { class: "hint" }, `Replaced the previous files.`) : "",
      el("p", { class: "hint" }, "The ontology was not changed. To include this model, populate it separately: ",
         el("code", {}, `python3 ontology/populate_ontology.py --domains ${result.model_id}`)),
      el("details", {}, el("summary", {}, "YAML"), pre)));
  }

  _flash(text) {
    this.ui.state.textContent = text;
  }

  // ---------------------------------------------------------------- draft (per browser; convenience only)
  _saveDraft() {
    try { localStorage.setItem(DRAFT_KEY, JSON.stringify(this.state)); } catch { /* storage unavailable */ }
  }

  _loadDraft() {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      const s = raw && JSON.parse(raw);
      return s && Array.isArray(s.dimensions) && Array.isArray(s.emotions) ? s : null;
    } catch {
      return null;
    }
  }
}
