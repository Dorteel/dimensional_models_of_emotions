# Ontology-to-GUI query interface

The GUI reads the ontology only through the SPARQL queries in this folder. The server
(`gui/server.py` → `gui/ontology_service/`) does the following on every request:

1. loads the OWL file with RDFLib, in memory, afresh (no cache, no triple store, no reasoning);
2. runs the named queries below;
3. assembles their result rows into JSON for the frontend.

The browser never sees SPARQL and never walks triples. Only these files can be executed. A query is
addressed by its name (path without `.rq`), and there is no endpoint that accepts SPARQL text.

## Prefixes

| Prefix | Namespace | Notes |
|---|---|---|
| `ecs:` | `http://example.org/conceptual-space-emotion.owl#` | The ontology's own terms: the `xml:base` of `ontology/emotional_ontology_populated.owl`. If the ontology IRI changes, update this prefix in each `.rq` file. |
| `rdf:` | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` | |
| `rdfs:` | `http://www.w3.org/2000/01/rdf-schema#` | |
| `owl:` | `http://www.w3.org/2002/07/owl#` | |

Each file declares the prefixes it uses and documents its result columns in a header comment.

## Queries

| Name | Used by | Returns |
|---|---|---|
| `domains/domains` | Domain Models | Every `ecs:Domain` individual, with optional `rdfs:label` and `ecs:hasModelType`. |
| `domains/quality_dimensions` | Domain Models | `ecs:hasQualityDimension` of each domain, with optional `rdfs:label`, `ecs:hasRange` (raw text), `ecs:isCircular` and `ecs:hasMeasurementLevel`. |
| `domains/prototypes` | Domain Models | Prototypes linked by `ecs:hasDomainPrototype` or `ecs:belongsToDomain`; `?link` tells which. |
| `domains/prototype_classes` | Domain Models | A prototype's asserted `rdf:type`s other than `ecs:PrototypicalInstance` and `owl:NamedIndividual`, i.e. its emotion class. |
| `domains/coordinates` | Domain Models | `ecs:hasPoint` / `ecs:hasCoordinate` / `ecs:onQualityDimension`, and `STR(ecs:numericValue)`, the lexical form exactly as in the file, with its datatype. |
| `domains/definitions` | Domain Models | `ecs:hasDefinition` (domains, dimensions, prototypes) and `ecs:hasClassDefinition` (emotion classes): `ecs:hasValue` text, `ecs:hasSource`, and the source's `rdfs:label`. |
| `domains/notes` | Domain Models | `ecs:hasNotes` on any term. |
| `domains/provenance` | Domain Models | Knowledge repositories (sources) with the number of definitions citing each. |
| `explorer/statements` | Emotional Ontology | Every statement (`?s ?p ?o`); the tab shows what the file states. |

## Rules

- **Nothing is filled in.** An absent optional value stays unbound. The service reports it as missing: the
  GUI shows "not stated in the ontology", "missing — no coordinate on this dimension", and so on.
- **Values are exact.** RDFLib's literal normalisation is switched off, so `1.0` stays `1.0`. Plotted
  coordinates are `float(lexical)` of exactly that string, and the inspector shows the string itself.
- **No reasoning.** Only asserted statements are queried. There are no inferred types and no inherited values.
- **Order is the file's.** SPARQL results are unordered. The service orders dimensions, prototypes and
  explorer lists by where the terms are described in the RDF/XML file (their document position), so a
  domain's axes keep the file's order. Domains are sorted by label.
- **Placeholders are flagged, not hidden.** Definition texts `no known definitions` and `undefined` are passed
  through verbatim with `placeholder: true`.

## API

| Endpoint | Content |
|---|---|
| `GET /api/domains` | Domains, dimensions, prototypes, coordinates, definitions, notes and sources from `emotional_ontology_populated.owl`. `meta.queries` lists the queries used. |
| `GET /api/ontology?file=<name>` | The Emotional Ontology tab model, built from `explorer/statements`. |
| `GET /api/queries` | Name, file, description and text of every query. |
| `GET /api/sparql/<name>[?file=<name>]` | Raw result rows of one named query, as SPARQL-JSON-like terms (`type`, `value`, `datatype`, `lang`). |

## Adding a query

Add a documented `.rq` file here, with a header comment, `PREFIX` lines and a list of result columns. It is
loaded and syntax-checked when the server starts. Use it from `gui/ontology_service/` through
`QueryLibrary.run(name, graph)`. `gui/tests/test_sparql.py` checks that every file is documented, declares
the prefixes it uses and parses.
