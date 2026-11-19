"""Compact display names for IRIs, using the prefixes declared in the ontology file."""

from __future__ import annotations

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
XSD = "http://www.w3.org/2001/XMLSchema#"
WELL_KNOWN = {RDF: "rdf", RDFS: "rdfs", OWL: "owl", XSD: "xsd"}


class Names:
    def __init__(self, prefixes: dict, base: str | None):
        ns = [(uri, prefix) for prefix, uri in prefixes.items()]
        for uri, prefix in WELL_KNOWN.items():
            if all(u != uri for u, _ in ns):
                ns.append((uri, prefix))
        if base and all(u != base + "#" for u, _ in ns):
            ns.append((base + "#", ""))
        self.ns = sorted(ns, key=lambda item: -len(item[0]))   # longest namespace first

    def short(self, iri: str) -> str:
        for uri, prefix in self.ns:
            if uri and iri.startswith(uri) and len(iri) > len(uri):
                local = iri[len(uri):]
                return local if prefix == "" else f"{prefix}:{local}"
        return iri


def graph_prefixes(graph) -> dict:
    return {prefix: str(uri) for prefix, uri in graph.namespaces()}
