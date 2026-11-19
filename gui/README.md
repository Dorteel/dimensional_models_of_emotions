# Emotional Ontology GUI

A local, browser-based dashboard for exploring the Emotional Ontology. It has two tabs.

**Emotional Ontology**:

- an interactive graph of the ontology's classes, individuals and relationships, with zoom, pan, node dragging and selection;
- a class-hierarchy navigator and a property list;
- an inspector that shows every statement the file makes about the selected term.

**Domain Models**:

- the `Domain` individuals of the populated ontology, with their quality dimensions;
- the prototypes' coordinates, plotted as a number line, a 2D scatterplot or an interactive 3D view;
- an inspector for domains, dimensions and prototypes that states missing information explicitly.

Everything shown is read from the OWL file on disk each time it is loaded: the server loads it with RDFLib
and answers with the results of the named SPARQL queries in [`sparql/`](sparql/README.md). Nothing is
hard-coded and the ontology is never written to.

## Setup (once)

The server needs [RDFLib](https://rdflib.readthedocs.io/), installed into a virtual environment inside `gui/`
(git-ignored):

```bash
python3 -m venv gui/.venv
gui/.venv/bin/pip install -r gui/requirements.txt      # rdflib==7.1.4
```

## Run

From the repository root:

```bash
python3 gui/server.py            # then open http://127.0.0.1:8765/
python3 gui/server.py --open     # same, and open the browser
```

If `python3` cannot import RDFLib, `server.py` restarts itself with `gui/.venv/bin/python`. Running
`gui/.venv/bin/python gui/server.py` directly does the same thing.

Options: `--port 8765`, `--owl-dir ontology` (folder with `.owl` files), `--default <file.owl>`.
Without `--owl-dir`, the server uses `ontology/`. If `ontology/` contains no `.owl` files, it falls back to
`owl/`, the location used before the move. It checks again on every request, so a move is picked up without a
restart. The status bars show which folder is in use.

Requirements: Python 3.10+, RDFLib (see Setup) and a modern browser. There is no build step, no external
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

## Architecture

```
gui/
  server.py                 local HTTP server + read-only JSON API (see sparql/README.md)
  requirements.txt          rdflib (installed into gui/.venv)
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
    js/selftest.js          in-browser end-to-end test (only loaded with ?selftest=1)
    js/selftest-domains.js  Domain Models part of the self-test
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
| `test_server.py` | The dashboard and assets are served. The API lists and reads the OWL files (sha256 matches). The `ontology/` → `owl/` folder resolution and the domain source are reported. `/api/domains` is built by SPARQL. Named queries are listed and runnable, and no user-supplied SPARQL is accepted. Only listed files are reachable (no path traversal). Files are unchanged. |
| `test_architecture.py` | Components do not import ontology or API code. Both adapters are pure. Tabs use no OWL vocabulary directly. There is no SPARQL in JavaScript. Only `api.js` fetches. No external resources are loaded. |
| `test_browser.py` | Runs the self-test in headless Chrome/Chromium against each OWL file (see below). It also compares every domain, dimension, prototype and raw coordinate string the Domain Models tab received from `/api/domains` (SPARQL) with an independent ElementTree reading of `emotional_ontology_populated.owl`. Skipped if no browser is found; set `CHROME=/path/to/browser` to choose one. |

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

To watch the self-test in a normal browser, open `http://127.0.0.1:8765/?selftest=1`. The results appear at
the bottom of the page.

## Not in this iteration

Domain-model editing and VLM inference are deliberately not implemented. The GUI does not create or change
ontology classes, properties or files.
