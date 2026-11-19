"""Comparison of two domain models from the populated ontology (Compare Domain Models tab, GET /api/compare).

`compare(a, b, equivalences)` works on two domain objects as produced by `build_domains` (SPARQL queries in
gui/sparql/domains/) and has no other inputs, so it can be reused outside the GUI (e.g. to evaluate an
extracted model against a reference one). `build_comparison` loads the inputs from an ontology file.

Rules (nothing is inferred):
  * Emotions match only by shared emotion class identifier (the class IRI of the prototypes' asserted rdf:type),
    never by label or name similarity. Prototypes without an emotion class are listed but never matched.
  * Two dimensions correspond only when the ontology establishes it: the same dimension individual (identical
    IRI) or an asserted owl:sameAs between them (query compare/dimension_equivalence). Equal or similar labels
    (e.g. "valence" in two models, or PAD pleasure vs circumplex valence) are not used.
  * Numerical differences are computed for a corresponding pair only if its scale is explicitly compatible:
    each dimension states exactly one range in min=…,max=… form, both ranges are equal, neither is stated to be
    circular, and stated measurement levels do not differ. Otherwise the reason is reported instead.
  * Differences are B − A, computed exactly in decimal arithmetic on the lexical values from the file.
    A Euclidean distance is given only when every dimension of both domains has a compatible counterpart.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Context, Decimal, InvalidOperation

from .compare_report import table
from .domains import QUERIES as DOMAIN_QUERIES, build_domains
from .queries import QueryLibrary, term_id
from .store import LoadedOntology

QUERIES = ["compare/dimension_equivalence"]
CIRCULAR_TRUE = ("true", "1", "yes")
DISTANCE_DIGITS = 12

SHARED, ONLY_A, ONLY_B, UNCLASSIFIED_A, UNCLASSIFIED_B = (
    "shared", "only in A", "only in B", "no emotion class (A)", "no emotion class (B)")


def _local(iri: str) -> str:
    return str(iri).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _fmt(d: Decimal) -> str:
    d = d.normalize()
    return "0" if d.is_zero() else format(d, "f")


def dimension_equivalences(loaded: LoadedOntology, library: QueryLibrary) -> set[frozenset]:
    """Unordered pairs of dimension IRIs stated to be the same individual (owl:sameAs, either direction)."""
    _, rows = library.run("compare/dimension_equivalence", loaded.graph)
    return {frozenset((term_id(r["dimension"]), term_id(r["equivalent"]))) for r in rows}


# ------------------------------------------------------------------ dimensions

def _definition_state(defs) -> str:
    texts = [t for d in defs for t in d["texts"]]
    if not texts:
        return "missing"
    return "placeholder" if all(t["placeholder"] for t in texts) else "stated"


def _definition_texts(defs) -> list[dict]:
    return [{"text": t["value"], "placeholder": t["placeholder"], "sources": [s["label"] for s in d["sources"]]}
            for d in defs for t in d["texts"]]


def _range_state(dim) -> tuple[bool, str]:
    """(numeric range stated, explanation)."""
    ranges = dim["ranges"]
    if not ranges:
        return False, "range not stated"
    if len(ranges) > 1:
        return False, f"{len(ranges)} ranges stated ({', '.join(r['raw'] for r in ranges)})"
    r = ranges[0]
    if not r["parsed"]:
        return False, f"range '{r['raw']}' is not in min=…,max=… form"
    if r["min"] is None or r["max"] is None:
        return False, f"range '{r['raw']}' has no numeric min and max"
    if not r["min"] < r["max"]:
        return False, f"range '{r['raw']}' has min ≥ max"
    return True, r["raw"]


def _circular(dim) -> bool | None:
    vals = {str(v).strip().lower() for v in dim["circular"]}
    if not vals:
        return None
    return any(v in CIRCULAR_TRUE for v in vals)


def scale_compatibility(x, y) -> dict:
    """Whether coordinates on dimensions x and y may be subtracted. Both must already correspond."""
    reasons = []
    for side, dim in (("A", x), ("B", y)):
        ok, why = _range_state(dim)
        if not ok:
            reasons.append(f"{side} {dim['label']}: {why}")
    if not reasons and (x["range"]["min"], x["range"]["max"]) != (y["range"]["min"], y["range"]["max"]):
        reasons.append(f"ranges differ ({x['range']['raw']} vs {y['range']['raw']})")
    for side, dim in (("A", x), ("B", y)):
        if _circular(dim):
            reasons.append(f"{side} {dim['label']} is stated to be circular (a linear difference is not meaningful)")
    lx, ly = set(x["measurementLevel"]), set(y["measurementLevel"])
    if lx and ly and lx != ly:
        reasons.append(f"measurement levels differ ({', '.join(sorted(lx))} vs {', '.join(sorted(ly))})")
    return {"compatible": not reasons, "reasons": reasons}


def match_dimensions(a, b, equivalences: set[frozenset]) -> dict:
    def corresponds(x, y):
        return x == y or frozenset((x, y)) in equivalences

    cand_a = {x["id"]: [y["id"] for y in b["dimensions"] if corresponds(x["id"], y["id"])] for x in a["dimensions"]}
    cand_b = {y["id"]: [x["id"] for x in a["dimensions"] if corresponds(x["id"], y["id"])] for y in b["dimensions"]}
    by_a = {x["id"]: x for x in a["dimensions"]}
    by_b = {y["id"]: y for y in b["dimensions"]}
    pairs, ambiguous = [], []
    for x in a["dimensions"]:
        ys = cand_a[x["id"]]
        if len(ys) == 1 and len(cand_b[ys[0]]) == 1:
            y = by_b[ys[0]]
            pairs.append({"a": x["id"], "b": y["id"], "aLabel": x["label"], "bLabel": y["label"],
                          "basis": "same dimension (identical IRI)" if x["id"] == y["id"] else "owl:sameAs",
                          **scale_compatibility(x, y)})
        elif ys:
            ambiguous.append(f"{x['label']} ({_local(x['id'])}) has {len(ys)} stated counterparts in B: "
                             + ", ".join(_local(i) for i in ys))
    for y in b["dimensions"]:
        xs = cand_b[y["id"]]
        if len(xs) > 1:
            ambiguous.append(f"{y['label']} ({_local(y['id'])}) has {len(xs)} stated counterparts in A: "
                             + ", ".join(_local(i) for i in xs))
    paired_a, paired_b = {p["a"] for p in pairs}, {p["b"] for p in pairs}
    unmatched_a = [x for x in by_a if x not in paired_a]
    unmatched_b = [y for y in by_b if y not in paired_b]
    if not pairs:
        status = "none"
    elif not unmatched_a and not unmatched_b:
        status = "full"
    else:
        status = "partial"
    return {"pairs": pairs, "unmatchedA": unmatched_a, "unmatchedB": unmatched_b, "ambiguous": ambiguous,
            "equivalence": status, "numeric": any(p["compatible"] for p in pairs),
            "distance": status == "full" and all(p["compatible"] for p in pairs)}


# ------------------------------------------------------------------ emotions

def _classes(domain):
    """{class id: {"label", "prototypes": [prototype, ...]}} in prototype order; unclassified prototypes."""
    out, unclassified = {}, []
    for p in domain["prototypes"]:
        if not p["emotionClasses"]:
            unclassified.append(p)
        for c in p["emotionClasses"]:
            out.setdefault(c["id"], {"id": c["id"], "label": c["label"], "prototypes": []})["prototypes"].append(p)
    return out, unclassified


def _proto_ref(domain, p):
    return {"id": p["id"], "label": p["label"], "values": [
        {"dimension": d["id"], "raw": p["byDim"][d["id"]]["raw"], "status": p["byDim"][d["id"]]["status"]}
        for d in domain["dimensions"]]}


def _differences(pa, pb, dims):
    diffs, notes, squares = [], [], Decimal(0)
    complete = dims["distance"]
    for pair in dims["pairs"]:
        va, vb = pa["byDim"][pair["a"]], pb["byDim"][pair["b"]]
        if not pair["compatible"]:
            diffs.append({"value": None, "note": "scales not established as compatible"})
            complete = False
            continue
        missing = [f"{side} {lbl}: {v['status']}" for side, lbl, v in
                   (("A", pair["aLabel"], va), ("B", pair["bLabel"], vb)) if v["status"] != "ok"]
        if missing:
            diffs.append({"value": None, "note": "; ".join(missing)})
            notes.extend(missing)
            complete = False
            continue
        try:
            d = Decimal(vb["raw"].strip()) - Decimal(va["raw"].strip())
        except InvalidOperation:   # NUMERIC already guards this; keep the comparison going if it ever differs
            diffs.append({"value": None, "note": "value not decimal"})
            complete = False
            continue
        diffs.append({"value": _fmt(d), "note": ""})
        squares += d * d
    distance = _fmt(Context(prec=DISTANCE_DIGITS).create_decimal(squares.sqrt(Context(prec=40)))) if complete else None
    return diffs, distance, notes


# ------------------------------------------------------------------ summary + warnings

def _domain_summary(domain):
    classes, unclassified = _classes(domain)
    plotted = sum(all(v["status"] == "ok" for v in p["byDim"].values()) for p in domain["prototypes"])
    return {
        "id": domain["id"], "label": domain["label"], "name": domain["name"], "modelTypes": domain["modelTypes"],
        "description": _definition_texts(domain["description"]),
        "dimensions": [{"id": d["id"], "label": d["label"], "name": d["name"],
                        "range": d["range"]["raw"] if d["range"] else None,
                        "rangeState": _range_state(d)[1], "rangeStated": _range_state(d)[0],
                        "min": d["range"]["min"] if d["range"] else None, "max": d["range"]["max"] if d["range"] else None,
                        "circular": d["circular"], "measurementLevel": d["measurementLevel"],
                        "definitionState": _definition_state(d["definitions"]),
                        "definitions": _definition_texts(d["definitions"])} for d in domain["dimensions"]],
        "prototypes": len(domain["prototypes"]), "plotted": plotted,
        "emotionClasses": len(classes), "unclassified": len(unclassified),
    }


def _domain_warnings(side, domain):
    w = []
    add = lambda text, subject=None: w.append({"scope": side, "subject": subject, "text": text})  # noqa: E731
    name = domain["label"]
    if _definition_state(domain["description"]) != "stated":
        add(f"{name}: description not stated in the ontology"
            + (" (placeholder only)" if _definition_state(domain["description"]) == "placeholder" else ""), domain["id"])
    if not domain["dimensions"]:
        add(f"{name}: no quality dimensions", domain["id"])
    if not domain["prototypes"]:
        add(f"{name}: no prototypical instances are linked to this domain (nothing to plot or match)", domain["id"])
    for d in domain["dimensions"]:
        ok, why = _range_state(d)
        if not ok:
            add(f"{name} / {d['label']}: {why}", d["id"])
        state = _definition_state(d["definitions"])
        if state != "stated":
            add(f"{name} / {d['label']}: definition " + ("not stated" if state == "missing" else "is a placeholder only"),
                d["id"])
    for p in domain["prototypes"]:
        if not p["emotionClasses"]:
            add(f"{name} / {p['label']}: no emotion class (cannot be matched)", p["id"])
        for d in domain["dimensions"]:
            v = p["byDim"][d["id"]]
            if v["status"] != "ok":
                add(f"{name} / {p['label']}: coordinate on {d['label']} {v['status']}"
                    + (f" ({v['raw']})" if v["raw"] is not None else ""), p["id"])
        for issue in p["issues"]:
            if not issue.startswith(("value '",)) and " values on " not in issue:
                add(f"{name} / {p['label']}: {issue}", p["id"])
    for issue in domain["issues"]:
        add(f"{name}: {issue}", domain["id"])
    return w


def compare(a: dict, b: dict, equivalences: set[frozenset] = frozenset()) -> dict:
    """Compare two domain objects (build_domains format). `equivalences`: stated owl:sameAs dimension pairs."""
    dims = match_dimensions(a, b, equivalences)
    classes_a, unclassified_a = _classes(a)
    classes_b, unclassified_b = _classes(b)
    shared = [c for c in classes_a if c in classes_b]
    only_a = [c for c in classes_a if c not in classes_b]
    only_b = [c for c in classes_b if c not in classes_a]

    rows = []
    for cid in shared:
        for pa in classes_a[cid]["prototypes"]:
            for pb in classes_b[cid]["prototypes"]:
                diffs, distance, notes = _differences(pa, pb, dims)
                rows.append({"status": SHARED, "class": {"id": cid, "label": classes_a[cid]["label"]},
                             "a": _proto_ref(a, pa), "b": _proto_ref(b, pb), "differences": diffs,
                             "distance": distance, "notes": notes})
    for status, ids, classes, side, domain in ((ONLY_A, only_a, classes_a, "a", a), (ONLY_B, only_b, classes_b, "b", b)):
        for cid in ids:
            for p in classes[cid]["prototypes"]:
                rows.append({"status": status, "class": {"id": cid, "label": classes[cid]["label"]},
                             "a": None, "b": None, side: _proto_ref(domain, p), "differences": [], "distance": None,
                             "notes": []})
    for status, protos, side, domain in ((UNCLASSIFIED_A, unclassified_a, "a", a), (UNCLASSIFIED_B, unclassified_b, "b", b)):
        for p in protos:
            rows.append({"status": status, "class": None, "a": None, "b": None, side: _proto_ref(domain, p),
                         "differences": [], "distance": None, "notes": ["no emotion class: not matched"]})

    links = defaultdict(set)   # "a:<prototype>" -> {"b:<prototype>"} and back (for linked selection)
    for r in rows:
        if r["status"] == SHARED:
            links[f"a:{r['a']['id']}"].add(f"b:{r['b']['id']}")
            links[f"b:{r['b']['id']}"].add(f"a:{r['a']['id']}")

    same = a["id"] == b["id"]
    warnings = _domain_warnings("A", a) + ([] if same else _domain_warnings("B", b))
    cw = lambda text: warnings.append({"scope": "comparison", "subject": None, "text": text})  # noqa: E731
    if same:
        cw("The same domain is selected as A and B: every prototype is compared with itself.")
    if dims["equivalence"] == "none":
        cw("No dimension correspondence is established in the ontology (same dimension or owl:sameAs): "
           "structural comparison only, no numerical differences.")
    for p in dims["pairs"]:
        if not p["compatible"]:
            cw(f"{p['aLabel']} ↔ {p['bLabel']}: no numerical differences: " + "; ".join(p["reasons"]))
    if dims["equivalence"] == "partial":
        cw("Dimensions without a counterpart: "
           + ", ".join([f"A {_dim_label(a, x)}" for x in dims["unmatchedA"]] + [f"B {_dim_label(b, y)}" for y in dims["unmatchedB"]])
           + " (no distance is computed).")
    for text in dims["ambiguous"]:
        cw(f"Ambiguous dimension correspondence, not used: {text}")

    return {
        "sameDomain": same,
        "a": _domain_summary(a), "b": _domain_summary(b),
        "dimensions": dims,
        "emotions": {"shared": [{"id": c, "label": classes_a[c]["label"], "a": [p["id"] for p in classes_a[c]["prototypes"]],
                                 "b": [p["id"] for p in classes_b[c]["prototypes"]]} for c in shared],
                     "onlyA": [{"id": c, "label": classes_a[c]["label"]} for c in only_a],
                     "onlyB": [{"id": c, "label": classes_b[c]["label"]} for c in only_b],
                     "unclassifiedA": [p["id"] for p in unclassified_a],
                     "unclassifiedB": [p["id"] for p in unclassified_b]},
        "rows": rows,
        "links": {k: sorted(v) for k, v in links.items()},
        "warnings": warnings,
    }


def _dim_label(domain, dim_id):
    return next(d["label"] for d in domain["dimensions"] if d["id"] == dim_id)


def _cited_sources(domain):
    defs = [*domain["description"], *(x for d in domain["dimensions"] for x in d["definitions"]),
            *(x for p in domain["prototypes"] for x in p["definitions"]),
            *(x for p in domain["prototypes"] for c in p["emotionClasses"] for x in c["definitions"])]
    seen = {}
    for d in defs:
        for s in d["sources"]:
            seen.setdefault(s["id"], s["label"])
    return [{"id": k, "label": v} for k, v in seen.items()]


class UnknownDomain(KeyError):
    pass


def build_comparison(loaded: LoadedOntology, library: QueryLibrary, a_id: str, b_id: str) -> dict:
    """GET /api/compare: both domains (for plotting, as in /api/domains), the comparison and its provenance."""
    data = build_domains(loaded, library)
    by_id = {d["id"]: d for d in data["domains"]}
    for key in (a_id, b_id):
        if key not in by_id:
            raise UnknownDomain(key)
    a, b = by_id[a_id], by_id[b_id]
    result = compare(a, b, dimension_equivalences(loaded, library))
    meta = data["meta"]
    result["provenance"] = {
        "file": meta["file"], "sha256": meta["sha256"], "parser": meta["parser"], "triples": meta["triples"],
        "base": meta["base"], "queries": [*DOMAIN_QUERIES, *QUERIES],
        "sourcesA": _cited_sources(a), "sourcesB": _cited_sources(b),
        "rules": [
            "Emotions are matched only by shared emotion class IRI (asserted rdf:type of the prototypes).",
            "Dimensions correspond only if they are the same individual or owl:sameAs is asserted between them.",
            "Differences (B − A) only for corresponding dimensions with equal stated min=…,max=… ranges, "
            "not circular and without differing measurement levels; computed exactly on the file's lexical values.",
            "A Euclidean distance only when every dimension of both domains has such a counterpart.",
        ],
    }
    header, rows = table(result)   # the same table as the CSV / Markdown / HTML exports, row i = result["rows"][i]
    result["table"] = {"header": header, "rows": rows}
    return {"meta": {**meta, "queries": result["provenance"]["queries"]}, "domains": {"a": a, "b": b},
            "comparison": result}


__all__ = ["QUERIES", "UnknownDomain", "build_comparison", "compare", "dimension_equivalences",
           "match_dimensions", "scale_compatibility"]
