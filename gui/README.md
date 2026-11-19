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

Everything shown is read from the OWL file on disk each time it is loaded. Nothing is hard-coded and the
ontology is never written to.

## Run

From the repository root:

```bash
python3 gui/server.py            # then open http://127.0.0.1:8765/
python3 gui/server.py --open     # same, and open the browser
```

Options: `--port 8765`, `--owl-dir ontology` (folder with `.owl` files), `--default <file.owl>`.
Without `--owl-dir`, the server uses `ontology/`. If `ontology/` contains no `.owl` files, it falls back to
`owl/`, the location used before the move. It checks again on every request, so a move is picked up without a
restart. The status bars show which folder is in use.

Requirements: Python 3.10+ (standard library only) and a modern browser. There are no dependencies to
install, no build step, and no network access. The server listens on `127.0.0.1` only.

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
reads the domain YAML or ODS files. Everything comes from these links in the ontology:

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
  server.py                 local HTTP server + read-only JSON API (/api/ontologies, /api/ontology?file=)
  owl_loader/               ontology loading and parsing (Python, no GUI code)
    rdfxml.py               RDF/XML -> triples (reports unsupported constructs instead of guessing)
    model.py                triples -> entities, edges, class hierarchy, stats
  web/
    index.html, css/style.css
    js/main.js              dashboard layout: tab bar; tabs are registered in one list
    js/api.js               the only module that fetches data
    js/ontology/adapter.js  ontology JSON -> generic graph / tree / inspector structures (pure functions)
    js/ontology/domains.js  ontology JSON -> domains, dimensions, prototypes, coordinates; plot data (pure)
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
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s gui/tests -v
```

| Test file | What it checks |
|---|---|
| `test_loader.py` | Every triple of each `ontology/*.owl` file is read, cross-checked with an independent ElementTree reading. Classes, individuals, properties, edges and literals match the file. Every declared class is in the hierarchy. RDF/XML edge cases are handled. Unsupported constructs are reported. Files are unchanged (sha256). |
| `test_server.py` | The dashboard and assets are served. The API lists and reads the OWL files (sha256 matches). The `ontology/` → `owl/` folder resolution and the domain source are reported. Only listed files are reachable (no path traversal). Files are unchanged. |
| `test_architecture.py` | Components do not import ontology or API code. Both adapters are pure. Tabs use no OWL vocabulary directly. Only `api.js` fetches. No external resources are loaded. |
| `test_browser.py` | Runs the self-test in headless Chrome/Chromium against each OWL file (see below). It also compares every domain, dimension, prototype and raw coordinate string the Domain Models tab extracted with an independent ElementTree reading of `emotional_ontology_populated.owl`. Skipped if no browser is found; set `CHROME=/path/to/browser` to choose one. |

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
