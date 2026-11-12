"""Validate the Domain Model outputs in domains/ against the template, the macro and the sources.

Reads every generated ODS independently (LibreOffice CSV export of each sheet)
and compares it and its YAML with the raw files in sources/. Missing
definitions ("undefined") and unknown range/circularity (ODS "unknown", YAML
null) are accepted only where the sources really lack the value; coordinates
must be numeric, within any documented range and equal to the source values.
The ODS -> YAML exporter is tested against a YAML file produced by the real
ExportYAML macro (domains/yourdomainmodel2.yaml) and on invalid scratch copies.

Usage (from the repository root):
    python3 domains/validate_domain_models.py
Exit code 0 = all checks passed.
"""

from __future__ import annotations

import csv
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "domains"))
import build_domain_models as gen  # noqa: E402  (only for the exporter tests in section E)

SOURCES = ROOT / "sources"
DOMAINS = ROOT / "domains"
REPORT = DOMAINS / "GENERATION_REPORT.md"
MISSING = DOMAINS / "MISSING_DEFINITIONS.md"
UNDEFINED, UNKNOWN = "undefined", "unknown"

# sha256 of files that must not change, recorded before the generator was first run.
PROTECTED = {
    "domain_model_template_with_notes.ods": "41da6e1fc42e9e9aa0a81a35e6273ae4453502c1a7a0406b7b315d84ba2201b2",
    "custom_domain_model_definition.ods": "ad32d2f796da9ca98a9c39721580510bcc1fc52d757497d547f31c5bc087515d",
    "domains/yourdomainmodel.yaml": "1efac8a99c4f83d2a51ada36d125fbef32016a37d33ee54fd9b7da2afa439ac6",
    "domains/yourdomainmodel2.yaml": "e5a58069d9700918c996c7e99e19fc241689d10cfe01bba8c6db9fa010477ef7",
    "owl/emotional_ontology.owl": "91aaea5eb52dff9a0891a295c182295c95d9724ddc5d949f9860439cec016827",
    "owl/emotional_ontology_populated.owl": "ba5943d825c1153fab88e05224c82b95ddfec3f21c9cf37ab00c4ac2db874d4e",
    "sources/emotions/emotion_dictionary.ods": "666f96aa48e937206e2791ef78e516aa9d28856590d2c3cb69f19c9004670cf1",
    "sources/emotions/emotion_catalogue.ods": "5366328234ae4c910460fb7ea9838a366b3491d56f6d48a932642cb2c2f72bc1",
}
YAML_KEYS = ["schema_version", "id", "name", "description", "notes", "dimensions", "emotions"]
DIM_KEYS = ["id", "name", "definition", "notes", "min", "max", "circular"]
EMO_KEYS = ["id", "name", "definition", "notes", "coordinates"]

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def key(label):
    return re.sub(r"\s+", " ", label.replace("_", " ").strip()).casefold()


def safe_id(label):  # independent re-implementation of the macro's SafeID
    out = ""
    for ch in label.strip(" ").lower():
        if ch in "abcdefghijklmnopqrstuvwxyz0123456789_":
            out += ch
        elif ch in " -":
            out += "_"
    return out


def raw_rows(rel):
    with open(SOURCES / rel, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        return [(reader.line_num, dict(zip(header, r))) for r in reader]


WORK = Path(tempfile.mkdtemp(prefix="domain_models_verify_"))


def sheets_of(path: Path):
    """All sheets of an ODS, read back by LibreOffice as CSV (full precision, not 'as shown')."""
    out_dir = WORK / path.stem
    out_dir.mkdir(exist_ok=True)
    subprocess.run(["soffice", f"-env:UserInstallation=file://{WORK}/profile", "--headless", "--convert-to",
                    "csv:Text - txt - csv (StarCalc):44,34,76,1,,0,false,true,false,false,false,-1",
                    "--outdir", str(out_dir), str(path)], capture_output=True, timeout=180, check=True)
    with zipfile.ZipFile(path) as z:
        names = re.findall(r'<table:table table:name="([^"]*)"', z.read("content.xml").decode())
    result = {}
    for name in names:
        f = out_dir / f"{path.stem}-{name}.csv"
        with open(f, newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        result[name] = [r + [""] * (13 - len(r)) for r in rows] + [[""] * 13] * max(0, 64 - len(rows))
    return result


def cell(rows, ref):  # "B4" -> rows[3][1]
    m = re.fullmatch(r"([A-Z])(\d+)", ref)
    return rows[int(m.group(2)) - 1][ord(m.group(1)) - 65]


# ----------------------------------------------------------------- sources
dim_models = {r["model_label"].strip(): (line, r) for line, r in raw_rows("dimensional_model_overview.csv")}
disc_models = {r["model_label"].strip(): (line, r) for line, r in raw_rows("discrete_model_overview.csv")}
dict_rows = sheets_of(SOURCES / "emotions" / "emotion_dictionary.ods")["Dictionary"]
dict_head = [h for h in dict_rows[0] if h]
dictionary = {}
for r in dict_rows[1:]:
    if r[0]:
        dictionary[key(r[0])] = [(dict_head[i].removesuffix(" definition"), r[i], r[i + 1])
                                 for i in range(1, len(dict_head), 2) if r[i] != ""]
catalogue = {key(r[0]): r[1] for r in sheets_of(SOURCES / "emotions" / "emotion_catalogue.ods")["Catalogue"][1:] if r[0]}
template = sheets_of(ROOT / "domain_model_template_with_notes.ods")["DomainModel"]

# ----------------------------------------------------------------- A. nothing protected was modified
changed = [p for p, h in PROTECTED.items() if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h]
check("Template, macro workbook, ontology OWL files, emotion dictionary/catalogue and existing YAML unchanged (sha256)",
      not changed, f"changed: {changed}")
git = subprocess.run(["git", "status", "--porcelain", "--", "sources", "owl", "create_ontology.py", "populate_ontology.py"],
                     cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
dirty = [l for l in git if l and l[3:].rstrip("/") != "sources/emotions"]
check("No tracked source, ontology or ontology-code file modified (git status)", not dirty, f"{dirty}")

# ----------------------------------------------------------------- B. every model accounted for
expected = {m for m, (_, r) in dim_models.items() if r["model_dimensions"].strip()}
missing_md = MISSING.read_text(encoding="utf-8") if MISSING.exists() else ""
check("Every dimensional model with at least one dimension has domains/<model>.ods and domains/<model>.yaml",
      all((DOMAINS / f"{m}.ods").exists() and (DOMAINS / f"{m}.yaml").exists() for m in expected), f"{sorted(expected)}")
check("No leftover drafts directory", not (DOMAINS / "drafts").exists())
check("Every model not generated (discrete or without dimensions) is listed in MISSING_DEFINITIONS.md",
      all(f"| `{m}` |" in missing_md for m in (set(dim_models) - expected) | set(disc_models)),
      f"{sorted((set(dim_models) - expected) | set(disc_models))}")
report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
check("GENERATION_REPORT.md names every model", report and all(f"`{m}`" in report for m in list(dim_models) + list(disc_models)))


def md_rows(model):
    """(kind, item, missing) rows of MISSING_DEFINITIONS.md for one model."""
    sect = missing_md.split(f"## `{model}`", 1)[1].split("\n## ", 1)[0] if f"## `{model}`" in missing_md else ""
    rows = []
    for line in sect.splitlines():
        parts = [p.strip() for p in line.strip("|").split(" | ")]
        if len(parts) == 4 and parts[0] in ("model", "dimension", "emotion"):
            rows.append((parts[0], parts[1], parts[2], parts[3]))
    return rows


# ----------------------------------------------------------------- C/D. ODS and YAML per model
LABEL_CELLS = [(r, c) for r in range(64) for c in range(13) if template[r][c] != ""]
for m in sorted(expected):
    s = sheets_of(DOMAINS / f"{m}.ods")["DomainModel"]
    text = (DOMAINS / f"{m}.yaml").read_text(encoding="utf-8")
    y = yaml.safe_load(text)
    line, row = dim_models[m]
    dims = [d.strip() for d in row["model_dimensions"].split(",") if d.strip()]
    md = md_rows(m)
    md_items = {(k, i, miss.split(" (")[0]) for k, i, miss, _ in md}

    # --- ODS vs sources ---
    problems = []
    if list(sheets_of(DOMAINS / f"{m}.ods")) != ["DomainModel"]:
        problems.append("sheets")
    if any(s[r][c] != template[r][c] for r, c in LABEL_CELLS if not (r == 31 and 3 <= c <= 11)):
        problems.append("template label cells changed")
    if cell(s, "B4") != m or cell(s, "B5") != "":
        problems.append("name/description")
    if row["model_source"].strip() and row["model_source"].strip() not in cell(s, "B6"):
        problems.append("model source missing from Notes")
    rng = [row["range_min"].strip(), row["range_max"].strip()]
    for i, dim in enumerate(dims):
        r = s[9 + i]
        exp_range = rng if all(rng) else [UNKNOWN, UNKNOWN]
        if r[0] != safe_id(dim) or r[1] != dim or s[31][3 + i] != dim:
            problems.append(f"dimension {dim} id/name")
        if r[2] != UNDEFINED:  # no source documents any dimension definition
            problems.append(f"dimension {dim} definition {r[2]!r}")
        if [r[3], r[4]] != exp_range:
            problems.append(f"dimension {dim} range {r[3:5]} (expected {exp_range})")
        if r[5] != UNKNOWN:  # circularity is documented nowhere
            problems.append(f"dimension {dim} circularity {r[5]!r}")
    if any(s[9 + i][1] for i in range(len(dims), 20)) or any(s[31][3 + i] for i in range(len(dims), 9)):
        problems.append("extra dimensions")
    check(f"{m}.ods: model and dimensions match sources; undocumented definitions 'undefined', range/circularity "
          "'unknown' (nothing substituted)", not problems, "; ".join(problems))

    proto_rel = f"models/{m}/standard_model.csv"
    src = raw_rows(proto_rel) if (SOURCES / proto_rel).exists() else []
    protos = [s[r] for r in range(33, 63) if s[r][1] != ""]
    name_bad, coord_bad, ref_bad, def_bad = [], [], [], []
    if [p[1] for p in protos] != [r["emotion"] for _, r in src]:
        name_bad.append("prototype list/order differs from the source file")
    if any(any(s[r]) for r in range(33 + len(protos), 63)):
        name_bad.append("content below the last prototype")
    for (p_line, src_row), p in zip(src, protos):
        if p[0] != safe_id(p[1]):
            name_bad.append(f"{p[1]}: id {p[0]}")
        for i, dim in enumerate(dims):
            try:
                ok = float(p[3 + i]) == float(src_row[dim])
            except ValueError:
                ok = False
            if not ok:
                coord_bad.append((p[1], dim, p[3 + i], src_row[dim]))
        if any(p[3 + i] for i in range(len(dims), 9)):
            coord_bad.append((p[1], "extra coordinate"))
        if key(p[1]) not in catalogue:
            ref_bad.append(p[1])
        defs = dictionary.get(key(p[1]), [])
        exp_def = defs[0][1] if len(defs) == 1 else UNDEFINED
        if p[2] != exp_def or f"sources/{proto_rel} line {p_line}." not in p[12]:
            def_bad.append(p[1])
    check(f"{m}.ods: prototype names, order and IDs match " + (f"sources/{proto_rel}" if src else "sources (none documented)"),
          not name_bad, f"{len(protos)} prototypes {name_bad}")
    check(f"{m}.ods: every coordinate numeric and exactly equal to the source value", not coord_bad,
          f"{len(protos) * len(dims)} coordinates; mismatches: {coord_bad}")
    check(f"{m}.ods: every prototype references an existing emotion concept", not ref_bad, f"unresolved: {ref_bad}")
    check(f"{m}.ods: definitions verbatim from the dictionary, 'undefined' exactly where it has none", not def_bad,
          f"problems: {def_bad}")

    # --- YAML structure and validity ---
    struct = list(y) == YAML_KEYS and all(list(d) == DIM_KEYS for d in y["dimensions"]) and \
        all(list(e) == EMO_KEYS for e in y["emotions"])
    check(f"{m}.yaml: ExportYAML structure (keys and order)", struct)
    invalid = []
    for dd in y["dimensions"]:
        if not isinstance(dd["definition"], str) or not dd["definition"]:
            invalid.append(f"{dd['id']} definition")
        if (dd["min"] is None) != (dd["max"] is None) or (dd["min"] is not None and not (
                type(dd["min"]) in (int, float) and type(dd["max"]) in (int, float) and dd["min"] < dd["max"])):
            invalid.append(f"{dd['id']} range")
        if dd["circular"] not in (True, False, None):
            invalid.append(f"{dd['id']} circular")
    for e in y["emotions"]:
        if list(e["coordinates"]) != [dd["id"] for dd in y["dimensions"]]:
            invalid.append(f"{e['id']} coordinate keys")
        for dd in y["dimensions"]:
            v = e["coordinates"].get(dd["id"])
            if type(v) not in (int, float):
                invalid.append(f"{e['id']}.{dd['id']} = {v!r} (not a number)")
            elif dd["min"] is not None and not dd["min"] <= v <= dd["max"]:
                invalid.append(f"{e['id']}.{dd['id']} = {v} out of range")
    check(f"{m}.yaml: valid — numeric coordinates within any documented range; 'undefined' definitions and null "
          "range/circularity accepted", not invalid, f"{invalid}")
    yaml_coords = [list(e["coordinates"].values()) for e in y["emotions"]]
    check(f"{m}.yaml: every coordinate exactly equals the source value",
          yaml_coords == [[float(r[d]) for d in dims] for _, r in src], f"{sum(map(len, yaml_coords))} coordinates")

    # --- ODS <-> YAML equivalence (field by field) ---
    as_num = lambda v: None if v == UNKNOWN else float(v)  # noqa: E731
    as_circ = lambda v: {"yes": True, "no": False, UNKNOWN: None}.get(v.lower(), "INVALID")  # noqa: E731
    ods_view = {
        "id": safe_id(cell(s, "B4")), "name": cell(s, "B4"), "description": cell(s, "B5"), "notes": cell(s, "B6"),
        "dimensions": [{"id": s[9 + i][0], "name": s[9 + i][1], "definition": s[9 + i][2], "notes": s[9 + i][6],
                        "min": as_num(s[9 + i][3]), "max": as_num(s[9 + i][4]), "circular": as_circ(s[9 + i][5])}
                       for i in range(len(dims))],
        "emotions": [{"id": p[0], "name": p[1], "definition": p[2], "notes": p[12],
                      "coordinates": {s[9 + i][0]: float(p[3 + i]) for i in range(len(dims))}} for p in protos]}
    yaml_view = {k: y[k] for k in ods_view}
    check(f"{m}: ODS and YAML contain equivalent information (every field)", ods_view == yaml_view)

    # --- MISSING_DEFINITIONS.md covers every placeholder ---
    needed = {("dimension", d["name"], "Definition") for d in y["dimensions"] if d["definition"] == UNDEFINED} | \
             {("dimension", d["name"], "Minimum and maximum") for d in y["dimensions"] if d["min"] is None} | \
             {("dimension", d["name"], "Circularity") for d in y["dimensions"] if d["circular"] is None} | \
             {("emotion", e["name"], "Definition") for e in y["emotions"] if e["definition"] == UNDEFINED}
    extra = {i for i in md_items if i[0] != "model"} - needed
    check(f"{m}: MISSING_DEFINITIONS.md lists exactly the 'undefined'/unknown items, each with source references",
          needed <= md_items and not extra and all(refs for *_, refs in md),
          f"{len(needed)} items; unlisted {sorted(needed - md_items)}; extra {sorted(extra)}")

# ----------------------------------------------------------------- E. exporter behaviour
with gen.office() as session:
    macro = gen.MacroFunctions(session)
    try:
        # E1: rebuild the macro-exported example in a copy of the template and compare byte-for-byte.
        golden_text = (DOMAINS / "yourdomainmodel2.yaml").read_text(encoding="utf-8")
        g = yaml.safe_load(golden_text)
        doc = gen.load(session, ROOT / "domain_model_template_with_notes.ods", AsTemplate=True)
        d = doc.Sheets.getByName("DomainModel")
        d.getCellRangeByName("B4").String = g["name"]
        d.getCellRangeByName("B5").String = g["description"]
        d.getCellRangeByName("B6").String = g["notes"]
        for i, dim in enumerate(g["dimensions"]):
            for c, v in enumerate([dim["id"], dim["name"], dim["definition"]]):
                d.getCellByPosition(c, 9 + i).String = v
            d.getCellByPosition(3, 9 + i).Value = dim["min"]
            d.getCellByPosition(4, 9 + i).Value = dim["max"]
            d.getCellByPosition(5, 9 + i).String = "yes" if dim["circular"] else "no"
            d.getCellByPosition(6, 9 + i).String = dim["notes"]
        for j, emo in enumerate(g["emotions"]):
            for c, v in enumerate([emo["id"], emo["name"], emo["definition"]]):
                d.getCellByPosition(c, 33 + j).String = v
            d.getCellByPosition(12, 33 + j).String = emo["notes"]
            for i, v in enumerate(emo["coordinates"].values()):
                d.getCellByPosition(3 + i, 33 + j).Value = v
        golden_ods = session.work / "golden.ods"
        doc.storeToURL(gen.uno.systemPathToFileUrl(str(golden_ods)), (gen.prop("FilterName", "calc8"),))
        doc.close(True)
        out, errs = gen.export_yaml(session, macro, golden_ods)
        check("Exporter reproduces a YAML file written by the real ExportYAML macro byte-for-byte "
              "(domains/yourdomainmodel2.yaml)", out == golden_text and not errs, f"errors: {errs}")

        # E2: re-exporting each generated ODS reproduces its YAML byte-for-byte (YAML derived from ODS).
        for m in sorted(expected):
            out, errs = gen.export_yaml(session, macro, DOMAINS / f"{m}.ods")
            check(f"{m}: re-export of {m}.ods reproduces {m}.yaml byte-for-byte",
                  out == (DOMAINS / f"{m}.yaml").read_text(encoding="utf-8"), f"errors: {errs}")

        # E3: invalid coordinates are rejected (scratch copies of the circumplex ODS).
        def mutated(label, edit):
            scratch = session.work / f"mut_{label}.ods"
            shutil.copyfile(DOMAINS / "circumplex.ods", scratch)
            doc = gen.load(session, scratch)
            edit(doc.Sheets.getByName("DomainModel"))
            doc.store()
            doc.close(True)
            return gen.export_yaml(session, macro, scratch)

        def set_text(sh):
            sh.getCellByPosition(3, 33).String = "n/a"

        def set_empty(sh):
            sh.getCellByPosition(4, 34).setFormula("")

        def set_out_of_range(sh):
            sh.getCellByPosition(3, 35).Value = 1.5

        def set_bad_range(sh):
            sh.getCellByPosition(3, 9).String = "unknown"  # min unknown but max numeric

        for label, edit, expect in [("text", set_text, "missing/non-numeric coordinate"),
                                    ("empty", set_empty, "missing/non-numeric coordinate"),
                                    ("range", set_out_of_range, "out of range"),
                                    ("halfrange", set_bad_range, "invalid numerical range")]:
            out, errs = mutated(label, edit)
            check(f"Exporter rejects an invalid coordinate/range ({label})", out is None and any(expect in e for e in errs),
                  f"{errs}")
    finally:
        macro.close()

shutil.rmtree(WORK, ignore_errors=True)
print(f"\n{sum(RESULTS)}/{len(RESULTS)} checks passed.")
sys.exit(0 if all(RESULTS) else 1)
