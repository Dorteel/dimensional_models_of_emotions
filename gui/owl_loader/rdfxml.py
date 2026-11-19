"""Minimal RDF/XML reader (standard library only).

Turns an RDF/XML file into a list of triples. Supports the constructs that
RDF/XML serialisers such as Owlready2 emit:

  * node elements with rdf:about / rdf:ID / rdf:nodeID or none (blank node),
    typed node elements (implicit rdf:type) and rdf:Description;
  * property elements with rdf:resource, rdf:nodeID, rdf:datatype, xml:lang,
    plain text, a nested node element, or rdf:parseType="Resource";
  * property attributes on node elements;
  * xml:base and relative IRIs.

Constructs outside this subset (rdf:parseType="Literal"/"Collection", rdf:li,
reification with rdf:ID on property elements) are not guessed at: they are
reported in `warnings` and skipped, so a caller can show the user what was not
read.
"""

from __future__ import annotations

import xml.sax
from dataclasses import dataclass, field
from urllib.parse import urljoin

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
XML = "http://www.w3.org/XML/1998/namespace"


@dataclass(frozen=True)
class IRI:
    value: str


@dataclass(frozen=True)
class BNode:
    value: str


@dataclass(frozen=True)
class Literal:
    value: str
    datatype: str | None = None
    lang: str | None = None


@dataclass(frozen=True)
class Triple:
    s: IRI | BNode
    p: IRI
    o: IRI | BNode | Literal
    line: int


@dataclass
class ParseResult:
    triples: list = field(default_factory=list)
    prefixes: dict = field(default_factory=dict)   # prefix -> namespace IRI ("" = default namespace)
    base: str | None = None
    warnings: list = field(default_factory=list)


class _Frame:
    """One open XML element: either a node element or a property element."""

    def __init__(self, kind, subject=None, predicate=None, base=None, lang=None, line=0):
        self.kind = kind            # "root" | "node" | "property"
        self.subject = subject      # node: the node's term; property: the parent node's term
        self.predicate = predicate  # property only
        self.base = base
        self.lang = lang
        self.line = line
        self.text = []
        self.datatype = None
        self.has_object = False     # property already produced an object (resource / nested node)
        self.parse_type = None
        self.skip = False


class _Handler(xml.sax.ContentHandler):
    def __init__(self, result: ParseResult, document_base: str | None):
        super().__init__()
        self.r = result
        self.stack: list[_Frame] = []
        self.locator = None
        self.bnodes = 0
        self.document_base = document_base

    # ---------------------------------------------------------------- helpers
    def setDocumentLocator(self, locator):
        self.locator = locator

    def line(self):
        return self.locator.getLineNumber() if self.locator else 0

    def startPrefixMapping(self, prefix, uri):
        self.r.prefixes.setdefault(prefix or "", uri)

    def new_bnode(self, label=None):
        self.bnodes += 1
        return BNode(label or f"_b{self.bnodes}")

    def resolve(self, ref, base):
        return IRI(urljoin(base or "", ref)) if base else IRI(ref)

    def warn(self, message):
        self.r.warnings.append({"line": self.line(), "message": message})

    def emit(self, s, p, o, line=None):
        self.r.triples.append(Triple(s, p, o, line or self.line()))

    @staticmethod
    def name_iri(name):
        uri, local = name
        return IRI((uri or "") + local)

    # ---------------------------------------------------------------- SAX events
    def startElementNS(self, name, qname, attrs):
        parent = self.stack[-1] if self.stack else None
        base = attrs.get((XML, "base"), parent.base if parent else self.document_base)
        if not self.stack and attrs.get((XML, "base")):
            self.r.base = attrs.get((XML, "base"))
        lang = attrs.get((XML, "lang"), parent.lang if parent else None)

        if parent is not None and parent.skip:
            frame = _Frame("skipped", base=base, lang=lang, line=self.line())
            frame.skip = True
            self.stack.append(frame)
            return

        if parent is None:  # document element
            if name == (RDF, "RDF"):
                self.stack.append(_Frame("root", base=base, lang=lang, line=self.line()))
                return
            # A document without rdf:RDF is a single node element.
            parent = _Frame("root", base=base, lang=lang)

        if parent.kind in ("root", "property"):
            self._start_node(name, attrs, parent, base, lang)
        else:
            self._start_property(name, attrs, parent, base, lang)

    def _start_node(self, name, attrs, parent, base, lang):
        about = attrs.get((RDF, "about"))
        rid = attrs.get((RDF, "ID"))
        node_id = attrs.get((RDF, "nodeID"))
        if about is not None:
            subject = self.resolve(about, base)
        elif rid is not None:
            subject = self.resolve("#" + rid, base)
        elif node_id is not None:
            subject = BNode(node_id)
        else:
            subject = self.new_bnode()
        line = self.line()
        if name != (RDF, "Description"):
            self.emit(subject, IRI(RDF + "type"), self.name_iri(name), line)
        for (uri, local), value in attrs.items():
            if uri in (RDF, XML) or (uri is None and local in ("about", "ID", "nodeID")):
                if uri == RDF and local not in ("about", "ID", "nodeID"):
                    if local == "type":
                        self.emit(subject, IRI(RDF + "type"), self.resolve(value, base), line)
                    else:
                        self.warn(f"Unsupported attribute rdf:{local} on node element skipped")
                continue
            self.emit(subject, IRI((uri or "") + local), Literal(value, None, lang), line)
        if parent.kind == "property":
            if parent.has_object:
                self.warn("Property element with more than one object; extra object skipped")
            else:
                self.emit(parent.subject, parent.predicate, subject, parent.line)
                parent.has_object = True
        self.stack.append(_Frame("node", subject=subject, base=base, lang=lang, line=line))

    def _start_property(self, name, attrs, parent, base, lang):
        frame = _Frame("property", subject=parent.subject, predicate=self.name_iri(name),
                       base=base, lang=lang, line=self.line())
        if name == (RDF, "li"):
            self.warn("rdf:li container membership is not supported; element skipped")
            frame.skip = True
            self.stack.append(frame)
            return
        if attrs.get((RDF, "ID")) is not None:
            self.warn("Reification (rdf:ID on a property element) is not supported; statement kept, "
                      "reification skipped")
        parse_type = attrs.get((RDF, "parseType"))
        resource = attrs.get((RDF, "resource"))
        node_id = attrs.get((RDF, "nodeID"))
        frame.datatype = attrs.get((RDF, "datatype"))
        if parse_type == "Resource":
            bnode = self.new_bnode()
            self.emit(parent.subject, frame.predicate, bnode, frame.line)
            frame.has_object = True
            self.stack.append(frame)
            # Children are property elements of the new blank node.
            self.stack.append(_Frame("node", subject=bnode, base=base, lang=lang, line=frame.line))
            self.stack[-1].parse_type = "Resource-inner"
            return
        if parse_type is not None:
            self.warn(f'rdf:parseType="{parse_type}" is not supported; property {frame.predicate.value} skipped')
            frame.skip = True
            self.stack.append(frame)
            return
        other = {(u, l): v for (u, l), v in attrs.items()
                 if u not in (RDF, XML) and not (u is None and l in ("about", "ID", "nodeID"))}
        if resource is not None or node_id is not None or other:
            obj = (self.resolve(resource, base) if resource is not None
                   else BNode(node_id) if node_id is not None else self.new_bnode())
            self.emit(parent.subject, frame.predicate, obj, frame.line)
            for (u, l), v in other.items():  # property attributes on an empty property element
                self.emit(obj, IRI((u or "") + l), Literal(v, None, lang), frame.line)
            frame.has_object = True
        self.stack.append(frame)

    def characters(self, content):
        if self.stack and self.stack[-1].kind == "property" and not self.stack[-1].skip:
            self.stack[-1].text.append(content)

    def endElementNS(self, name, qname):
        frame = self.stack.pop()
        if frame.parse_type == "Resource-inner":
            # Close the synthetic node frame and its property frame together.
            frame = self.stack.pop()
            return
        if frame.kind != "property" or frame.skip or frame.has_object:
            return
        text = "".join(frame.text)
        lang = None if frame.datatype else frame.lang
        self.emit(frame.subject, frame.predicate, Literal(text, frame.datatype, lang), frame.line)


def parse_rdfxml(path, document_base: str | None = None) -> ParseResult:
    result = ParseResult()
    parser = xml.sax.make_parser()
    parser.setFeature(xml.sax.handler.feature_namespaces, True)
    parser.setFeature(xml.sax.handler.feature_namespace_prefixes, False)
    # Never fetch external entities or DTDs.
    parser.setFeature(xml.sax.handler.feature_external_ges, False)
    parser.setFeature(xml.sax.handler.feature_external_pes, False)
    parser.setContentHandler(_Handler(result, document_base))
    parser.parse(str(path))
    return result
