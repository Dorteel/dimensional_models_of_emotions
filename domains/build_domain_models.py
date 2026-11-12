"""Generate Domain Model ODS and YAML files from the files in sources/.

Pipeline, per dimensional model documented in sources/dimensional_model_overview.csv
that has at least one quality dimension:

  1. Open domain_model_template_with_notes.ods as a template (never modified) and
     fill its DomainModel sheet exactly where the template's macros write
     (B4:B6 model; rows 10-29 dimensions; row 32 coordinate headers; rows 34-63
     prototypes; column M prototype notes). Save it as domains/<model>.ods.
  2. Re-open that saved ODS and export domains/<model>.yaml with a port of the
     ExportYAML macro (custom_domain_model_definition.ods, Basic/Standard/Module1).
     Scalars are formatted by the macro's own YAMLQuote / YAMLNumber / SafeID.
     The YAML is always derived from the ODS, never written independently.
  3. Write domains/MISSING_DEFINITIONS.md listing everything undocumented.

Nothing is invented:
  * a missing dimension or emotion definition is the exact string "undefined";
  * a missing range or circularity is the text "unknown" in the ODS and null in
    the YAML (the only extension of the macro's export rules);
  * a missing model description is left empty (the template does not require one);
  * coordinates and available definitions are copied verbatim.

Discrete models (sources/discrete_model_overview.csv) have no quality
dimensions; the template requires at least one, so they are only reported.

Usage (from the repository root):
    python3 domains/build_domain_models.py                    # (re)generate from sources/
    python3 domains/build_domain_models.py --export <x.ods>   # YAML from an edited ODS only

Regenerating overwrites domains/<model>.ods; keep manual edits in a copy and
export it with --export, or add the missing facts to sources/.
"""

from __future__ import annotations

import contextlib
import csv
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "sources"
DOMAINS = ROOT / "domains"
TEMPLATE = ROOT / "domain_model_template_with_notes.ods"
MACRO_DOC = ROOT / "custom_domain_model_definition.ods"
DICTIONARY = SOURCES / "emotions" / "emotion_dictionary.ods"
CATALOGUE = SOURCES / "emotions" / "emotion_catalogue.ods"
MISSING_REPORT = DOMAINS / "MISSING_DEFINITIONS.md"
UNDEFINED = "undefined"   # documented-definition placeholder (exact string required)
UNKNOWN = "unknown"       # undocumented range / circularity (YAML null)

# Template layout (0-based row/column indices, as used by the template macros)
DIM_ROWS = range(9, 29)       # rows 10-29
COORD_HEADER_ROW = 31         # row 32, columns D onward
PROTO_ROWS = range(33, 63)    # rows 34-63
PROTO_NOTES_COL = 12          # column M
MAX_DIMS, MAX_PROTOS = 9, 30


def key(label: str) -> str:
    """Lexical identity used by the emotion dictionary (case, whitespace, '_' not significant)."""
    return re.sub(r"\s+", " ", label.replace("_", " ").strip()).casefold()


def read_csv(rel: str):
    with open(SOURCES / rel, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        return [(reader.line_num, dict(zip(header, row))) for row in reader]


def basic_trim(text: str) -> str:
    return text.strip(" ")


# --------------------------------------------------------------------------
# LibreOffice session
# --------------------------------------------------------------------------

def prop(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


class Session:
    def __init__(self, desktop, work: Path):
        self.desktop, self.work = desktop, work


@contextlib.contextmanager
def office():
    """Headless LibreOffice with a throwaway profile; yields a Session (desktop + scratch dir)."""
    work = Path(tempfile.mkdtemp(prefix="domain_models_lo_"))
    pipe = f"domainmodels{int(time.time() * 1000)}"
    proc = subprocess.Popen(["soffice", f"-env:UserInstallation=file://{work}/profile", "--headless", "--invisible",
                             "--norestore", f"--accept=pipe,name={pipe};urp;"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(120):
            try:
                ctx = resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        else:
            raise SystemExit("Could not connect to LibreOffice")
        session = Session(ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx), work)
        yield session
        with contextlib.suppress(Exception):
            session.desktop.terminate()
    finally:
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(work, ignore_errors=True)


def load(desktop, path: Path, **extra):
    args = [prop("Hidden", True)] + [prop(k, v) for k, v in extra.items()]
    return desktop.desktop.loadComponentFromURL(uno.systemPathToFileUrl(str(path)), "_blank", 0, tuple(args))


class MacroFunctions:
    """YAMLQuote, YAMLNumber and SafeID executed by the template's own Basic macro."""

    def __init__(self, desktop):
        # Work on a scratch copy so the macro workbook itself is never opened for writing.
        self.copy = desktop.work / "macro_copy.ods"
        shutil.copyfile(MACRO_DOC, self.copy)
        self.doc = load(desktop, self.copy, ReadOnly=True, MacroExecutionMode=4)
        provider = self.doc.getScriptProvider()
        self.fn = {name: provider.getScript(f"vnd.sun.star.script:Standard.Module1.{name}?language=Basic&location=document")
                   for name in ("YAMLQuote", "YAMLNumber", "SafeID")}

    def __call__(self, name, value):
        return self.fn[name].invoke((value,), (), ())[0]

    def close(self):
        self.doc.close(True)


def read_sheet(desktop, path: Path, sheet: str):
    doc = load(desktop, path, ReadOnly=True)
    try:
        data = doc.Sheets.getByName(sheet).getCellRangeByName("A1").getSpreadsheet()
        cursor = data.createCursor()
        cursor.gotoEndOfUsedArea(False)
        rows = cursor.RangeAddress.EndRow + 1
        cols = cursor.RangeAddress.EndColumn + 1
        return [list(r) for r in data.getCellRangeByPosition(0, 0, cols - 1, rows - 1).DataArray]
    finally:
        doc.close(True)


# --------------------------------------------------------------------------
# Source models
# --------------------------------------------------------------------------

def load_dictionary(desktop):
    rows = read_sheet(desktop, DICTIONARY, "Dictionary")
    head = rows[0]
    out = {}
    for r in rows[1:]:
        defs = []
        for i in range(1, len(head), 2):
            if str(r[i]) != "":
                defs.append({"source": head[i].removesuffix(" definition"), "text": str(r[i]), "reference": str(r[i + 1])})
        out[key(str(r[0]))] = {"name": str(r[0]), "definitions": defs}
    return out


def load_catalogue(desktop):
    rows = read_sheet(desktop, CATALOGUE, "Catalogue")
    return {key(str(r[0])): {"name": str(r[0]), "id": str(r[1])} for r in rows[1:]}


def dimensional_models():
    models = []
    for line, row in read_csv("dimensional_model_overview.csv"):
        label = row["model_label"].strip()
        dims = [d.strip() for d in row["model_dimensions"].split(",") if d.strip()]
        proto_file = SOURCES / "models" / label / "standard_model.csv"
        prototypes = []
        if proto_file.exists():
            for p_line, p_row in read_csv(f"models/{label}/standard_model.csv"):
                prototypes.append({"name": p_row["emotion"], "line": p_line,
                                   "coords": {d: p_row[d] for d in p_row if d != "emotion"}})
        models.append({"label": label, "line": line, "row": row, "dims": dims,
                       "proto_file": f"models/{label}/standard_model.csv" if proto_file.exists() else None,
                       "prototypes": prototypes})
    return models


# --------------------------------------------------------------------------
# Populate ODS
# --------------------------------------------------------------------------

def related_concepts(label, dictionary):
    """Dictionary concepts whose single-word label shares nearly the whole stem (heuristic, never merged)."""
    k = key(label)
    out = []
    for other_key, entry in dictionary.items():
        if other_key == k or " " in other_key or "/" in other_key or " " in k:
            continue
        prefix = len(os.path.commonprefix([k, other_key]))
        if prefix >= 3 and prefix >= min(len(k), len(other_key)) - 2:
            out.append(entry)
    return out


def populate(desktop, macro, model, dictionary, datasets, out_path: Path):
    """Write the model into a copy of the template; return the list of missing items (for MISSING_DEFINITIONS.md)."""
    missing = []
    row = model["row"]
    name = model["label"]
    src_loc = f"sources/dimensional_model_overview.csv line {model['line']}"
    model_src = row["model_source"].strip()
    model_refs = [f"Model source: {model_src}" if model_src else "Model source: none recorded",
                  f"Model row: {src_loc}"]

    def gap(kind, item, info, refs):
        missing.append({"model": name, "kind": kind, "item": item, "missing": info, "references": refs})

    doc = load(desktop, TEMPLATE, AsTemplate=True)
    try:
        d = doc.Sheets.getByName("DomainModel")
        # --- model (macro SaveModel: B4 name, B5 description, B6 notes) ---
        d.getCellRangeByName("B4").String = name
        gap("model", name, "Description (not required by the template; left blank)", model_refs)
        if not model_src:
            gap("model", name, "Source reference (model_source is empty)", [f"Model row: {src_loc}"])
        notes = [f"Model as listed in {src_loc} (model_label '{name}').",
                 f"Source: {model_src}." if model_src else "Source: none recorded (model_source is empty).",
                 f"model_dimensions as recorded: \"{row['model_dimensions']}\"."]
        if row["ground_truth"].strip():
            notes.append(f"ground_truth as recorded: \"{row['ground_truth'].strip()}\".")
        notes.append(f"'{UNDEFINED}' = no documented definition; '{UNKNOWN}' = value not documented "
                     "(see domains/MISSING_DEFINITIONS.md).")
        d.getCellRangeByName("B6").String = " ".join(notes)

        # --- dimensions (macro AddDimension: A id, B name, C definition, D min, E max, F circular, G notes) ---
        rmin, rmax = row["range_min"].strip(), row["range_max"].strip()
        has_range = rmin != "" and rmax != ""
        if len(model["dims"]) > MAX_DIMS:
            raise SystemExit(f"{name}: more than {MAX_DIMS} dimensions")
        for i, dim in enumerate(model["dims"]):
            r = DIM_ROWS[i]
            dim_refs = model_refs + [f"Dataset annotated with '{dim}': {ds} ({ref}, sources/datasets.csv line {ln})"
                                     for ds, ref, dims, ln in datasets if dim in dims]
            same = dictionary.get(key(dim))
            if same:
                dim_refs.append(f"Emotion concept with the same label in the emotion dictionary: '{same['name']}' "
                                "(an emotion, not a dimension definition)")
            d.getCellByPosition(0, r).String = macro("SafeID", dim)
            d.getCellByPosition(1, r).String = dim
            d.getCellByPosition(2, r).String = UNDEFINED  # no source documents dimension definitions
            gap("dimension", dim, "Definition (written as 'undefined')", dim_refs)
            dim_notes = [f"Dimension listed in model_dimensions, {src_loc}.", "Definition: none documented."]
            if has_range:
                d.getCellByPosition(3, r).Value = float(rmin)
                d.getCellByPosition(4, r).Value = float(rmax)
                dim_notes.append(f"Minimum/maximum from range_min/range_max of that row ({rmin}, {rmax}); "
                                 "recorded once per model and applied to each of its dimensions.")
            else:
                d.getCellByPosition(3, r).String = UNKNOWN
                d.getCellByPosition(4, r).String = UNKNOWN
                dim_notes.append("Minimum/maximum: not documented (range_min/range_max empty).")
                gap("dimension", dim, "Minimum and maximum (written as 'unknown'; YAML null)", dim_refs)
            d.getCellByPosition(5, r).String = UNKNOWN  # circularity is not documented for any dimension
            dim_notes.append("Circularity: not documented.")
            gap("dimension", dim, "Circularity (written as 'unknown'; YAML null)", dim_refs)
            d.getCellByPosition(6, r).String = " ".join(dim_notes)
            d.getCellByPosition(3 + i, COORD_HEADER_ROW).String = dim

        # --- prototypes (macro AddPrototype: A id, B name, C definition, D.. coordinates, M notes) ---
        if not model["prototypes"]:
            gap("model", name, "Prototypical emotions and coordinates (no sources/models/"
                f"{name}/standard_model.csv; exported as 'emotions: []')", model_refs)
        if len(model["prototypes"]) > MAX_PROTOS:
            raise SystemExit(f"{name}: more than {MAX_PROTOS} prototypes")
        source_dims = list(model["prototypes"][0]["coords"]) if model["prototypes"] else []
        if model["prototypes"] and source_dims != model["dims"]:
            raise SystemExit(f"{name}: coordinate columns {source_dims} differ from dimensions {model['dims']}")
        for j, proto in enumerate(model["prototypes"]):
            r = PROTO_ROWS[j]
            entry = dictionary.get(key(proto["name"]))
            if entry is None:
                raise SystemExit(f"{name}: prototype '{proto['name']}' is not in the emotion dictionary")
            coord_loc = f"sources/{model['proto_file']} line {proto['line']}"
            d.getCellByPosition(0, r).String = macro("SafeID", proto["name"])
            d.getCellByPosition(1, r).String = proto["name"]
            p_notes = [f"Coordinates: {coord_loc}."]
            defs = entry["definitions"]
            if len(defs) == 1:
                d.getCellByPosition(2, r).String = defs[0]["text"]
                ref = f", {defs[0]['reference']}" if defs[0]["reference"] else ""
                p_notes.append(f"Definition: {defs[0]['source']}{ref} (via sources/emotions/emotion_dictionary.ods, "
                               f"concept '{entry['name']}').")
            elif not defs:
                d.getCellByPosition(2, r).String = UNDEFINED
                p_notes.append(f"Definition: none in sources/emotions/emotion_dictionary.ods (concept '{entry['name']}').")
                refs = model_refs + [f"Coordinates: {coord_loc}",
                                     f"Emotion dictionary concept '{entry['name']}' (catalogue): no definitions or source URLs"]
                for rel in related_concepts(proto["name"], dictionary):
                    srcs = "; ".join(f"{x['source']}" + (f" {x['reference']}" if x["reference"] else "")
                                     for x in rel["definitions"]) or "no definitions"
                    refs.append(f"Lexically related dictionary concept '{rel['name']}' (different concept, "
                                f"not merged; heuristic): {srcs}")
                gap("emotion", proto["name"], "Definition (written as 'undefined')", refs)
            else:
                raise SystemExit(f"{name}: '{proto['name']}' has {len(defs)} candidate definitions; "
                                 "choosing one needs a researcher decision")
            for i, dim in enumerate(model["dims"]):
                d.getCellByPosition(3 + i, r).Value = float(proto["coords"][dim])
            d.getCellByPosition(PROTO_NOTES_COL, r).String = " ".join(p_notes)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        doc.storeToURL(uno.systemPathToFileUrl(str(out_path)), (prop("FilterName", "calc8"),))
    finally:
        doc.close(True)
    return missing


# --------------------------------------------------------------------------
# ExportYAML (port of the macro; scalars formatted by the macro itself)
# --------------------------------------------------------------------------

def export_yaml(desktop, macro, path: Path):
    """Return (yaml_text or None, errors).

    Applies the ExportYAML validation rules, with one documented extension: a dimension's
    Minimum/Maximum or Circular? cell may contain the text 'unknown', exported as YAML null.
    Definitions are required to be non-empty (they may be 'undefined'). Coordinates must be
    numeric and, when the dimension's range is known, inside it. All errors are collected.
    """
    doc = load(desktop, path, ReadOnly=True)
    try:
        d = doc.Sheets.getByName("DomainModel")
        Q = lambda v: macro("YAMLQuote", v)  # noqa: E731
        N = lambda v: macro("YAMLNumber", v)  # noqa: E731
        is_value = lambda c: c.Type.value == "VALUE"  # noqa: E731
        is_unknown = lambda c: not is_value(c) and basic_trim(c.String).lower() == UNKNOWN  # noqa: E731
        errors = []
        model_name = basic_trim(d.getCellRangeByName("B4").String)
        if model_name == "":
            errors.append("Please save a model name first.")
        model_id = macro("SafeID", model_name)
        if model_name and model_id == "":
            errors.append("The model name must contain letters or digits to form an identifier.")
        out = [f"schema_version: {Q('1.0')}", f"id: {Q(model_id)}", f"name: {Q(model_name)}",
               f"description: {Q(d.getCellRangeByName('B5').String)}", f"notes: {Q(d.getCellRangeByName('B6').String)}",
               "dimensions:"]
        ids, mins, maxs = [], [], []
        for row in DIM_ROWS:
            label = basic_trim(d.getCellByPosition(1, row).String)
            if label == "":
                break
            identifier = basic_trim(d.getCellByPosition(0, row).String)
            definition = basic_trim(d.getCellByPosition(2, row).String)
            circular = basic_trim(d.getCellByPosition(5, row).String).lower()
            if identifier == "" or definition == "":
                errors.append(f"Dimension row {row + 1} needs an ID and definition.")
            if identifier in ids:
                errors.append(f"Duplicate dimension ID: {identifier}")
            if len(ids) > MAX_DIMS - 1:
                errors.append("Only the first 9 dimensions are supported by this template.")
            c_min, c_max = d.getCellByPosition(3, row), d.getCellByPosition(4, row)
            lo = hi = None
            if is_unknown(c_min) and is_unknown(c_max):
                min_txt = max_txt = "null"
            elif is_value(c_min) and is_value(c_max):
                lo, hi = c_min.Value, c_max.Value
                min_txt, max_txt = N(lo), N(hi)
                if lo >= hi:
                    errors.append(f"Dimension row {row + 1} has minimum >= maximum.")
                    lo = hi = None
            else:
                errors.append(f"Dimension row {row + 1} has an invalid numerical range "
                              f"(both numbers, or both '{UNKNOWN}').")
                min_txt = max_txt = "null"
            if circular == "yes":
                circ_txt = "true"
            elif circular == "no":
                circ_txt = "false"
            elif circular == UNKNOWN:
                circ_txt = "null"
            else:
                errors.append(f"Dimension row {row + 1} must have Circular = Yes, No or {UNKNOWN}.")
                circ_txt = "null"
            ids.append(identifier)
            mins.append(lo)
            maxs.append(hi)
            out += [f"  - id: {Q(identifier)}", f"    name: {Q(label)}", f"    definition: {Q(definition)}",
                    f"    notes: {Q(d.getCellByPosition(6, row).String)}", f"    min: {min_txt}",
                    f"    max: {max_txt}", f"    circular: {circ_txt}"]
        if not ids:
            errors.append("Please add at least one quality dimension before exporting.")
        out.append("emotions:")
        pcount = 0
        for row in PROTO_ROWS:
            label = basic_trim(d.getCellByPosition(1, row).String)
            if label == "":
                break
            identifier = basic_trim(d.getCellByPosition(0, row).String)
            definition = basic_trim(d.getCellByPosition(2, row).String)
            if identifier == "" or definition == "":
                errors.append(f"Prototype row {row + 1} needs an ID and definition.")
            out += [f"  - id: {Q(identifier)}", f"    name: {Q(label)}", f"    definition: {Q(definition)}",
                    f"    notes: {Q(d.getCellByPosition(PROTO_NOTES_COL, row).String)}", "    coordinates:"]
            for i, dim_id in enumerate(ids):
                cell = d.getCellByPosition(3 + i, row)
                if not is_value(cell):
                    errors.append(f"Prototype row {row + 1} has a missing/non-numeric coordinate for {dim_id}")
                    continue
                if mins[i] is not None and (cell.Value < mins[i] or cell.Value > maxs[i]):
                    errors.append(f"Prototype row {row + 1}: {dim_id} is out of range.")
                out.append(f"      {Q(dim_id)}: {N(cell.Value)}")
            pcount += 1
        for row in PROTO_ROWS[pcount:]:  # anything after the first empty name row would be silently dropped
            if any(d.getCellByPosition(c, row).String for c in range(0, 13)):
                errors.append(f"Prototype row {row + 1} has content but no emotion name.")
        if pcount == 0:
            out[-1] = "emotions: []"
        return (None if errors else "\n".join(out) + "\n"), errors
    finally:
        doc.close(True)


# --------------------------------------------------------------------------
# MISSING_DEFINITIONS.md
# --------------------------------------------------------------------------

def md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def write_missing_report(missing, not_generated):
    lines = [
        "# Missing Definitions and Unknown Values",
        "",
        "Generated by `domains/build_domain_models.py`; do not edit by hand. Regenerate after changing `sources/`.",
        "",
        "Nothing listed here was invented. In the Domain Model files:",
        "",
        f"- a missing **definition** is the exact string `\"{UNDEFINED}\"` (ODS cell and YAML);",
        f"- a missing **range** or **circularity** is the text `{UNKNOWN}` in the ODS and `null` in the YAML;",
        "- a missing model **description** is left empty (the template does not require one).",
        "",
        "The references are starting points for a human investigation. They are not evidence that the "
        "missing value exists there. Lexically related concepts are a heuristic and are never merged.",
        "",
    ]
    for model in sorted({m["model"] for m in missing}):
        rows = [m for m in missing if m["model"] == model]
        lines += [f"## `{model}`", "", "| Kind | Dimension / emotion | Missing information | Available source references |",
                  "|---|---|---|---|"]
        order = {"model": 0, "dimension": 1, "emotion": 2}
        for m in sorted(rows, key=lambda m: order[m["kind"]]):
            lines.append(f"| {m['kind']} | {md_cell(m['item'])} | {md_cell(m['missing'])} | "
                         + "<br>".join(md_cell(r) for r in m["references"]) + " |")
        lines.append("")
    lines += ["## Models not generated", "", "| Model | Missing information | Available source references |",
              "|---|---|---|"]
    for m in not_generated:
        refs = [f"Model row: sources/discrete_model_overview.csv line {m['line']}",
                f"Model source: {m['source']}" if m["source"] else "Model source: none recorded"]
        if m["emotion_labels"]:
            refs.append("Emotion labels: " + ", ".join(m["emotion_labels"]))
        lines.append(f"| `{m['model']}` | {md_cell(m['reason'])} | " + "<br>".join(md_cell(r) for r in refs) + " |")
    MISSING_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------

def main():
    missing, not_generated = [], []
    datasets = [(r["dataset_label"].strip(), r["dataset_source"].strip(),
                 [x.strip() for x in r["dimensions"].split(",")], line) for line, r in read_csv("datasets.csv")]
    failed = []
    with office() as session:
        macro = MacroFunctions(session)
        try:
            dictionary = load_dictionary(session)
            for model in dimensional_models():
                name = model["label"]
                if not model["dims"]:
                    not_generated.append({"model": name, "line": model["line"], "source": model["row"]["model_source"],
                                          "emotion_labels": [], "reason": "No quality dimensions documented."})
                    continue
                ods = DOMAINS / f"{name}.ods"
                missing += populate(session, macro, model, dictionary, datasets, ods)
                text, errors = export_yaml(session, macro, ods)
                if text is None:  # cannot happen with only documented data; never leave a stale YAML behind
                    (DOMAINS / f"{name}.yaml").unlink(missing_ok=True)
                    failed.append((name, errors))
                    print(f"[ERROR] {name}: YAML export refused: {errors}")
                    continue
                (DOMAINS / f"{name}.yaml").write_text(text, encoding="utf-8")
                print(f"[generated] domains/{name}.ods + domains/{name}.yaml")
        finally:
            macro.close()
    for line, row in read_csv("discrete_model_overview.csv"):
        not_generated.append({
            "model": row["model_label"], "line": line, "source": row["model_source"].strip(),
            "emotion_labels": [x.strip() for x in row["emotion_labels"].split(",") if x.strip()],
            "reason": "Discrete model: no quality dimensions or coordinates documented; the template requires "
                      "at least one dimension."})
        print(f"[not generated] {row['model_label']} (discrete model, no dimensions)")
    write_missing_report(missing, not_generated)
    print(f"Wrote {MISSING_REPORT.relative_to(ROOT)} ({len(missing)} missing items)")
    if failed:
        raise SystemExit(1)


def export_only(ods: Path):
    """Export YAML from an edited ODS (does not regenerate anything)."""
    with office() as session:
        macro = MacroFunctions(session)
        try:
            text, errors = export_yaml(session, macro, ods)
            name = macro("SafeID", basic_trim(load_name(session, ods))) if text else ""
        finally:
            macro.close()
    if text is None:
        print(f"YAML export refused for {ods}:")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)
    out = DOMAINS / f"{name}.yaml"
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}")


def load_name(session, ods: Path) -> str:
    doc = load(session, ods, ReadOnly=True)
    try:
        return doc.Sheets.getByName("DomainModel").getCellRangeByName("B4").String
    finally:
        doc.close(True)


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--export":
        export_only(Path(sys.argv[2]).resolve())
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit("usage: build_domain_models.py [--export <edited DomainModel .ods>]")
