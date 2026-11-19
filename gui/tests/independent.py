"""Independent readings of an ontology file, used by the tests to check the SPARQL-based service.

* `et_*` functions read the raw RDF/XML with ElementTree (no RDFLib, no SPARQL, no GUI code). They give the
  literals' exact lexical forms and the order of statements in the file. They handle the flat RDF/XML that
  Owlready2 writes (top-level node elements with simple property elements) and fail loudly otherwise.
* `graph_*` functions inspect an RDFLib graph through its triple API (Graph.objects/subjects), not SPARQL.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from rdflib import Graph, Literal, Namespace, RDF, RDFS

RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
XML_NS = "{http://www.w3.org/XML/1998/namespace}"
ECS = Namespace("http://example.org/conceptual-space-emotion.owl#")


def _local(tag):
    return re.split(r"[#/}]", tag)[-1]


def et_triples(path):
    """All statements as (subject, predicate, ("iri", value) | ("lit", lexical, datatype, lang))."""
    root = ET.parse(path).getroot()
    base = root.get(XML_NS + "base", "")
    full = lambda ref: base + ref if ref.startswith("#") else ref  # noqa: E731
    iri = lambda tag: tag[1:].replace("}", "")  # noqa: E731
    triples = set()
    for node in root:
        about = node.get(f"{{{RDF_NS}}}about")
        assert about is not None, f"unexpected node element without rdf:about: {node.tag}"
        s = full(about)
        if node.tag != f"{{{RDF_NS}}}Description":
            triples.add((s, RDF_NS + "type", ("iri", iri(node.tag))))
        for prop in node:
            assert len(prop) == 0, "nested node elements are outside this independent reader"
            res = prop.get(f"{{{RDF_NS}}}resource")
            if res is not None:
                triples.add((s, iri(prop.tag), ("iri", full(res))))
            else:
                triples.add((s, iri(prop.tag), ("lit", prop.text or "", prop.get(f"{{{RDF_NS}}}datatype"),
                                                prop.get(XML_NS + "lang"))))
    return triples


def et_nodes(path):
    """{subject IRI: {"types": set(local names), "props": {local predicate: [values in file order]}}}."""
    root = ET.parse(path).getroot()
    base = root.get(XML_NS + "base", "")
    full = lambda ref: base + ref if ref.startswith("#") else ref  # noqa: E731
    nodes = {}
    for node in root:
        about = node.get(f"{{{RDF_NS}}}about")
        if about is None:
            continue
        entry = nodes.setdefault(full(about), {"types": set(), "props": {}})
        if node.tag != f"{{{RDF_NS}}}Description":
            entry["types"].add(_local(node.tag))
        for prop in node:
            res = prop.get(f"{{{RDF_NS}}}resource")
            value = full(res) if res is not None else (prop.text or "")
            if prop.tag == f"{{{RDF_NS}}}type":
                entry["types"].add(_local(value))
            else:
                entry["props"].setdefault(_local(prop.tag), []).append(value)
    return nodes


def et_domains(path):
    """Domains with dimensions and prototypes in file statement order, and raw coordinate strings."""
    nodes = et_nodes(path)
    get = lambda iri, p: nodes.get(iri, {"props": {}})["props"].get(p, [])  # noqa: E731
    domains = {}
    for iri, n in nodes.items():
        if "Domain" not in n["types"]:
            continue
        dims = list(dict.fromkeys(get(iri, "hasQualityDimension")))
        protos = list(dict.fromkeys(get(iri, "hasDomainPrototype") +
                                    [s for s in nodes if iri in get(s, "belongsToDomain")]))
        table = {}
        for p in protos:
            found = {}
            for point in get(p, "hasPoint"):
                for c in get(point, "hasCoordinate"):
                    for dim in get(c, "onQualityDimension"):
                        found.setdefault(dim, []).extend(get(c, "numericValue"))
            table[p] = {dim: (found[dim][0] if len(found.get(dim, [])) == 1 else
                              " | ".join(found[dim]) if found.get(dim) else None) for dim in dims}
        domains[iri] = {"label": (get(iri, "label") or [iri])[0], "dimensions": dims, "prototypes": table}
    return domains


# ------------------------------------------------------------------ RDFLib triple API (no SPARQL)

def graph_domains(graph: Graph) -> dict:
    out = {}
    for d in graph.subjects(RDF.type, ECS.Domain):
        dims = set(graph.objects(d, ECS.hasQualityDimension))
        protos = set(graph.objects(d, ECS.hasDomainPrototype)) | set(graph.subjects(ECS.belongsToDomain, d))
        coords = {}
        for p in protos:
            row = {}
            for point in graph.objects(p, ECS.hasPoint):
                for c in graph.objects(point, ECS.hasCoordinate):
                    for dim in graph.objects(c, ECS.onQualityDimension):
                        row.setdefault(str(dim), []).extend(str(v) for v in graph.objects(c, ECS.numericValue))
            coords[str(p)] = {k: sorted(v) for k, v in row.items()}
        classes = {str(p): sorted(str(t) for t in graph.objects(p, RDF.type)
                                  if t not in (ECS.PrototypicalInstance,) and not str(t).endswith("#NamedIndividual"))
                   for p in protos}
        out[str(d)] = {
            "labels": sorted(str(x) for x in graph.objects(d, RDFS.label)),
            "notes": sorted(str(x) for x in graph.objects(d, ECS.hasNotes)),
            "dimensions": {str(x): {"labels": sorted(str(v) for v in graph.objects(x, RDFS.label)),
                                    "ranges": sorted(str(v) for v in graph.objects(x, ECS.hasRange)),
                                    "circular": sorted(str(v) for v in graph.objects(x, ECS.isCircular)),
                                    "notes": sorted(str(v) for v in graph.objects(x, ECS.hasNotes))} for x in dims},
            "prototypes": {str(p): sorted(str(v) for v in graph.objects(p, RDFS.label)) for p in protos},
            "coordinates": coords,
            "classes": classes,
        }
    return out


def graph_definitions(graph: Graph, subject, prop) -> list:
    """[(text values sorted, source labels sorted)] for subject --prop--> Definition."""
    out = []
    for d in graph.objects(subject, prop):
        texts = sorted(str(t) for t in graph.objects(d, ECS.hasValue))
        sources = sorted(str(lbl) for s in graph.objects(d, ECS.hasSource) for lbl in graph.objects(s, RDFS.label))
        out.append((texts, sources))
    return sorted(out)


def literal_lexical(term) -> str:
    assert isinstance(term, Literal)
    return str(term)
