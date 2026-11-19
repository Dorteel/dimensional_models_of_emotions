"""Build a JSON-serialisable view of an OWL ontology from RDF triples.

The view is a faithful re-arrangement of the triples in the file; nothing is
inferred except what is needed to arrange them (e.g. listing a class's direct
instances). Terms that are used but never declared are marked `declared: false`.

Output (see `load_ontology`):
  meta        file path, sha256, size, mtime, ontology IRI, base, prefixes
  entities    {id: {id, iri, label, kind, declared, types, line, literals, ...}}
  edges       [{source, target, kind, predicate, label, line}]
  hierarchy   [{id, children: [...], instances: [...]}]  (class tree; roots under owl:Thing)
  stats       counts per kind
  warnings    unsupported RDF/XML constructs reported by the reader
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from .rdfxml import BNode, IRI, Literal, parse_rdfxml

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
XSD = "http://www.w3.org/2001/XMLSchema#"

TYPE = RDF + "type"
SUBCLASS = RDFS + "subClassOf"
SUBPROPERTY = RDFS + "subPropertyOf"
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
# Characteristics such as owl:FunctionalProperty are extra types of a property.
PROPERTY_CHARACTERISTICS = {OWL + t for t in ("FunctionalProperty", "InverseFunctionalProperty", "TransitiveProperty",
                                               "SymmetricProperty", "AsymmetricProperty", "ReflexiveProperty",
                                               "IrreflexiveProperty")}
INDIVIDUAL_TYPE = OWL + "NamedIndividual"
ONTOLOGY_TYPE = OWL + "Ontology"
OWL_THING = OWL + "Thing"
WELL_KNOWN = {RDF: "rdf", RDFS: "rdfs", OWL: "owl", XSD: "xsd"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class _Names:
    """Compact, unique display names for IRIs using the file's own prefixes."""

    def __init__(self, prefixes, base):
        self.ns = []
        for prefix, uri in prefixes.items():
            self.ns.append((uri, prefix))
        for uri, prefix in WELL_KNOWN.items():
            if all(u != uri for u, _ in self.ns):
                self.ns.append((uri, prefix))
        if base and all(u != base + "#" for u, _ in self.ns):
            self.ns.append((base + "#", ""))
        self.ns.sort(key=lambda item: -len(item[0]))  # longest namespace first

    def short(self, iri: str) -> str:
        for uri, prefix in self.ns:
            if uri and iri.startswith(uri) and len(iri) > len(uri):
                local = iri[len(uri):]
                return local if prefix == "" else f"{prefix}:{local}"
        return iri


def _term_id(term):
    return term.value if isinstance(term, IRI) else "_:" + term.value


def load_ontology(path) -> dict:
    path = Path(path)
    stat = path.stat()
    parsed = parse_rdfxml(path)
    names = _Names(parsed.prefixes, parsed.base)
    triples = parsed.triples

    types = defaultdict(list)
    for t in triples:
        if t.p.value == TYPE and not isinstance(t.o, Literal):
            types[_term_id(t.s)].append(_term_id(t.o))

    first_line = {}
    for t in triples:
        first_line.setdefault(_term_id(t.s), t.line)

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
    for t in triples:
        s_id, p_id = _term_id(t.s), t.p.value
        s = entity(s_id)
        if isinstance(t.o, Literal):
            lit = {"predicate": p_id, "predicate_name": names.short(p_id), "value": t.o.value,
                   "datatype": t.o.datatype, "datatype_name": names.short(t.o.datatype) if t.o.datatype else None,
                   "lang": t.o.lang, "line": t.line}
            if p_id == LABEL:
                s["labels"].append(lit)
            elif p_id == COMMENT:
                s["comments"].append(lit)
            else:
                s["literals"].append(lit)
            continue
        o_id = _term_id(t.o)
        if p_id == TYPE:
            if o_id in PROPERTY_TYPES:
                s["property_kind"] = PROPERTY_TYPES[o_id]
            elif o_id in PROPERTY_CHARACTERISTICS:
                s["characteristics"].append(names.short(o_id))
            if o_id in CLASS_TYPES or o_id in PROPERTY_TYPES or o_id in PROPERTY_CHARACTERISTICS \
                    or o_id in (INDIVIDUAL_TYPE, ONTOLOGY_TYPE):
                s["types"].append({"id": o_id, "name": names.short(o_id), "builtin": True, "line": t.line})
                continue
            o = entity(o_id, "class")
            s["types"].append({"id": o_id, "name": o["name"], "builtin": False, "line": t.line})
            o["instances"].append(s_id)
            edges.append({"source": s_id, "target": o_id, "kind": "type", "predicate": TYPE,
                          "label": "rdf:type", "line": t.line})
            continue
        if p_id == SUBCLASS:
            o = entity(o_id, "class")
            s["superclasses"].append(o_id)
            o["subclasses"].append(s_id)
            edges.append({"source": s_id, "target": o_id, "kind": "subclass", "predicate": SUBCLASS,
                          "label": "rdfs:subClassOf", "line": t.line})
            continue
        if p_id in (DOMAIN, RANGE):
            is_datatype = o_id.startswith(XSD) or o_id == RDFS + "Literal"
            o = entity(o_id, "datatype" if is_datatype else "class")
            s["domain" if p_id == DOMAIN else "range"].append(o_id)
            continue
        o = entity(o_id)
        s["out"].append({"predicate": p_id, "predicate_name": names.short(p_id), "target": o_id, "line": t.line})
        o["in"].append({"predicate": p_id, "predicate_name": names.short(p_id), "source": s_id, "line": t.line})
        edges.append({"source": s_id, "target": o_id, "kind": "relation", "predicate": p_id,
                      "label": names.short(p_id), "line": t.line})

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
        "meta": {"file": path.name, "path": str(path), "sha256": _sha256(path), "size": stat.st_size,
                 "mtime": stat.st_mtime, "ontology_iri": ontology_iri, "base": parsed.base,
                 "prefixes": parsed.prefixes},
        "entities": entities,
        "edges": edges,
        "hierarchy": hierarchy,
        "stats": dict(stats),
        "warnings": parsed.warnings,
    }


def find_ontologies(directory) -> list[Path]:
    directory = Path(directory)
    return sorted(p for p in directory.glob("*.owl") if p.is_file()) if directory.is_dir() else []


__all__ = ["load_ontology", "find_ontologies"]
