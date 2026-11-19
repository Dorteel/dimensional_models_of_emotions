"""Model for the Emotional Ontology tab, built from the result of the SPARQL query explorer/statements.

The query returns every statement of the file; this module arranges the rows into entities (classes,
individuals, properties), edges and the asserted class hierarchy. Nothing is inferred (no reasoning).
The JSON shape is the one the Emotional Ontology tab consumes:

  meta        file, path, sha256, size, mtime, parser, ontology IRI, base, prefixes, queries used
  entities    {id: {id, iri, name, label, kind, declared, line, types, labels, comments, literals,
                    superclasses, subclasses, instances, domain, range, property_kind, characteristics, out, in}}
  edges       [{source, target, kind, predicate, label, line}]
  hierarchy   {id: owl:Thing, implicit, children: [...], instances: [...]}
  stats       counts per kind
  warnings    always empty (RDFLib reports unreadable files as errors)
"""

from __future__ import annotations

from collections import defaultdict

from rdflib import Literal

from .names import OWL, RDF, RDFS, XSD, Names, graph_prefixes
from .queries import QueryLibrary, term_id
from .queries import term_id as _tid   # the model code below uses "term_id" as a variable name
from .store import LoadedOntology

STATEMENTS_QUERY = "explorer/statements"

TYPE = RDF + "type"
SUBCLASS = RDFS + "subClassOf"
DOMAIN = RDFS + "domain"
RANGE = RDFS + "range"
LABEL = RDFS + "label"
COMMENT = RDFS + "comment"

CLASS_TYPES = {OWL + "Class", RDFS + "Class"}
PROPERTY_TYPES = {
    OWL + "ObjectProperty": "object",
    OWL + "DatatypeProperty": "datatype",
    OWL + "AnnotationProperty": "annotation",
    RDF + "Property": "rdf",
}
PROPERTY_CHARACTERISTICS = {OWL + t for t in ("FunctionalProperty", "InverseFunctionalProperty", "TransitiveProperty",
                                               "SymmetricProperty", "AsymmetricProperty", "ReflexiveProperty",
                                               "IrreflexiveProperty")}
INDIVIDUAL_TYPE = OWL + "NamedIndividual"
ONTOLOGY_TYPE = OWL + "Ontology"
OWL_THING = OWL + "Thing"


def statements(loaded: LoadedOntology, library: QueryLibrary):
    """Rows of explorer/statements as (subject id, predicate IRI, object term), in document order."""
    _, rows = library.run(STATEMENTS_QUERY, loaded.graph)
    triples = [(term_id(r["s"]), str(r["p"]), r["o"]) for r in rows]
    pos = loaded.document.position
    # RDF is unordered: order by the subject's and object's position in the file (then by IRI / lexical form),
    # which reproduces the file's own order for lists such as a domain's dimensions.
    def key(t):
        s, p, o = t
        obj = (float("inf"), str(o)) if isinstance(o, Literal) else (pos(term_id(o)), term_id(o))
        return (pos(s), s, p, obj)
    return sorted(triples, key=key)


def build_explorer_model(loaded: LoadedOntology, library: QueryLibrary) -> dict:
    graph = loaded.graph
    names = Names(graph_prefixes(graph), loaded.document.base)
    triples = statements(loaded, library)

    types = defaultdict(list)
    for s_id, p_id, o in triples:
        if p_id == TYPE and not isinstance(o, Literal):
            types[s_id].append(_tid(o))

    first_line = loaded.document.lines

    def kind_of(term_id):
        ts = set(types.get(term_id, []))
        if ts & CLASS_TYPES:
            return "class"
        for prop_type, prop_kind in PROPERTY_TYPES.items():
            if prop_type in ts:
                return "property"
        if ONTOLOGY_TYPE in ts:
            return "ontology"
        if INDIVIDUAL_TYPE in ts:
            return "individual"
        return None

    entities = {}

    def entity(term_id, declared_kind=None):
        if term_id not in entities:
            kind = kind_of(term_id)
            entities[term_id] = {
                "id": term_id,
                "iri": None if term_id.startswith("_:") else term_id,
                "name": term_id if term_id.startswith("_:") else names.short(term_id),
                "kind": kind or declared_kind or "resource",
                "declared": kind is not None,
                "line": first_line.get(term_id),
                "types": [],
                "labels": [],
                "comments": [],
                "literals": [],        # [{predicate, value, datatype, lang, line}]
                "superclasses": [],
                "subclasses": [],
                "instances": [],
                "domain": [],
                "range": [],
                "property_kind": None,
                "characteristics": [],
                "out": [],             # [{predicate, target, line}]
                "in": [],              # [{predicate, source, line}]
            }
        return entities[term_id]

    # Declared entities first, so kinds come from declarations.
    for term_id in list(types):
        if kind_of(term_id):
            entity(term_id)

    edges = []
    for s_id, p_id, o in triples:
        s = entity(s_id)
        line = first_line.get(s_id)   # statements are located by their subject's description
        if isinstance(o, Literal):
            dt = str(o.datatype) if o.datatype is not None else None
            lit = {"predicate": p_id, "predicate_name": names.short(p_id), "value": str(o),
                   "datatype": dt, "datatype_name": names.short(dt) if dt else None,
                   "lang": o.language or None, "line": line}
            if p_id == LABEL:
                s["labels"].append(lit)
            elif p_id == COMMENT:
                s["comments"].append(lit)
            else:
                s["literals"].append(lit)
            continue
        o_id = _tid(o)
        if p_id == TYPE:
            if o_id in PROPERTY_TYPES:
                s["property_kind"] = PROPERTY_TYPES[o_id]
            elif o_id in PROPERTY_CHARACTERISTICS:
                s["characteristics"].append(names.short(o_id))
            if o_id in CLASS_TYPES or o_id in PROPERTY_TYPES or o_id in PROPERTY_CHARACTERISTICS \
                    or o_id in (INDIVIDUAL_TYPE, ONTOLOGY_TYPE):
                s["types"].append({"id": o_id, "name": names.short(o_id), "builtin": True, "line": line})
                continue
            o = entity(o_id, "class")
            s["types"].append({"id": o_id, "name": o["name"], "builtin": False, "line": line})
            o["instances"].append(s_id)
            edges.append({"source": s_id, "target": o_id, "kind": "type", "predicate": TYPE,
                          "label": "rdf:type", "line": line})
            continue
        if p_id == SUBCLASS:
            o = entity(o_id, "class")
            s["superclasses"].append(o_id)
            o["subclasses"].append(s_id)
            edges.append({"source": s_id, "target": o_id, "kind": "subclass", "predicate": SUBCLASS,
                          "label": "rdfs:subClassOf", "line": line})
            continue
        if p_id in (DOMAIN, RANGE):
            is_datatype = o_id.startswith(XSD) or o_id == RDFS + "Literal"
            o = entity(o_id, "datatype" if is_datatype else "class")
            s["domain" if p_id == DOMAIN else "range"].append(o_id)
            continue
        o = entity(o_id)
        s["out"].append({"predicate": p_id, "predicate_name": names.short(p_id), "target": o_id, "line": line})
        o["in"].append({"predicate": p_id, "predicate_name": names.short(p_id), "source": s_id, "line": line})
        edges.append({"source": s_id, "target": o_id, "kind": "relation", "predicate": p_id,
                      "label": names.short(p_id), "line": line})

    # Property schema: domain -> range, one edge per (domain, range) pair, labelled with the property.
    for e in entities.values():
        if e["kind"] == "property":
            for d in e["domain"]:
                for r in e["range"]:
                    edges.append({"source": d, "target": r, "kind": "domain_range", "predicate": e["id"],
                                  "label": e["name"], "line": e["line"]})

    for e in entities.values():
        labels = [l["value"] for l in e["labels"]]
        e["label"] = labels[0] if labels else e["name"]
        if e["kind"] == "resource" and e["declared"] is False and e["types"]:
            e["kind"] = "individual"  # typed by a (possibly undeclared) class: an individual by assertion

    # Class hierarchy (direct subclass links only; classes without a superclass hang under owl:Thing).
    classes = {k: e for k, e in entities.items() if e["kind"] == "class" and k != OWL_THING}

    def tree(class_id, seen):
        if class_id in seen:  # cycle guard
            return {"id": class_id, "children": [], "instances": [], "cycle": True}
        seen = seen | {class_id}
        node = entities[class_id]
        return {"id": class_id,
                "children": [tree(c, seen) for c in sorted(node["subclasses"], key=lambda c: entities[c]["label"].lower())
                             if c in classes],
                "instances": sorted(node["instances"], key=lambda i: entities[i]["label"].lower())}

    roots = sorted((k for k, e in classes.items() if not [s for s in e["superclasses"] if s in classes]),
                   key=lambda k: classes[k]["label"].lower())
    untyped = sorted((k for k, e in entities.items() if e["kind"] == "individual" and
                      not [t for t in e["types"] if not t["builtin"]]), key=lambda k: entities[k]["label"].lower())
    hierarchy = {"id": OWL_THING, "label": "owl:Thing", "implicit": OWL_THING not in entities,
                 "children": [tree(r, set()) for r in roots], "instances": untyped}

    ontology_iri = next((k for k, e in entities.items() if e["kind"] == "ontology"), None)
    stats = defaultdict(int)
    for e in entities.values():
        stats[e["kind"] + ("" if e["declared"] else "_undeclared")] += 1
    for edge in edges:
        stats["edges_" + edge["kind"]] += 1
    stats["triples"] = len(triples)

    return {
        "meta": {**loaded.meta, "ontology_iri": ontology_iri, "base": loaded.document.base,
                 "prefixes": graph_prefixes(graph), "queries": [STATEMENTS_QUERY]},
        "entities": entities,
        "edges": edges,
        "hierarchy": hierarchy,
        "stats": dict(stats),
        "warnings": [],
    }
