"""Tests for gui/owl_loader against the real ontology files and small RDF/XML samples.

The real files are cross-checked with an independent ElementTree reading of the same XML.
"""

import hashlib
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

GUI = Path(__file__).resolve().parents[1]
REPO = GUI.parent
sys.path.insert(0, str(GUI))

from owl_loader import find_ontologies, load_ontology  # noqa: E402
from owl_loader.rdfxml import BNode, IRI, Literal, parse_rdfxml  # noqa: E402

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
OWL = "http://www.w3.org/2002/07/owl#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
XMLNS = "{http://www.w3.org/XML/1998/namespace}"
OWL_FILES = find_ontologies(REPO / "owl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def independent_triples(path):
    """Flat RDF/XML (top-level node elements with simple property elements) read with ElementTree."""
    root = ET.parse(path).getroot()
    base = root.get(XMLNS + "base", "")
    full = lambda ref: base + ref if ref.startswith("#") else ref  # noqa: E731
    iri = lambda tag: tag[1:].replace("}", "")  # noqa: E731
    triples = set()
    for node in root:
        about = node.get(f"{{{RDF}}}about")
        assert about is not None, f"unexpected node element without rdf:about: {node.tag}"
        s = full(about)
        if node.tag != f"{{{RDF}}}Description":
            triples.add((s, RDF + "type", ("iri", iri(node.tag))))
        for prop in node:
            assert len(prop) == 0, "nested node elements are outside this independent reader"
            res = prop.get(f"{{{RDF}}}resource")
            if res is not None:
                triples.add((s, iri(prop.tag), ("iri", full(res))))
            else:
                triples.add((s, iri(prop.tag), ("lit", prop.text or "", prop.get(f"{{{RDF}}}datatype"),
                                                prop.get(XMLNS + "lang"))))
    return triples


def loader_triples(path):
    out = set()
    for t in parse_rdfxml(path).triples:
        o = ("iri", t.o.value) if isinstance(t.o, IRI) else ("lit", t.o.value, t.o.datatype, t.o.lang)
        out.add((t.s.value, t.p.value, o))
    return out


class RealOntologyFiles(unittest.TestCase):
    def test_ontology_files_exist(self):
        self.assertTrue(OWL_FILES, "no .owl files in owl/")

    def test_every_triple_read(self):
        for path in OWL_FILES:
            with self.subTest(file=path.name):
                expected = independent_triples(path)
                got = loader_triples(path)
                self.assertEqual(got, expected, f"{len(expected - got)} missing, {len(got - expected)} extra")
                self.assertEqual(parse_rdfxml(path).warnings, [])

    def test_entities_and_edges_match_file(self):
        for path in OWL_FILES:
            with self.subTest(file=path.name):
                m = load_ontology(path)
                triples = independent_triples(path)
                typed = lambda t: {s for s, p, o in triples if p == RDF + "type" and o == ("iri", t)}  # noqa: E731
                classes = {k for k, e in m["entities"].items() if e["kind"] == "class" and e["declared"]}
                individuals = {k for k, e in m["entities"].items() if e["kind"] == "individual"}
                props = {k for k, e in m["entities"].items() if e["kind"] == "property"}
                self.assertEqual(classes, typed(OWL + "Class"))
                self.assertEqual(individuals, typed(OWL + "NamedIndividual"))
                self.assertEqual(props, typed(OWL + "ObjectProperty") | typed(OWL + "DatatypeProperty")
                                 | typed(OWL + "AnnotationProperty"))
                edge = {(e["source"], e["predicate"], e["target"]) for e in m["edges"] if e["kind"] != "domain_range"}
                for s, p, o in triples:
                    if o[0] != "iri" or p in (RDFS + "domain", RDFS + "range"):
                        continue
                    if p == RDF + "type" and (o[1].startswith(OWL)):
                        continue  # declarations, not graph edges
                    self.assertIn((s, p, o[1]), edge)
                literals = sum(len(e["literals"]) + len(e["labels"]) + len(e["comments"]) for e in m["entities"].values())
                self.assertEqual(literals, sum(1 for t in triples if t[2][0] == "lit"))

    def test_every_declared_class_in_hierarchy(self):
        for path in OWL_FILES:
            with self.subTest(file=path.name):
                m = load_ontology(path)
                seen = set()

                def walk(node):
                    seen.add(node["id"])
                    for c in node["children"]:
                        walk(c)
                walk(m["hierarchy"])
                declared = {k for k, e in m["entities"].items() if e["kind"] == "class" and e["declared"]}
                self.assertLessEqual(declared, seen)

    def test_files_are_not_modified(self):
        for path in OWL_FILES:
            before = sha(path)
            load_ontology(path)
            self.assertEqual(sha(path), before)


class RdfXmlSubset(unittest.TestCase):
    def parse(self, body):
        doc = f"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="{RDF}" xmlns:rdfs="{RDFS}" xmlns:owl="{OWL}" xmlns:ex="http://ex.org/#"
         xml:base="http://ex.org/onto">{body}</rdf:RDF>"""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.owl"
            p.write_text(doc, encoding="utf-8")
            return parse_rdfxml(p)

    def test_nested_blank_nodes_lang_and_nodeid(self):
        r = self.parse("""
          <owl:Class rdf:about="#A"><rdfs:label xml:lang="en">An A</rdfs:label>
            <ex:link><rdf:Description rdf:about="#B"><ex:v>1</ex:v></rdf:Description></ex:link>
            <ex:anon rdf:parseType="Resource"><ex:w>2</ex:w></ex:anon>
            <ex:ref rdf:nodeID="n1"/>
          </owl:Class>""")
        t = {(x.s, x.p.value, x.o) for x in r.triples}
        a, b = IRI("http://ex.org/onto#A"), IRI("http://ex.org/onto#B")
        self.assertIn((a, RDF + "type", IRI(OWL + "Class")), t)
        self.assertIn((a, RDFS + "label", Literal("An A", None, "en")), t)
        self.assertIn((a, "http://ex.org/#link", b), t)
        self.assertIn((b, "http://ex.org/#v", Literal("1")), t)
        self.assertIn((a, "http://ex.org/#ref", BNode("n1")), t)
        anon = [x.o for x in r.triples if x.p.value == "http://ex.org/#anon"][0]
        self.assertIn((anon, "http://ex.org/#w", Literal("2")), t)
        self.assertEqual(r.warnings, [])

    def test_unsupported_constructs_are_reported(self):
        r = self.parse("""<owl:Class rdf:about="#A"><ex:list rdf:parseType="Collection">
            <rdf:Description rdf:about="#B"/></ex:list></owl:Class>""")
        self.assertTrue(any("Collection" in w["message"] for w in r.warnings))
        self.assertFalse(any(x.p.value == "http://ex.org/#list" for x in r.triples))


if __name__ == "__main__":
    unittest.main()
