"""Load an ontology file into an RDFLib graph (fresh on every call; no cache, no external store).

Besides the graph, the loader records *document positions*: the line on which each subject is first
described in the RDF/XML file. RDF itself is unordered, so these positions are used only for provenance
("defined at line N") and to keep the GUI's ordering stable and identical to the file (e.g. a domain's
dimensions appear in the order they are declared). They are never used to read ontology content.
"""

from __future__ import annotations

import hashlib
import time
import xml.sax
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin

import rdflib
from rdflib import Graph

# Keep every literal's lexical form exactly as written in the file (e.g. "1.0" must not become "1").
rdflib.NORMALIZE_LITERALS = False

RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
XML_NS = "http://www.w3.org/XML/1998/namespace"


@dataclass
class DocumentInfo:
    base: str | None = None
    lines: dict = field(default_factory=dict)   # subject IRI -> first line where it is described

    def position(self, iri: str) -> float:
        return self.lines.get(iri, float("inf"))


@dataclass
class LoadedOntology:
    graph: Graph
    path: Path
    meta: dict
    document: DocumentInfo


class _Positions(xml.sax.ContentHandler):
    def __init__(self, info: DocumentInfo):
        super().__init__()
        self.info, self.depth, self.locator, self.bases = info, 0, None, [None]

    def setDocumentLocator(self, locator):
        self.locator = locator

    def startElementNS(self, name, qname, attrs):
        base = attrs.get((XML_NS, "base"), self.bases[-1])
        self.bases.append(base)
        if self.depth == 0:
            self.info.base = base
        elif self.depth == 1:   # node elements directly under rdf:RDF
            about = attrs.get((RDF_NS, "about"))
            rid = attrs.get((RDF_NS, "ID"))
            ref = about if about is not None else (f"#{rid}" if rid is not None else None)
            if ref is not None:
                iri = urljoin(base, ref) if base else ref
                self.info.lines.setdefault(iri, self.locator.getLineNumber())
        self.depth += 1

    def endElementNS(self, name, qname):
        self.depth -= 1
        self.bases.pop()


def document_info(path: Path) -> DocumentInfo:
    info = DocumentInfo()
    parser = xml.sax.make_parser()
    parser.setFeature(xml.sax.handler.feature_namespaces, True)
    parser.setFeature(xml.sax.handler.feature_external_ges, False)
    parser.setFeature(xml.sax.handler.feature_external_pes, False)
    parser.setContentHandler(_Positions(info))
    parser.parse(str(path))
    return info


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path) -> LoadedOntology:
    """Parse the RDF/XML file with RDFLib. Read-only; called afresh for every request."""
    path = Path(path)
    stat = path.stat()
    graph = Graph(bind_namespaces="none")   # only the prefixes declared in the file
    started = time.time()
    graph.parse(str(path), format="xml")
    meta = {"file": path.name, "path": str(path), "sha256": sha256(path), "size": stat.st_size,
            "mtime": stat.st_mtime, "loaded_at": started, "triples": len(graph),
            "parser": f"rdflib {rdflib.__version__}"}
    return LoadedOntology(graph=graph, path=path, meta=meta, document=document_info(path))
