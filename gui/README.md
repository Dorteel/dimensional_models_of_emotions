# Emotional Ontology GUI

A local, browser-based dashboard for exploring the Emotional Ontology and creating domain models. It has three tabs.

**Emotional Ontology**:

- an interactive graph of the ontology's classes, individuals and relationships, with zoom, pan, node dragging and selection;
- a class-hierarchy navigator and a property list;
- an inspector that shows every statement the file makes about the selected term.

**Domain Models**:

- the `Domain` individuals of the populated ontology, with their quality dimensions;
- the prototypes' coordinates, plotted as a number line, a 2D scatterplot or an interactive 3D view;
- an inspector for domains, dimensions and prototypes that states missing information explicitly.

**Create Domain Model**:

- the three-step workflow of `domains/create_custom_domain_model.ods` in the browser: domain model,
  quality dimensions, and optional prototypical emotions;
- saving writes `domains/<model_id>/<model_id>.yaml` and `.ods` with the builder workbook's own macros.

Everything the first two tabs show is read from the OWL file on disk each time it is loaded: the server loads
it with RDFLib and answers with the results of the named SPARQL queries in [`sparql/`](sparql/README.md).
Nothing is hard-coded. No tab writes to the ontology: creating a model and populating the ontology remain
separate steps.

## Setup (once)

The server needs [RDFLib](https://rdflib.readthedocs.io/), installed into a virtual environment inside `gui/`
(git-ignored). PyYAML is used by the tests.

```bash
python3 -m venv gui/.venv
gui/.venv/bin/pip install -r gui/requirements.txt      # rdflib==7.1.4, PyYAML==6.0.2
```

Saving in the **Create Domain Model** tab also needs LibreOffice (`soffice`) and a Python with its UNO bridge
and PyYAML, normally the system `python3` with `python3-uno`. That is the same requirement as
`domains/ods_export.py`. The server finds that interpreter itself; set `GUI_UNO_PYTHON=/path/to/python3` to
choose another one.

## Run

From the repository root:

```bash
python3 gui/server.py            # then open http://127.0.0.1:8765/
python3 gui/server.py --open     # same, and open the browser
```

If `python3` cannot import RDFLib, `server.py` restarts itself with `gui/.venv/bin/python`. Running
`gui/.venv/bin/python gui/server.py` directly does the same thing.

Options: `--port 8765`, `--owl-dir ontology` (folder with `.owl` files), `--default <file.owl>`,
`--domains-dir <folder>`, where Create Domain Model saves (default `domains/`; for example a scratch folder for a trial run).
Without `--owl-dir`, the server uses `ontology/`. If `ontology/` contains no `.owl` files, it falls back to
`owl/`, the location used before the move. It checks again on every request, so a move is picked up without a
restart. The status bars show which folder is in use.

Requirements: Python 3.10+, RDFLib (see Setup), LibreOffice for saving domain models, and a modern browser. There is no build step, no external
SPARQL server or triple store, and no network access at run time. The server listens on `127.0.0.1` only.

Deep links:

- `http://127.0.0.1:8765/?file=emotional_ontology.owl&select=Emotion#ontology` opens a file in the ontology
  tab and selects a term by local name, label or IRI.
- `http://127.0.0.1:8765/?domain=circumplex&prototype=happy#domains` opens a domain and selects a prototype.

## Ontology source

The task referred to `AO/Emotional Ontology.owl`. **That folder and file do not exist in this repository.**
The existing ontology files are used instead, unchanged:

| File | Content |
|---|---|
| `ontology/emotional_ontology_populated.owl` | Schema plus population. **Shown by default.** |
| `ontology/emotional_ontology.owl` | Schema only (classes and properties, no individuals). |

Both are RDF/XML as written by Owlready2 (`ontology/create_ontology.py`, `ontology/populate_ontology.py`). The file selector
switches between every `.owl` file in `ontology/`, and **Reload** re-reads the current one from disk. The status bar
shows the file name, its sha256 and the counts, so you can see exactly which version is displayed.

## Using the Emotional Ontology tab

| Action | How |
|---|---|
| Zoom | Mouse wheel, `+`/`−` buttons, or `+`/`-` keys when the graph has focus. **Fit** frames the visible graph. |
| Pan | Drag the background, or use the arrow keys. |
| Move a node | Drag it. |
| Inspect | Click a node, a hierarchy or property item, or a search result. The inspector lists IRI, source line, labels and comments, types, super/subclasses, direct instances, data values (verbatim, with datatype), and outgoing and incoming relations. |
| Navigate | Click any link in the inspector, including the hierarchy breadcrumbs, or use the class tree (▸ expands; badges count direct instances). |
| Reduce clutter | **Focus** shows only the selection and its neighbours (depth 1–3). **Show** filters node kinds, edge kinds and individual relation properties. |

Visual encoding:
- classes are blue squares; individuals are orange circles;
- terms used but not declared in the file (e.g. `owl:Thing`) are dashed;
- edges: blue solid `subClassOf`, orange dotted `rdf:type`, grey relation assertions, purple dashed property domain → range.

Individual labels appear when zoomed in or highlighted.

What is shown is what the file states. There is **no reasoning**: inferred types or inherited relations are
not displayed. The class tree uses only the direct `rdfs:subClassOf` statements. Classes without one are
placed under `owl:Thing`, which is marked "implicit root" when the file does not declare it.

## Using the Domain Models tab

**Data source.** The tab reads only `ontology/emotional_ontology_populated.owl`, re-read on **Reload**. It never
reads the domain YAML or ODS files. `GET /api/domains` runs the queries in `sparql/domains/` and returns their
grouped results; the tab does not traverse triples itself. The queries follow these links in the ontology
(details in [`sparql/README.md`](sparql/README.md)):

- `Domain` `hasQualityDimension` → `QualityDimension`, with `rdfs:label`, `hasRange`, `isCircular`,
  `hasMeasurementLevel`, `hasNotes` and `hasDefinition`;
- `Domain` `hasDomainPrototype` → `PrototypicalInstance`; `belongsToDomain` in the other direction is also accepted;
- the prototype `hasPoint` → `Point`, which `hasCoordinate` → `Coordinate`, with `numericValue` and `onQualityDimension`;
- the prototype's emotion class is its `rdf:type` other than `PrototypicalInstance`.

**Selecting a domain.** Use the **Domain** menu or the tree on the left; the tree also lists dimensions and
prototypes. The header shows the domain's name, its dimensions with their stated range, and its coverage.
The inspector shows the description, notes, dimensions and prototypes.

**Plot**, depending on the number of dimensions:

| Dimensions | Plot |
|---|---|
| 1 | Number line. |
| 2 | Scatterplot with labelled points. |
| 3 | 3D view: drag to rotate, wheel to zoom, double-click or **Reset view** to reset, arrow keys rotate. |
| More than 3 | X/Y/Z pickers choose the projected dimensions. Set Z to "none" for a 2D projection. |

- **Axis ranges:** a stated `hasRange` sets the axis bounds. Otherwise the axis spans the data and is
  labelled "range not stated".
- **Values:** point positions are the `numericValue`s, unchanged.
- **Prototypes that can't be plotted:** those without a value on every plotted dimension are listed under the plot.
- **No coordinates:** a domain with none shows an explanation instead of an empty chart.

**Inspection.** Click a point or tree item. For a prototype, the inspector shows:

- its emotion class, with a link to the ontology tab;
- every dimensional value, verbatim, with its `Coordinate` individual;
- the prototype's definition and the class definitions, each with its source;
- notes and any inconsistencies found in the ontology.

**Missing information is stated, never filled in:**

- missing range, circularity, measurement level, description or notes are labelled "not stated in the ontology";
- placeholder definitions (`no known definitions`, `undefined`) are shown verbatim and marked as placeholders;
- links labelled "open in ontology inspector" switch to the Emotional Ontology tab with that term selected.

## Using the Create Domain Model tab

The tab follows the builder workbook `domains/create_custom_domain_model.ods` and its DomainModel layout
`domains/domain_model_template.ods`:

| Step | Fields |
|---|---|
| 1 Domain model | Name, description, notes. The model ID is `SafeID(name)`: lowercase, `a-z 0-9 _` kept, space and `-` become `_`, everything else dropped. |
| 2 Quality dimensions | 1 to 9 dimensions, each with a name, definition, notes, minimum, maximum and circularity (Yes/No). They can be added, removed and reordered. The dimension ID is `SafeID(name)`. |
| 3 Prototypical emotions (optional) | Up to 30 emotions, each with a definition, notes and a coordinate on every dimension. |

**Adding emotions.** In step 3, an emotion comes from one of two places:

- **From `emotions/emotion_catalogue.ods`:** the name is fixed, and the ID is the catalogue's Concept ID, the
  ID ontology population matches against the dictionary. Its definitions from `emotions/emotion_dictionary.ods`
  are offered; choosing one copies it verbatim and records its source in the notes, which you can edit.
- **New:** you enter the name, and the ID is `SafeID(name)`. A note explains that ontology population requires
  every emotion to be in `emotions/emotion_dictionary.ods`.

**Validation** runs on the server while you type. It applies the builder's rules (`SaveModel`, `AddDimension`,
`AddPrototype`, `BuildDomainYAML`), and each message points at its field:

- required names and definitions;
- unique dimension and emotion names and IDs;
- numeric minimum < maximum, and circularity Yes/No;
- a numeric coordinate inside its dimension's range for every dimension;
- no value beyond the 15 significant digits ODS stores losslessly (the macro's `YAMLNumber` refuses those too);
- the template's limits.

The preview reuses the Domain Models plot.

**Saving** (`POST /api/models/save`) runs `gui/model_builder/office_save.py` with LibreOffice:

1. It fills the DomainModel sheet of a scratch copy of the builder workbook. The workbook itself is never
   modified.
2. It produces the YAML with the workbook's own `BuildDomainYAML`, the function behind **SAVE DOMAIN MODEL**,
   and the ODS with the template plus the workbook's `CopyDomainModelValues`. There is no second exporter.
3. It checks that the YAML loads back as exactly the entered model, and that re-exporting the new ODS with
   `domains/ods_export.py` (`export_yaml`) reproduces the YAML byte for byte.
4. It installs both files like the macro does: staged, the previous pair backed up, and restored if anything
   fails.

**Overwriting.** Saving over an existing `domains/<model_id>/` asks for confirmation. The reference models
(`circumplex`, `pad`, `plutchik_model`, `vector_model`) and `examples`/`drafts` are refused. Only the new model's
folder is written.

**Drafts.** The form is kept as a draft in the browser's local storage until **Clear form**.

**After saving.** The ontology is not changed. To include the model, populate separately, for example
`python3 ontology/populate_ontology.py --domains <model_id>`.

## Architecture

```
gui/
  server.py                 local HTTP server + read-only JSON API (see sparql/README.md)
  requirements.txt          rdflib, PyYAML (installed into gui/.venv)
  sparql/                   the named SPARQL queries (.rq) — the only way the GUI reads the ontology
    domains/*.rq            domains, quality dimensions, prototypes, classes, coordinates, definitions, notes, provenance
    explorer/statements.rq  every statement (Emotional Ontology tab)
    README.md               query interface: prefixes, columns, rules, API
  ontology_service/         Python query service (no GUI code)
    store.py                RDFLib loading (fresh per request, literal lexical forms kept), document positions
    queries.py              QueryLibrary: loads and runs the named .rq files; no ad-hoc SPARQL
    domains.py              query rows -> domains / dimensions / prototypes / coordinates JSON
    explorer.py             query rows -> entities, edges, class hierarchy (Emotional Ontology tab)
    names.py                compact names from the file's prefixes
  model_builder/            Create Domain Model backend (no GUI code)
    catalogue.py            emotions/emotion_catalogue.ods + dictionary definitions (read-only)
    ods_reader.py           minimal ODS cell reader (standard library)
    validation.py           the builder macros' validation rules, field by field; SafeID mirror
    save.py                 destination rules, runs office_save.py with a UNO-capable Python
    office_save.py          fills the builder's DomainModel sheet; YAML/ODS via its macros; atomic install
  web/
    index.html, css/style.css
    js/main.js              dashboard layout: tab bar; tabs are registered in one list
    js/api.js               the only module that fetches data
    js/ontology/adapter.js  ontology JSON -> generic graph / tree / inspector structures (pure functions)
    js/ontology/domains.js  /api/domains JSON -> plot data, tree items, inspector descriptions (pure)
    js/components/          reusable, ontology-agnostic UI components
      graph-view.js         SVG graph: zoom, pan, drag, select, focus, filters
      force-layout.js       deterministic force-directed layout
      tree-view.js          collapsible tree navigator
      inspector.js          detail panel with navigation links
      coordinate-plot.js    number line / scatterplot / 3D view of labelled points
    js/tabs/ontology-tab.js the Emotional Ontology tab: composes the pieces above
    js/tabs/domain-tab.js   the Domain Models tab: tree + coordinate plot + inspector
    js/models/domain-form.js Create Domain Model form state (pure: add/remove/reorder, preview data)
    js/tabs/create-tab.js   the Create Domain Model tab: three-step form, validation messages, preview, save
    js/selftest.js          in-browser end-to-end test (only loaded with ?selftest=1)
    js/selftest-domains.js  Domain Models part of the self-test
    js/selftest-create.js   Create Domain Model part (only with &create=1; the test server saves to a scratch folder)
  tests/                    unittest suite
```

**Adding a tab:** add an entry to `TABS` in `web/js/main.js` with a module whose constructor receives its
panel element and a `context`. `context.openInOntology(file, id)` shows a term in the Emotional Ontology tab. The components in `web/js/components/` take plain data (`{nodes, edges}`, tree items,
inspector descriptions) and can be reused for domain or VLM views. `tests/test_architecture.py` checks that
they stay independent of the ontology code.

## Tests

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 gui/.venv/bin/python -m unittest discover -s gui/tests -v
```

| Test file | What it checks |
|---|---|
| `test_sparql.py` | The query files are complete, documented (header and columns), declare their prefixes and parse. Only named queries run, and there is no SPARQL text in Python or JS. `explorer/statements` equals an independent ElementTree reading of each OWL file; entities, edges, literals, hierarchy and "defined at" lines match. Against RDFLib's triple API (no SPARQL) and the raw XML: 4 domains, 36 prototypes and 80 coordinates; labels, dimensions, ranges, notes, classes, definitions with sources, and provenance counts match; coordinate strings are exact; order follows the file. The schema-only file has no domains. Reload re-reads the file (tested on a temporary copy). Ontology files are unchanged. |
| `independent.py` | Helper module, not a test: the independent ElementTree and RDFLib-triple-API readings used above. |
| `test_server.py` | The dashboard and assets are served. The catalogue endpoint works. The model endpoints accept only same-origin JSON (415/403/400/404 otherwise), and validation reports field errors and the destination without writing. The API lists and reads the OWL files (sha256 matches). The `ontology/` → `owl/` folder resolution and the domain source are reported. `/api/domains` is built by SPARQL. Named queries are listed and runnable, and no user-supplied SPARQL is accepted. Only listed files are reachable (no path traversal). Files are unchanged. |
| `test_architecture.py` | Components do not import ontology or API code. Both adapters and the form-state module are pure. Tabs use no OWL vocabulary directly. There is no SPARQL in JavaScript. Only `api.js` fetches. No external resources are loaded. |
| `test_model_builder.py` | Validation rules field by field; the `SafeID` and precision mirrors; the ODS reader (repeats, whitespace, stored values) and the catalogue/dictionary against LibreOffice's own reading. Saving into temporary folders, with each pair checked independently: the YAML is parsed; the ODS has only DomainModel, no macros, and every cell (numbers as stored values) equals the model; the existing `python3 domains/ods_export.py --export` reproduces the YAML byte for byte. Also: models without prototypes; nothing written for invalid models; overwrite only after confirmation; rollback after a failed commit; no empty folder left behind; reserved names and non-folder conflicts refused; only the model's folder written. The builder, the template and the repository's `domains/` folder are unchanged. |
| `test_browser.py` | Runs the self-test in headless Chrome/Chromium against each OWL file (see below). A further run fills and saves the Create Domain Model form against a server that saves to a temporary folder; the saved files are then checked, and the repository's `domains/` folder is unchanged. It also compares every domain, dimension, prototype and raw coordinate string the Domain Models tab received from `/api/domains` (SPARQL) with an independent ElementTree reading of `emotional_ontology_populated.owl`. Skipped if no browser is found; set `CHROME=/path/to/browser` to choose one. |

The self-test in `test_browser.py` drives the real UI with DOM events and compares the result with the API
data. Expected values are derived from the file. It checks that:

- the graph contains every class, individual and relationship;
- clicking class and individual nodes fills the inspector;
- inspector links navigate between nodes;
- wheel and button zoom, background panning and node dragging work;
- expanding the tree and selecting a class centres it in the graph, and breadcrumbs navigate up;
- focus mode, filters and search work.

For the Domain Models tab it checks that:

- every `Domain` individual is listed, and each domain gets the right plot mode or an empty state;
- every plotted point carries its ontology values verbatim, and its pixel position is a linear function of
  those values (in 3D, checked in a fixed front view);
- clicking a point shows its emotion class, values, definitions and notes;
- missing ranges and placeholder definitions are stated;
- tree navigation and the link to the ontology inspector work;
- 3D rotate, zoom and reset work.

Two modes have no domain with coordinates in the current ontology, so they are tested with components only:

- the number line, using the real values of one dimension;
- the more-than-3 projection, using a synthetic 4-D domain that exists only during the test and is removed afterwards.

For the Create Domain Model tab (`&create=1`) it checks:

- validation messages on the right fields: empty form, minimum ≥ maximum, duplicate names, out-of-range and
  over-precise coordinates, reserved names;
- `SafeID` model and dimension IDs, and the destination path;
- adding catalogue emotions (name and Concept ID fixed), and copying a dictionary definition verbatim with its
  source;
- that new emotions are accepted with a note;
- that reordering dimensions moves the coordinates;
- the preview plot;
- saving, and overwrite confirmation (declined, then accepted).

To watch the self-test in a normal browser, open `http://127.0.0.1:8765/?selftest=1`. The results appear at
the bottom of the page. Add `&create=1` only with `--domains-dir` pointing to a scratch folder, because that
part saves a model.

## Not in this iteration

VLM inference is deliberately not implemented. Existing models are not loaded back into the form; edit their
ODS and re-export with `domains/ods_export.py`. The GUI does not create or change ontology classes, properties
or files, and it never populates the ontology.
