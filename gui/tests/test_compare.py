"""Tests for the domain comparison (ontology_service.compare, compare_report, GET /api/compare).

* Real data (ontology/emotional_ontology_populated.owl): two different domains, the same domain twice, domains
  without prototypes, different numbers of dimensions, missing ranges and placeholder definitions, and
  dimensions with equal labels that must not be equated. Expected values come from independent readings of the
  file (RDFLib triple API / ElementTree in independent.py), not from the comparison code.
* A synthetic ontology written to a temporary folder covers what the real file does not contain: owl:sameAs
  between dimensions, unequal ranges, circular dimensions, measurement levels, partial and ambiguous
  correspondence, several prototypes per class, prototypes without a class, missing and non-numeric values.
* Exports: the CSV, Markdown and HTML contain exactly the comparison table, identifiers and warnings.
"""

import csv
import hashlib
import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

GUI = Path(__file__).resolve().parents[1]
REPO = GUI.parent
sys.path.insert(0, str(GUI))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import independent as ind  # noqa: E402
from ontology_service import QueryLibrary, build_domains, load  # noqa: E402  (load first: keeps lexical forms)
from ontology_service import compare_report as report  # noqa: E402
from ontology_service.compare import (UnknownDomain, build_comparison, compare,  # noqa: E402
                                      dimension_equivalences)
from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, URIRef  # noqa: E402
from rdflib import Namespace  # noqa: E402
import server  # noqa: E402

ECS = Namespace("http://example.org/conceptual-space-emotion.owl#")
POPULATED = server.resolve_owl_dir() / server.DOMAIN_SOURCE
LIB = QueryLibrary()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_hashes(folder):
    return {str(p.relative_to(folder)): sha(p) for p in sorted(Path(folder).rglob("*")) if p.is_file()}


# ------------------------------------------------------------------ synthetic ontology

class Fixture:
    """Builds a small populated ontology with rdflib and writes it as RDF/XML."""

    def __init__(self):
        self.g = Graph()
        self.g.bind("ecs", ECS)
        self.n = 0

    def domain(self, name):
        d = ECS[name]
        self.g.add((d, RDF.type, ECS.Domain))
        self.g.add((d, RDFS.label, Literal(name)))
        return d

    def dim(self, domain, name, rng=None, circular=None, level=None, definition=None, same_as=None):
        x = ECS[name]
        self.g.add((x, RDF.type, ECS.QualityDimension))
        self.g.add((x, RDFS.label, Literal(name.split("_")[-1])))
        self.g.add((domain, ECS.hasQualityDimension, x))
        for prop, value in ((ECS.hasRange, rng), (ECS.isCircular, circular), (ECS.hasMeasurementLevel, level)):
            if value is not None:
                self.g.add((x, prop, Literal(value, datatype=XSD.string)))
        if definition:
            d = ECS[f"def_{name}"]
            self.g.add((x, ECS.hasDefinition, d))
            self.g.add((d, ECS.hasValue, Literal(definition)))
            self.g.add((d, ECS.hasSource, ECS.src_fixture))
            self.g.add((ECS.src_fixture, RDFS.label, Literal("Fixture source")))
        if same_as is not None:
            self.g.add((x, OWL.sameAs, same_as))
        return x

    def proto(self, domain, name, cls, values):
        """values: {dimension: lexical string | None (no coordinate)}."""
        p, pt = ECS[name], ECS[f"point_{name}"]
        self.g.add((p, RDF.type, ECS.PrototypicalInstance))
        if cls:
            self.g.add((p, RDF.type, ECS[cls]))
            self.g.add((ECS[cls], RDFS.label, Literal(cls)))
        self.g.add((p, RDFS.label, Literal(name)))
        self.g.add((domain, ECS.hasDomainPrototype, p))
        self.g.add((p, ECS.belongsToDomain, domain))
        self.g.add((p, ECS.hasPoint, pt))
        for dim, raw in values.items():
            if raw is None:
                continue
            self.n += 1
            c = ECS[f"coord_{name}_{self.n}"]
            self.g.add((pt, ECS.hasCoordinate, c))
            self.g.add((c, ECS.onQualityDimension, dim))
            self.g.add((c, ECS.numericValue, Literal(raw, datatype=XSD.decimal)))
        return p

    def write(self, path):
        self.g.serialize(destination=str(path), format="xml")
        return path


def build_fixture(path):
    f = Fixture()
    # P and Q: full correspondence (owl:sameAs stated once from each side), equal ranges -> differences + distance.
    P, Q = f.domain("dom_p"), f.domain("dom_q")
    px = f.dim(P, "p_x", "min=-1,max=1", definition="x of P")
    py = f.dim(P, "p_y", "min=-1,max=1", definition="y of P")
    qx = f.dim(Q, "q_x", "min=-1,max=1", definition="x of Q", same_as=px)
    qy = f.dim(Q, "q_y", "min=-1,max=1")                      # no definition
    f.g.add((py, OWL.sameAs, qy))                             # stated from the other side
    f.proto(P, "p_joy", "Joy", {px: "0.1", py: "0.3"})
    f.proto(P, "p_sad", "Sadness", {px: "-0.5", py: "-0.5"})
    f.proto(P, "p_fear", "Fear", {px: "0.2", py: None})        # missing coordinate
    f.proto(P, "p_anon", None, {px: "0", py: "0"})             # no emotion class
    f.proto(Q, "q_joy1", "Joy", {qx: "0.4", qy: "-0.1"})       # B - A = 0.3, -0.4; distance 0.5
    f.proto(Q, "q_joy2", "Joy", {qx: "0.1", qy: "0.3"})        # identical: 0, 0, distance 0
    f.proto(Q, "q_fear", "Fear", {qx: "0.5", qy: "0.5"})
    f.proto(Q, "q_anger", "Anger", {qx: "0.9", qy: "0.9"})
    # R: corresponds to P, but the scales are not compatible in different ways.
    R = f.domain("dom_r")
    f.dim(R, "r_x", "min=0,max=10", same_as=px)                # ranges differ
    f.dim(R, "r_y", "min=-1,max=1", circular="true", same_as=py)   # circular
    f.proto(R, "r_joy", "Joy", {ECS.r_x: "5", ECS.r_y: "0.5"})
    # S: partial correspondence (only s_x), one extra dimension.
    S = f.domain("dom_s")
    f.dim(S, "s_x", "min=-1,max=1", same_as=px)
    f.dim(S, "s_z", "min=-1,max=1")
    f.proto(S, "s_joy", "Joy", {ECS.s_x: "0.6", ECS.s_z: "0"})
    # T: ambiguous (two dimensions stated sameAs p_x), and a level mismatch on p_y.
    T = f.domain("dom_t")
    f.dim(T, "t_x1", "min=-1,max=1", same_as=px)
    f.dim(T, "t_x2", "min=-1,max=1", same_as=px)
    f.dim(T, "t_y", "min=-1,max=1", level="ordinal", same_as=py)
    f.g.add((py, ECS.hasMeasurementLevel, Literal("interval", datatype=XSD.string)))
    # E: no prototypes, one dimension without range or definition.
    E = f.domain("dom_empty")
    f.dim(E, "e_only")
    # U: same labels as P's dimensions ("x", "y") but no stated correspondence.
    U = f.domain("dom_u")
    ux, uy = f.dim(U, "u_x", "min=-1,max=1"), f.dim(U, "u_y", "min=-1,max=1")
    f.proto(U, "u_joy", "Joy", {ux: "0.1", uy: "0.3"})
    return f.write(path)


# ------------------------------------------------------------------ real data

class RealDomains(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = sha(POPULATED)
        cls.domains_before = tree_hashes(REPO / "domains")
        cls.loaded = load(POPULATED)
        cls.data = build_domains(cls.loaded, LIB)
        cls.by_name = {d["name"]: d for d in cls.data["domains"]}
        g = Graph()
        g.parse(str(POPULATED), format="xml")
        cls.graph = ind.graph_domains(g)          # independent: RDFLib triple API, no SPARQL
        cls.raw = ind.et_domains(POPULATED)       # independent: ElementTree on the XML
        cls.same_as = list(g.triples((None, OWL.sameAs, None)))

    def run_compare(self, a, b):
        return build_comparison(self.loaded, LIB, self.by_name[a]["id"], self.by_name[b]["id"])

    def classes(self, name):
        iri = self.by_name[name]["id"]
        return {c for cs in self.graph[iri]["classes"].values() for c in cs}

    def test_two_different_domains_circumplex_vs_pad(self):
        res = self.run_compare("domain_circumplex", "domain_pad")
        c = res["comparison"]
        ca, cb = self.classes("domain_circumplex"), self.classes("domain_pad")
        self.assertEqual({e["id"] for e in c["emotions"]["shared"]}, ca & cb)
        self.assertEqual({e["id"] for e in c["emotions"]["onlyA"]}, ca - cb)
        self.assertEqual({e["id"] for e in c["emotions"]["onlyB"]}, cb - ca)
        self.assertTrue(ca & cb, "the real data has shared emotion classes (bored, relaxed)")
        # No dimension correspondence is stated (no owl:sameAs in the file): structural comparison only.
        self.assertEqual(self.same_as, [])
        self.assertEqual(c["dimensions"]["equivalence"], "none")
        self.assertEqual(c["dimensions"]["pairs"], [])
        self.assertFalse(c["dimensions"]["numeric"] or c["dimensions"]["distance"])
        self.assertTrue(all(not r["differences"] and r["distance"] is None for r in c["rows"]))
        self.assertFalse([h for h in c["table"]["header"] if h.startswith("B − A") or "distance" in h])
        self.assertTrue(any("structural comparison only" in w["text"] for w in c["warnings"]))
        # Different numbers of dimensions, counts and coordinates exactly as in the file.
        self.assertEqual((len(c["a"]["dimensions"]), len(c["b"]["dimensions"])), (2, 3))
        for side, name in (("a", "domain_circumplex"), ("b", "domain_pad")):
            iri = self.by_name[name]["id"]
            self.assertEqual(c[side]["prototypes"], len(self.raw[iri]["prototypes"]))
            self.assertEqual([d["id"] for d in c[side]["dimensions"]], self.raw[iri]["dimensions"])
            for r in c["rows"]:
                if r[side]:
                    self.assertEqual([v["raw"] for v in r[side]["values"]],
                                     [self.raw[iri]["prototypes"][r[side]["id"]][d] for d in self.raw[iri]["dimensions"]])
        # Every prototype appears once: shared pairs (one prototype per class here) + unique ones.
        self.assertEqual(len(c["rows"]), len(ca | cb))
        # Links for highlighting go both ways and only between prototypes of a shared class.
        for r in (r for r in c["rows"] if r["status"] == "shared"):
            self.assertIn(f"b:{r['b']['id']}", c["links"][f"a:{r['a']['id']}"])
            self.assertIn(f"a:{r['a']['id']}", c["links"][f"b:{r['b']['id']}"])
        self.assertEqual(len(c["links"]), 2 * len(ca & cb))
        # Missing ranges (PAD) and placeholder definitions are reported.
        texts = [w["text"] for w in c["warnings"]]
        for d in c["b"]["dimensions"]:
            self.assertIn(f"pad / {d['label']}: range not stated", texts)
        self.assertTrue(any("definition is a placeholder only" in t for t in texts))
        # The domains used for plotting are the /api/domains objects.
        self.assertEqual(res["domains"]["a"], self.by_name["domain_circumplex"])
        self.assertEqual(res["domains"]["b"], self.by_name["domain_pad"])

    def test_equal_labels_are_not_equated(self):
        # circumplex and vector_model both have "valence" and "arousal", as different individuals.
        c = self.run_compare("domain_circumplex", "domain_vector_model")["comparison"]
        self.assertEqual([d["label"] for d in c["a"]["dimensions"]], [d["label"] for d in c["b"]["dimensions"]])
        self.assertEqual(c["dimensions"]["equivalence"], "none")
        # PAD pleasure is never equated with circumplex valence.
        c = self.run_compare("domain_pad", "domain_circumplex")["comparison"]
        self.assertEqual(c["dimensions"]["pairs"], [])

    def test_same_domain_twice(self):
        for name, d in self.by_name.items():
            with self.subTest(domain=name):
                c = self.run_compare(name, name)["comparison"]
                self.assertTrue(c["sameDomain"])
                self.assertEqual(c["dimensions"]["equivalence"], "full" if d["dimensions"] else "none")
                self.assertTrue(all(p["basis"] == "same dimension (identical IRI)" for p in c["dimensions"]["pairs"]))
                self.assertEqual(len(c["rows"]), len(d["prototypes"]))
                self.assertTrue(all(r["status"] == "shared" and r["a"] == r["b"] for r in c["rows"]))
                ranged = all(x["ranges"] and len(x["ranges"]) == 1 for x in d["dimensions"])
                self.assertEqual(c["dimensions"]["distance"], ranged and bool(d["dimensions"]))
                for r in c["rows"]:
                    if ranged:
                        self.assertEqual([x["value"] for x in r["differences"]], ["0"] * len(d["dimensions"]))
                        self.assertEqual(r["distance"], "0")
                    else:
                        self.assertTrue(all(x["value"] is None for x in r["differences"]))
                # Warnings of the domain are listed once, not twice.
                self.assertFalse([w for w in c["warnings"] if w["scope"] == "B"])
        self.assertTrue(self.run_compare("domain_circumplex", "domain_circumplex")["comparison"]["dimensions"]["numeric"])
        self.assertFalse(self.run_compare("domain_pad", "domain_pad")["comparison"]["dimensions"]["numeric"])

    def test_domains_without_prototypes(self):
        c = self.run_compare("domain_plutchik_model", "domain_vector_model")["comparison"]
        self.assertEqual((c["a"]["prototypes"], c["b"]["prototypes"]), (0, 0))
        self.assertEqual((len(c["a"]["dimensions"]), len(c["b"]["dimensions"])), (1, 2))
        self.assertEqual(c["rows"], [])
        self.assertEqual(c["emotions"]["shared"], [])
        texts = [w["text"] for w in c["warnings"]]
        self.assertIn("plutchik_model: no prototypical instances are linked to this domain (nothing to plot or match)", texts)
        self.assertIn("vector_model: no prototypical instances are linked to this domain (nothing to plot or match)", texts)
        c = self.run_compare("domain_circumplex", "domain_plutchik_model")["comparison"]
        self.assertTrue(all(r["status"] == "only in A" for r in c["rows"]))

    def test_unknown_domain(self):
        with self.assertRaises(UnknownDomain):
            build_comparison(self.loaded, LIB, self.by_name["domain_pad"]["id"], "http://example.org/nothing")

    def test_no_files_changed(self):
        for a in self.by_name:
            for b in self.by_name:
                c = self.run_compare(a, b)["comparison"]
                report.to_csv(c), report.to_markdown(c), report.to_html(c)
        self.assertEqual(sha(POPULATED), self.before)
        self.assertEqual(tree_hashes(REPO / "domains"), self.domains_before)


# ------------------------------------------------------------------ synthetic ontology

class SyntheticDomains(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="gui_compare_"))
        cls.path = build_fixture(cls.tmp / "fixture.owl")
        cls.loaded = load(cls.path)
        cls.by_name = {d["id"].rsplit("#", 1)[-1]: d for d in build_domains(cls.loaded, LIB)["domains"]}
        cls.equiv = dimension_equivalences(cls.loaded, LIB)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def cmp(self, a, b):
        return compare(self.by_name[a], self.by_name[b], self.equiv)

    def iri(self, local):
        return str(ECS[local])

    def test_equivalence_query_matches_triples(self):
        g = Graph()
        g.parse(str(self.path), format="xml")
        dims = set(g.objects(None, ECS.hasQualityDimension))
        expected = {frozenset((str(s), str(o))) for s, o in g.subject_objects(OWL.sameAs) if s in dims and o in dims}
        self.assertEqual(self.equiv, expected)
        self.assertEqual(len(expected), 8)

    def test_full_correspondence_differences_and_distance(self):
        c = self.cmp("dom_p", "dom_q")
        dims = c["dimensions"]
        self.assertEqual(dims["equivalence"], "full")
        self.assertEqual({(p["a"], p["b"], p["basis"]) for p in dims["pairs"]},   # order: the file's (document position)
                         {(self.iri("p_x"), self.iri("q_x"), "owl:sameAs"), (self.iri("p_y"), self.iri("q_y"), "owl:sameAs")})
        self.assertTrue(dims["distance"])
        rows = {(r["a"]["label"], r["b"]["label"]): r for r in c["rows"] if r["status"] == "shared"}
        # Several prototypes of one class: every pair is listed.
        self.assertEqual(set(rows), {("p_joy", "q_joy1"), ("p_joy", "q_joy2"), ("p_fear", "q_fear")})
        diff = lambda row: {p["aLabel"]: d["value"] for p, d in zip(dims["pairs"], row["differences"])}  # noqa: E731
        self.assertEqual(diff(rows[("p_joy", "q_joy1")]), {"x": "0.3", "y": "-0.4"})   # exact decimals
        self.assertEqual(rows[("p_joy", "q_joy1")]["distance"], "0.5")
        self.assertEqual(rows[("p_joy", "q_joy2")]["distance"], "0")
        # Missing coordinate: no difference on that dimension and no distance.
        fear = rows[("p_fear", "q_fear")]
        self.assertEqual(diff(fear), {"x": "0.3", "y": None})
        self.assertIsNone(fear["distance"])
        self.assertIn("A y: missing", fear["notes"])
        self.assertEqual(sorted(c["links"][f"a:{self.iri('p_joy')}"]), [f"b:{self.iri('q_joy1')}", f"b:{self.iri('q_joy2')}"])
        # Unique and unclassified prototypes are listed, never matched.
        status = {(r["status"], (r["a"] or r["b"])["label"]) for r in c["rows"] if r["status"] != "shared"}
        self.assertEqual(status, {("only in A", "p_sad"), ("only in B", "q_anger"), ("no emotion class (A)", "p_anon")})
        self.assertNotIn(f"a:{self.iri('p_anon')}", c["links"])
        texts = [w["text"] for w in c["warnings"]]
        self.assertIn("dom_p / p_anon: no emotion class (cannot be matched)", texts)
        self.assertIn("dom_p / p_fear: coordinate on y missing", texts)
        self.assertIn("dom_q / y: definition not stated", texts)

    def test_incompatible_scales_give_no_differences(self):
        c = self.cmp("dom_p", "dom_r")
        pairs = {p["bLabel"]: p for p in c["dimensions"]["pairs"]}
        self.assertEqual(c["dimensions"]["equivalence"], "full")
        self.assertFalse(pairs["x"]["compatible"])
        self.assertIn("ranges differ (min=-1,max=1 vs min=0,max=10)", pairs["x"]["reasons"])
        self.assertFalse(pairs["y"]["compatible"])
        self.assertTrue(any("circular" in r for r in pairs["y"]["reasons"]))
        self.assertFalse(c["dimensions"]["numeric"] or c["dimensions"]["distance"])
        row = next(r for r in c["rows"] if r["status"] == "shared")
        self.assertEqual([d["value"] for d in row["differences"]], [None, None])
        self.assertIsNone(row["distance"])
        header, _ = report.table(c)
        self.assertFalse([h for h in header if h.startswith("B − A")])

    def test_missing_range_and_measurement_level(self):
        c = self.cmp("dom_p", "dom_t")
        self.assertEqual(c["dimensions"]["ambiguous"][0][:2], "x ")       # p_x has two stated counterparts
        self.assertEqual([p["bLabel"] for p in c["dimensions"]["pairs"]], ["y"])
        self.assertIn("measurement levels differ (interval vs ordinal)", c["dimensions"]["pairs"][0]["reasons"])
        self.assertTrue(any(w["text"].startswith("Ambiguous dimension correspondence") for w in c["warnings"]))
        c = self.cmp("dom_empty", "dom_p")
        self.assertEqual(c["dimensions"]["equivalence"], "none")
        texts = [w["text"] for w in c["warnings"]]
        self.assertIn("dom_empty / only: range not stated", texts)
        self.assertIn("dom_empty / only: definition not stated", texts)
        self.assertIn("dom_empty: description not stated in the ontology", texts)

    def test_partial_correspondence(self):
        c = self.cmp("dom_p", "dom_s")
        self.assertEqual(c["dimensions"]["equivalence"], "partial")
        self.assertTrue(c["dimensions"]["numeric"])
        self.assertFalse(c["dimensions"]["distance"])
        row = next(r for r in c["rows"] if r["status"] == "shared")
        self.assertEqual([d["value"] for d in row["differences"]], ["0.5"])
        self.assertIsNone(row["distance"])
        self.assertEqual(c["dimensions"]["unmatchedA"], [self.iri("p_y")])
        self.assertEqual(c["dimensions"]["unmatchedB"], [self.iri("s_z")])

    def test_same_labels_without_statement_are_not_equated(self):
        c = self.cmp("dom_p", "dom_u")
        self.assertEqual(sorted(d["label"] for d in c["a"]["dimensions"]), sorted(d["label"] for d in c["b"]["dimensions"]))
        self.assertEqual(c["dimensions"]["equivalence"], "none")
        self.assertTrue(all(not r["differences"] for r in c["rows"]))

    def test_differences_are_exact_decimals(self):
        c = self.cmp("dom_p", "dom_q")
        value = lambda ref, dim: next(v for v in ref["values"] if v["dimension"] == dim)  # noqa: E731
        for r in (r for r in c["rows"] if r["status"] == "shared"):
            for pair, d in zip(c["dimensions"]["pairs"], r["differences"]):   # one difference per dimension pair
                va, vb = value(r["a"], pair["a"]), value(r["b"], pair["b"])
                if d["value"] is not None:
                    self.assertEqual(Decimal(d["value"]), Decimal(vb["raw"]) - Decimal(va["raw"]))


# ------------------------------------------------------------------ exports

class _Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.cell, self.external = [], None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if any(str(a.get(k, "")).startswith(("http:", "https:", "//")) for k in ("src", "href")):
            self.external.append(a)
        if tag == "table":
            self.tables.append([])
        elif tag == "tr":
            self.tables[-1].append([])
        elif tag in ("td", "th"):
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.tables[-1][-1].append("".join(self.cell))
            self.cell = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


class Exports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="gui_compare_exports_"))
        cls.loaded = {"real": load(POPULATED), "fixture": load(build_fixture(cls.tmp / "fixture.owl"))}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def cases(self):
        for key, loaded in self.loaded.items():
            ds = {d["id"].rsplit("#", 1)[-1]: d["id"] for d in build_domains(loaded, LIB)["domains"]}
            pairs = ([("domain_circumplex", "domain_pad"), ("domain_circumplex", "domain_circumplex"),
                      ("domain_plutchik_model", "domain_vector_model")] if key == "real" else
                     [("dom_p", "dom_q"), ("dom_p", "dom_r"), ("dom_empty", "dom_p")])
            for a, b in pairs:
                yield f"{a} vs {b}", build_comparison(loaded, LIB, ds[a], ds[b])["comparison"]

    def test_csv_is_the_comparison_table(self):
        for name, c in self.cases():
            with self.subTest(name):
                text = report.to_csv(c)
                meta = [line[2:] for line in text.splitlines() if line.startswith("# ")]
                body = "\n".join(line for line in text.splitlines() if not line.startswith("# "))
                rows = list(csv.reader(io.StringIO(body)))
                self.assertEqual(rows[0], c["table"]["header"])
                self.assertEqual(rows[1:], c["table"]["rows"])
                self.assertEqual(len(rows) - 1, len(c["rows"]))
                # identifiers, axis labels and warnings
                self.assertIn(f"A: {c['a']['id']}", meta)
                self.assertIn(f"B: {c['b']['id']}", meta)
                for side in ("a", "b"):
                    for d in c[side]["dimensions"]:
                        self.assertTrue(any(m.startswith(f"{side.upper()} dimension {d['label']}: {d['id']}") for m in meta))
                for w in c["warnings"]:
                    self.assertIn(f"warning [{w['scope']}]: {w['text']}", meta)
                self.assertTrue(any(c["provenance"]["sha256"] in m for m in meta))
                # Coordinate cells are the file's lexical values, unchanged.
                for r, line in zip(c["rows"], rows[1:]):
                    for side in ("a", "b"):
                        if r[side]:
                            self.assertIn(r[side]["id"], line)
                            for v in r[side]["values"]:
                                if v["status"] == "ok":
                                    self.assertIn(v["raw"], line)

    def test_html_is_self_contained_and_matches(self):
        for name, c in self.cases():
            with self.subTest(name):
                text = report.to_html(c)
                parser = _Tables()
                parser.feed(text)
                self.assertEqual(parser.external, [])
                self.assertIn(report.FIGURES_MARKER, text)
                tables = parser.tables
                if c["rows"]:
                    found = [t for t in tables if t[0] == c["table"]["header"]]
                    self.assertEqual(len(found), 1)
                    self.assertEqual(found[0][1:], c["table"]["rows"])
                models = tables[0]
                self.assertEqual(models[2], ["IRI", c["a"]["id"], c["b"]["id"]])
                for w in c["warnings"]:
                    self.assertIn(report.html.escape(f"[{w['scope']}] {w['text']}"), text)
                for e in c["emotions"]["shared"]:
                    self.assertIn(report.html.escape(e["label"]), text)

    def test_markdown_matches(self):
        for name, c in self.cases():
            with self.subTest(name):
                text = report.to_markdown(c)
                self.assertTrue(text.startswith(f"# Domain model comparison: {c['a']['label']} vs {c['b']['label']}"))
                lines = text.splitlines()
                for r in c["table"]["rows"]:
                    self.assertIn("| " + " | ".join(report._md(x) for x in r) + " |", lines)
                for w in c["warnings"]:
                    self.assertIn(f"- {report._md('[' + w['scope'] + '] ' + w['text'])}", lines)
                for side in ("a", "b"):
                    self.assertIn(c[side]["id"], text)
                    for d in c[side]["dimensions"]:
                        self.assertIn(d["id"], text)
                self.assertIn(c["provenance"]["sha256"], text)


# ------------------------------------------------------------------ HTTP

class CompareEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.make_server(port=0)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.ids = {d["name"]: d["id"] for d in build_domains(load(POPULATED), LIB)["domains"]}

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=60) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def url(self, a, b, fmt=None):
        return f"/api/compare?a={quote(self.ids[a], safe='')}&b={quote(self.ids[b], safe='')}" + (f"&format={fmt}" if fmt else "")

    def test_json_and_exports(self):
        status, _, body = self.get(self.url("domain_circumplex", "domain_pad"))
        self.assertEqual(status, 200)
        data = json.loads(body)
        _, _, domains = self.get("/api/domains")
        by_id = {d["id"]: d for d in json.loads(domains)["domains"]}
        self.assertEqual(data["domains"]["a"], by_id[self.ids["domain_circumplex"]])
        self.assertEqual(data["domains"]["b"], by_id[self.ids["domain_pad"]])
        self.assertIn("compare/dimension_equivalence", data["meta"]["queries"])
        for fmt, mime, ext in (("csv", "text/csv", ".csv"), ("md", "text/markdown", ".md"), ("html", "text/html", ".html")):
            status, headers, text = self.get(self.url("domain_circumplex", "domain_pad", fmt))
            self.assertEqual(status, 200)
            self.assertTrue(headers["Content-Type"].startswith(mime))
            self.assertIn(f'filename="compare_domain_circumplex_vs_domain_pad{ext}"', headers["Content-Disposition"])
            render = {"csv": report.to_csv, "md": report.to_markdown, "html": report.to_html}[fmt]
            self.assertEqual(text.decode("utf-8"), render(data["comparison"]))

    def test_errors(self):
        self.assertEqual(self.get("/api/compare")[0], 400)
        self.assertEqual(self.get(f"/api/compare?a={quote(self.ids['domain_pad'], safe='')}&b=nothing")[0], 404)
        self.assertEqual(self.get(self.url("domain_pad", "domain_pad", "xlsx"))[0], 400)


if __name__ == "__main__":
    unittest.main()
