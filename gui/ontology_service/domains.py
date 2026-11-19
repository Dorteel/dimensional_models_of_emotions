"""Domain models for the Domain Models tab, assembled from the SPARQL queries in gui/sparql/domains/.

Every value comes from a query result; this module only groups rows by term and records what is missing
or inconsistent. Nothing is filled in or inferred.

Orders: SPARQL results are unordered. Domains are sorted by label; dimensions, prototypes and other lists
follow the order in which the terms are described in the OWL file (document position), which keeps axis
order identical to the file (e.g. valence before arousal). Ties fall back to the IRI.

Output (GET /api/domains):
  meta       file metadata + the names of the queries that produced the data
  domains    [{id, label, name, modelTypes, notes, description, dimensions, prototypes, issues}]
  sources    provenance: [{id, label, definitions}] (domains/provenance)
"""

from __future__ import annotations

import re
from collections import defaultdict

from .names import Names, graph_prefixes
from .queries import QueryLibrary, term_id
from .store import LoadedOntology

PLACEHOLDER_DEFINITIONS = ("no known definitions", "undefined")
NUMERIC = re.compile(r"^\s*[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?\s*$")
RANGE = re.compile(r"^\s*min\s*=\s*([^,]*),\s*max\s*=\s*(.*)$")

QUERIES = ["domains/domains", "domains/quality_dimensions", "domains/prototypes", "domains/prototype_classes",
           "domains/coordinates", "domains/definitions", "domains/notes", "domains/provenance"]


def is_placeholder(text: str) -> bool:
    return str(text).strip().lower() in PLACEHOLDER_DEFINITIONS


def parse_range(raw: str) -> dict:
    """hasRange is stored as text such as "min=-1,max=1"; anything else is kept raw and not interpreted."""
    m = RANGE.match(raw)
    if not m:
        return {"raw": raw, "min": None, "max": None, "parsed": False}
    num = lambda s: float(s) if NUMERIC.match(s) else None  # noqa: E731
    return {"raw": raw, "min": num(m.group(1)), "max": num(m.group(2)), "parsed": True}


def _s(term):
    return None if term is None else str(term)


def _add(lst, value):
    if value is not None and value not in lst:
        lst.append(value)


def build_domains(loaded: LoadedOntology, library: QueryLibrary) -> dict:
    graph = loaded.graph
    names = Names(graph_prefixes(graph), loaded.document.base)
    pos = loaded.document.position
    doc_order = lambda ids: sorted(ids, key=lambda i: (pos(i), i))  # noqa: E731
    rows = {q: library.run(q, graph)[1] for q in QUERIES}
    local = lambda iri: iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]  # noqa: E731

    # ---------------------------------------------------------------- definitions, notes, provenance
    definitions = defaultdict(dict)   # (subject, property local name) -> {definition id: {...}}
    for r in rows["domains/definitions"]:
        subj, prop, d = term_id(r["subject"]), local(str(r["property"])), term_id(r["definition"])
        entry = definitions[(subj, prop)].setdefault(d, {"id": d, "texts": [], "sources": []})
        if r["text"] is not None:
            t = {"value": str(r["text"]), "datatype": names.short(str(r["text"].datatype)) if r["text"].datatype else None,
                 "lang": _s(r["textLang"]) or None, "placeholder": is_placeholder(r["text"])}
            if t not in entry["texts"]:
                entry["texts"].append(t)
        if r["source"] is not None:
            src = {"id": term_id(r["source"]), "label": _s(r["sourceLabel"]) or names.short(str(r["source"]))}
            if src not in entry["sources"]:
                entry["sources"].append(src)

    def defs_of(subject, prop="hasDefinition"):
        found = definitions.get((subject, prop), {})
        return [found[k] for k in doc_order(found)]

    notes = defaultdict(list)
    for r in rows["domains/notes"]:
        _add(notes[term_id(r["subject"])], str(r["note"]))

    sources = [{"id": term_id(r["source"]), "label": _s(r["label"]) or names.short(str(r["source"])),
                "definitions": int(r["definitions"].toPython())} for r in rows["domains/provenance"]]
    sources.sort(key=lambda s: (s["label"].lower(), s["id"]))

    # ---------------------------------------------------------------- domains
    domain_info = {}
    for r in rows["domains/domains"]:
        d = term_id(r["domain"])
        info = domain_info.setdefault(d, {"labels": [], "modelTypes": []})
        _add(info["labels"], _s(r["label"]))
        _add(info["modelTypes"], _s(r["modelType"]))

    # ---------------------------------------------------------------- dimensions
    dims_of = defaultdict(list)
    dim_info = {}
    for r in rows["domains/quality_dimensions"]:
        d, x = term_id(r["domain"]), term_id(r["dimension"])
        _add(dims_of[d], x)
        info = dim_info.setdefault(x, {"labels": [], "ranges": [], "circular": [], "measurementLevel": []})
        _add(info["labels"], _s(r["label"]))
        _add(info["ranges"], _s(r["range"]))
        _add(info["circular"], _s(r["circular"]))
        _add(info["measurementLevel"], _s(r["measurementLevel"]))

    def dimension(x):
        info = dim_info[x]
        ranges = [parse_range(raw) for raw in info["ranges"]]
        return {"id": x, "label": info["labels"][0] if info["labels"] else names.short(x), "name": names.short(x),
                "ranges": ranges, "range": ranges[0] if len(ranges) == 1 else None,
                "circular": info["circular"], "measurementLevel": info["measurementLevel"],
                "notes": notes.get(x, []), "definitions": defs_of(x)}

    # ---------------------------------------------------------------- prototypes, classes, coordinates
    links = defaultdict(lambda: defaultdict(set))   # domain -> prototype -> {link kinds}
    proto_labels = defaultdict(list)
    for r in rows["domains/prototypes"]:
        d, p = term_id(r["domain"]), term_id(r["prototype"])
        links[d][p].add(str(r["link"]))
        _add(proto_labels[p], _s(r["label"]))
    classes = defaultdict(list)
    for r in rows["domains/prototype_classes"]:
        c = term_id(r["class"])
        entry = {"id": c, "label": _s(r["classLabel"]) or names.short(c)}
        if entry not in [{"id": x["id"], "label": x["label"]} for x in classes[term_id(r["prototype"])]]:
            classes[term_id(r["prototype"])].append({**entry, "definitions": defs_of(c, "hasClassDefinition")})
    coords = defaultdict(dict)   # prototype -> coordinate -> {...}
    for r in rows["domains/coordinates"]:
        p, c = term_id(r["prototype"]), term_id(r["coordinate"])
        entry = coords[p].setdefault(c, {"id": c, "pointId": term_id(r["point"]), "dimensions": [], "raw": [],
                                         "datatype": None})
        _add(entry["dimensions"], None if r["dimension"] is None else term_id(r["dimension"]))
        _add(entry["raw"], _s(r["lexical"]))
        if r["datatype"] is not None:
            entry["datatype"] = names.short(str(r["datatype"]))

    def prototype(p, dim_ids):
        issues = []
        points = doc_order({c["pointId"] for c in coords[p].values()})
        if len(points) > 1:
            issues.append(f"{len(points)} points (hasPoint) are stated for this prototype")
        cs = [coords[p][k] for k in doc_order(coords[p])]
        for c in cs:
            if len(c["raw"]) != 1:
                issues.append(f"{local(c['id'])} has {len(c['raw'])} numericValue statements")
            if len(c["dimensions"]) != 1:
                issues.append(f"{local(c['id'])} has {len(c['dimensions'])} onQualityDimension statements")
            for x in c["dimensions"]:
                if x not in dim_ids:
                    issues.append(f"{local(c['id'])} is on {local(x)}, which is not a dimension of this domain")
        by_dim = {}
        for x in dim_ids:
            found = [(raw, c) for c in cs if x in c["dimensions"] for raw in c["raw"]]
            value, raw, status = None, None, "missing"
            if len(found) == 1 and NUMERIC.match(found[0][0]):
                raw, status = found[0][0], "ok"
                value = float(raw)
            elif len(found) == 1:
                raw, status = found[0][0], "not numeric"
                issues.append(f"value '{raw}' on {local(x)} is not numeric")
            elif len(found) > 1:
                raw, status = " | ".join(f[0] for f in found), "conflicting"
                issues.append(f"{len(found)} values on {local(x)}: {raw}")
            by_dim[x] = {"value": value, "raw": raw, "status": status,
                         "coordinateId": found[0][1]["id"] if found else None}
        return {"id": p, "label": proto_labels[p][0] if proto_labels[p] else names.short(p), "name": names.short(p),
                "emotionClasses": classes.get(p, []), "points": points, "coordinates": cs, "byDim": by_dim,
                "definitions": defs_of(p), "notes": notes.get(p, []), "issues": issues}

    domains = []
    for d, info in domain_info.items():
        dim_ids = doc_order(dims_of.get(d, []))
        protos = doc_order(links.get(d, {}))
        issues = []
        for p in protos:
            kinds = links[d][p]
            if "hasDomainPrototype" not in kinds:
                issues.append(f"{local(p)} states belongsToDomain, but the domain has no hasDomainPrototype to it")
            if "belongsToDomain" not in kinds:
                issues.append(f"{local(p)} is a hasDomainPrototype of the domain, but has no belongsToDomain back")
        domains.append({
            "id": d, "label": info["labels"][0] if info["labels"] else names.short(d), "name": names.short(d),
            "modelTypes": info["modelTypes"], "notes": notes.get(d, []), "description": defs_of(d),
            "dimensions": [dimension(x) for x in dim_ids],
            "prototypes": [prototype(p, dim_ids) for p in protos],
            "issues": issues,
        })
    domains.sort(key=lambda x: (x["label"].lower(), x["id"]))

    return {"meta": {**loaded.meta, "queries": QUERIES, "base": loaded.document.base},
            "domains": domains, "sources": sources}
