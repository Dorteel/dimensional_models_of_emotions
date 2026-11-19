# Emotional Ontology GUI

A local, browser-based dashboard for exploring the Emotional Ontology. This first iteration has one tab,
**Emotional Ontology**:

- an interactive graph of the ontology's classes, individuals and relationships, with zoom, pan, node dragging and selection;
- a class-hierarchy navigator and a property list;
- an inspector that shows every statement the file makes about the selected term.

Everything shown is read from the OWL file on disk each time it is loaded. Nothing is hard-coded and the
ontology is never written to.

## Run

From the repository root:

```bash
python3 gui/server.py            # then open http://127.0.0.1:8765/
python3 gui/server.py --open     # same, and open the browser
```

Options: `--port 8765`, `--owl-dir ontology` (folder with `.owl` files), `--default <file.owl>`.

Requirements: Python 3.10+ (standard library only) and a modern browser. There are no dependencies to
install, no build step, and no network access. The server listens on `127.0.0.1` only.

Deep links: `http://127.0.0.1:8765/?file=emotional_ontology.owl&select=Emotion` opens a given file and
selects a term by local name, label or IRI.

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
    js/components/          reusable, ontology-agnostic UI components
      graph-view.js         SVG graph: zoom, pan, drag, select, focus, filters
      force-layout.js       deterministic force-directed layout
      tree-view.js          collapsible tree navigator
      inspector.js          detail panel with navigation links
    js/tabs/ontology-tab.js the Emotional Ontology tab: composes the pieces above
    js/selftest.js          in-browser end-to-end test (only loaded with ?selftest=1)
  tests/                    unittest suite
```

**Adding a tab:** add an entry to `TABS` in `web/js/main.js` with a module whose constructor receives its
panel element. The components in `web/js/components/` take plain data (`{nodes, edges}`, tree items,
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
| `test_server.py` | The dashboard and assets are served. The API lists and reads the OWL files (sha256 matches). Only listed files are reachable (no path traversal). Files are unchanged. |
| `test_architecture.py` | Components do not import ontology or API code. The adapter is pure. Only `api.js` fetches. No external resources are loaded. |
| `test_browser.py` | Runs `web/js/selftest.js` in headless Chrome/Chromium against each OWL file (see below). Skipped if no browser is found; set `CHROME=/path/to/browser` to choose one. |

The self-test in `test_browser.py` drives the real UI with DOM events and compares the result with the API
data. Expected values are derived from the file. It checks that:

- the graph contains every class, individual and relationship;
- clicking class and individual nodes fills the inspector;
- inspector links navigate between nodes;
- wheel and button zoom, background panning and node dragging work;
- expanding the tree and selecting a class centres it in the graph, and breadcrumbs navigate up;
- focus mode, filters and search work.

To watch the self-test in a normal browser, open `http://127.0.0.1:8765/?selftest=1`. The results appear at
the bottom of the page.

## Not in this iteration

Domain-model editing, domain visualisation and VLM inference are deliberately not implemented. The GUI does
not create or change ontology classes, properties or files.
