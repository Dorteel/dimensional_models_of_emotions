"""Tests for the SPARQL query files and the RDFLib query service (gui/sparql, gui/ontology_service).

SPARQL results are compared with two independent readings of the same file (see independent.py):
RDFLib's triple API without SPARQL, and ElementTree on the raw XML.
"""

import hashlib
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

GUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GUI))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rdflib import Graph, Literal, URIRef  # noqa: E402
from rdflib.plugins.sparql import prepareQuery  # noqa: E402

import independent as ind  # noqa: E402
from ontology_service import (QueryLibrary, UnknownQuery, build_domains, build_explorer_model,  # noqa: E402
                              find_ontologies, load)
from server import DOMAIN_SOURCE, resolve_owl_dir  # noqa: E402

OWL_DIR = resolve_owl_dir()
OWL_FILES = find_ontologies(OWL_DIR)
POPULATED = OWL_DIR / DOMAIN_SOURCE
SPARQL = GUI / "sparql"
LIB = QueryLibrary()
REQUIRED = ["domains/domains", "domains/quality_dimensions", "domains/prototypes", "domains/prototype_classes",
            "domains/coordinates", "domains/definitions", "domains/notes", "domains/provenance", "explorer/statements"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class QueryFiles(unittest.TestCase):
    def test_required_queries_exist_as_rq_files(self):
        for name in REQUIRED:
            self.assertTrue((SPARQL / f"{name}.rq").is_file(), name)
        self.assertEqual(sorted(LIB.names()), sorted(p.relative_to(SPARQL).with_suffix("").as_posix()
                                                     for p in SPARQL.rglob("*.rq")))

    def test_queries_are_documented_and_declare_their_prefixes(self):
        for path in SPARQL.rglob("*.rq"):
            with self.subTest(query=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("#"), "starts with a comment describing the query")
                self.assertIn("Columns", text)
                body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
                declared = set(re.findall(r"^PREFIX\s+(\w*):", body, re.M))
                code = re.sub(r"<[^>]*>|\"[^\"]*\"", "", body)            # drop IRIs and strings
                used = set(re.findall(r"(?<![\w?$])([A-Za-z]\w*):[A-Za-z_]", code))
                self.assertLessEqual(used, declared, f"undeclared prefixes {used - declared}")
                projected = re.findall(r"\?(\w+)", body.split("WHERE")[0])
                for var in projected:
                    self.assertIn(f"?{var}", text.split("PREFIX")[0], f"?{var} is not documented in the header")
                prepareQuery(text)

    def test_only_named_queries_can_run(self):
        g = Graph()
        with self.assertRaises(UnknownQuery):
            LIB.run("SELECT ?s WHERE { ?s ?p ?o }", g)
        with self.assertRaises(UnknownQuery):
            LIB.run("../server", g)

    def test_no_sparql_text_outside_rq_files(self):
        pattern = re.compile(r"\bSELECT\b[^\n]*\bWHERE\b|\bPREFIX\s+\w*:\s*<", re.I)
        for f in list((GUI / "ontology_service").rglob("*.py")) + [GUI / "server.py"] + list((GUI / "web").rglob("*.js")):
            with self.subTest(file=f.name):
                self.assertIsNone(pattern.search(f.read_text(encoding="utf-8")), f"SPARQL text in {f}")


class Explorer(unittest.TestCase):
    """explorer/statements and the Emotional Ontology tab model, for every ontology file."""

    def test_statements_equal_raw_file(self):
        for path in OWL_FILES:
            with self.subTest(file=path.name):
                _, rows = LIB.run("explorer/statements", load(path).graph)
                got = set()
                for r in rows:
                    o = r["o"]
                    obj = ("lit", str(o), str(o.datatype) if o.datatype else None, o.language) \
                        if isinstance(o, Literal) else ("iri", str(o))
                    got.add((str(r["s"]), str(r["p"]), obj))
                self.assertEqual(got, ind.et_triples(path))

    def test_entities_edges_literals_match_file(self):
        for path in OWL_FILES:
            with self.subTest(file=path.name):
                m = build_explorer_model(load(path), LIB)
                triples = ind.et_triples(path)
                typed = lambda t: {s for s, p, o in triples if p == ind.RDF_NS + "type" and o == ("iri", t)}  # noqa: E731
                owl = "http://www.w3.org/2002/07/owl#"
                ents = m["entities"]
                self.assertEqual({k for k, e in ents.items() if e["kind"] == "class" and e["declared"]}, typed(owl + "Class"))
                self.assertEqual({k for k, e in ents.items() if e["kind"] == "individual"}, typed(owl + "NamedIndividual"))
                self.assertEqual({k for k, e in ents.items() if e["kind"] == "property"},
                                 typed(owl + "ObjectProperty") | typed(owl + "DatatypeProperty") | typed(owl + "AnnotationProperty"))
                edge = {(e["source"], e["predicate"], e["target"]) for e in m["edges"] if e["kind"] != "domain_range"}
                for s, p, o in triples:
                    if o[0] == "iri" and p not in (ind.RDFS_NS + "domain", ind.RDFS_NS + "range") \
                            and not (p == ind.RDF_NS + "type" and o[1].startswith(owl)):
                        self.assertIn((s, p, o[1]), edge)
                literals = sum(len(e["literals"]) + len(e["labels"]) + len(e["comments"]) for e in ents.values())
                self.assertEqual(literals, sum(1 for t in triples if t[2][0] == "lit"))
                self.assertEqual(m["stats"]["triples"], len(triples))
                self.assertEqual(m["meta"]["queries"], ["explorer/statements"])

    def test_every_declared_class_in_hierarchy(self):
        for path in OWL_FILES:
            with self.subTest(file=path.name):
                m = build_explorer_model(load(path), LIB)
                seen = set()

                def walk(node):
                    seen.add(node["id"])
                    for c in node["children"]:
                        walk(c)
                walk(m["hierarchy"])
                declared = {k for k, e in m["entities"].items() if e["kind"] == "class" and e["declared"]}
                self.assertLessEqual(declared, seen)

    def test_defined_at_lines_point_to_the_declaration(self):
        for path in OWL_FILES:
            with self.subTest(file=path.name):
                lines = path.read_text(encoding="utf-8").splitlines()
                m = build_explorer_model(load(path), LIB)
                for e in m["entities"].values():
                    if e["declared"] and e["iri"]:
                        local = e["iri"].split("#")[-1]
                        self.assertRegex(lines[e["line"] - 1], rf'rdf:about="[^"]*{re.escape(local)}"', e["iri"])


class Domains(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = {p: sha(p) for p in OWL_FILES}
        cls.loaded = load(POPULATED)
        cls.data = build_domains(cls.loaded, LIB)
        cls.by_id = {d["id"]: d for d in cls.data["domains"]}
        # Independent graph (parsed separately) inspected with the triple API.
        g = Graph()
        g.parse(str(POPULATED), format="xml")
        cls.graph = g
        cls.expected = ind.graph_domains(g)

    def test_counts_4_domains_36_prototypes_80_coordinates(self):
        ds = self.data["domains"]
        self.assertEqual(len(ds), 4)
        self.assertEqual(sum(len(d["prototypes"]) for d in ds), 36)
        self.assertEqual(sum(v["status"] == "ok" for d in ds for p in d["prototypes"] for v in p["byDim"].values()), 80)
        self.assertEqual(sum(len(p["coordinates"]) for d in ds for p in d["prototypes"]), 80)

    def test_domains_dimensions_prototypes_match_graph(self):
        self.assertEqual(set(self.by_id), set(self.expected))
        for iri, exp in self.expected.items():
            d = self.by_id[iri]
            with self.subTest(domain=d["label"]):
                self.assertEqual([d["label"]], exp["labels"])
                self.assertEqual(sorted(d["notes"]), exp["notes"])
                self.assertEqual({x["id"] for x in d["dimensions"]}, set(exp["dimensions"]))
                for x in d["dimensions"]:
                    e = exp["dimensions"][x["id"]]
                    self.assertEqual([x["label"]], e["labels"])
                    self.assertEqual(sorted(r["raw"] for r in x["ranges"]), e["ranges"])
                    self.assertEqual(sorted(x["circular"]), e["circular"])
                    self.assertEqual(sorted(x["notes"]), e["notes"])
                self.assertEqual({p["id"] for p in d["prototypes"]}, set(exp["prototypes"]))
                for p in d["prototypes"]:
                    self.assertEqual([p["label"]], exp["prototypes"][p["id"]])
                    self.assertEqual(sorted(c["id"] for c in p["emotionClasses"]), exp["classes"][p["id"]])

    def test_coordinates_match_graph_and_raw_file_exactly(self):
        raw = ind.et_domains(POPULATED)
        for iri, d in self.by_id.items():
            for p in d["prototypes"]:
                with self.subTest(prototype=p["name"]):
                    graph_vals = self.expected[iri]["coordinates"][p["id"]]
                    for dim, v in p["byDim"].items():
                        self.assertEqual(v["raw"], raw[iri]["prototypes"][p["id"]][dim])        # lexical form in the XML
                        self.assertEqual([v["raw"]] if v["raw"] is not None else [], graph_vals.get(dim, []))
                        if v["status"] == "ok":
                            self.assertEqual(v["value"], float(v["raw"]))

    def test_order_follows_the_file(self):
        raw = ind.et_domains(POPULATED)
        for iri, d in self.by_id.items():
            with self.subTest(domain=d["label"]):
                self.assertEqual([x["id"] for x in d["dimensions"]], raw[iri]["dimensions"])
                self.assertEqual([p["id"] for p in d["prototypes"]], list(raw[iri]["prototypes"]))

    def test_definitions_and_sources_match_graph(self):
        g = self.graph
        flat = lambda defs: sorted((sorted(t["value"] for t in x["texts"]), sorted(s["label"] for s in x["sources"]))  # noqa: E731
                                   for x in defs)
        for d in self.data["domains"]:
            self.assertEqual(flat(d["description"]), ind.graph_definitions(g, URIRef(d["id"]), ind.ECS.hasDefinition))
            for x in d["dimensions"]:
                self.assertEqual(flat(x["definitions"]), ind.graph_definitions(g, URIRef(x["id"]), ind.ECS.hasDefinition))
            for p in d["prototypes"]:
                self.assertEqual(flat(p["definitions"]), ind.graph_definitions(g, URIRef(p["id"]), ind.ECS.hasDefinition))
                for c in p["emotionClasses"]:
                    self.assertEqual(flat(c["definitions"]),
                                     ind.graph_definitions(g, URIRef(c["id"]), ind.ECS.hasClassDefinition))
                for t in (t for x in p["definitions"] for t in x["texts"]):
                    self.assertEqual(t["placeholder"], t["value"].strip().lower() in ("no known definitions", "undefined"))

    def test_provenance_counts_match_graph(self):
        g = self.graph
        expected = {}
        for s in set(g.subjects(ind.RDF.type, ind.ECS.KnowledgeRepository)) | set(g.objects(None, ind.ECS.hasSource)):
            expected[str(s)] = len(set(g.subjects(ind.ECS.hasSource, s)))
        self.assertEqual({s["id"]: s["definitions"] for s in self.data["sources"]}, expected)

    def test_schema_only_file_has_no_domains(self):
        for path in OWL_FILES:
            if path.name == DOMAIN_SOURCE:
                continue
            with self.subTest(file=path.name):
                self.assertEqual(build_domains(load(path), LIB)["domains"], [])

    def test_reload_reads_the_file_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / POPULATED.name
            shutil.copyfile(POPULATED, copy)
            first = build_domains(load(copy), LIB)
            text = copy.read_text(encoding="utf-8")
            old = re.search(r'(<numericValue[^>]*>)([^<]+)(</numericValue>)', text)
            copy.write_text(text.replace(old.group(0), f"{old.group(1)}12345.678{old.group(3)}", 1), encoding="utf-8")
            second = build_domains(load(copy), LIB)
            raws = lambda data: sorted(v["raw"] or "" for d in data["domains"] for p in d["prototypes"]  # noqa: E731
                                       for v in p["byDim"].values())
            self.assertNotIn("12345.678", raws(first))
            self.assertIn("12345.678", raws(second))

    def test_ontology_files_unchanged(self):
        for p, h in self.before.items():
            self.assertEqual(sha(p), h)


if __name__ == "__main__":
    unittest.main()
