"""Build emotion_dictionary.ods and emotion_catalogue.ods from the files in sources/.

Standard library only. Source files are read, never written. Output is
deterministic: the same inputs always produce byte-identical ODS files.

Usage (from the repository root):
    python3 sources/emotions/build_emotion_tables.py

emotion_dictionary.ods has a single sheet, "Dictionary": column A is the
emotion concept, then two adjacent columns per definition source
("<Source> definition", "<Source> source").

Rules:
  * A concept is a label that appears in a label column of a source file.
  * Labels are merged into one concept only if they are identical after
    trimming, collapsing whitespace, treating "_" as a space and ignoring
    case. No other merging (spelling variants, word forms, synonyms).
  * Definitions and source references are copied verbatim. A cell that is
    empty or contains only "-" is unavailable and left blank. A source
    reference is kept even when its definition is missing.
  * Dataset definition files have no reference column; their source cell is
    the dataset's reference from sources/datasets.csv (blank if none).
  * Distinct definitions from the same source for the same concept would get
    numbered column pairs ("APA (2) definition", ...); none exist currently.

emotion_catalogue.ods: one sheet, columns Emotion and Concept ID.
"""

from __future__ import annotations

import csv
import re
import zipfile
from collections import OrderedDict, defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
SOURCES = HERE.parent
DICTIONARY_PATH = HERE / "emotion_dictionary.ods"
CATALOGUE_PATH = HERE / "emotion_catalogue.ods"

DEFINITIONS_CSV = "emotion_definitions.csv"
DATASETS = ["affectnet", "emoset", "emotic", "goemotions"]
MODELS = ["circumplex", "pad"]
NRC_ZIP = "NRC-Emotion-Lexicon.zip"
NRC_MEMBER = "NRC-Emotion-Lexicon/NRC-Emotion-Lexicon-Wordlevel-v0.92.txt"
DATASETS_CSV = "datasets.csv"

# (header, file, definition column, reference column or None, dataset label in datasets.csv or None)
DEFINITION_SOURCES = [
    ("APA", DEFINITIONS_CSV, "apa_definition", "apa_definition_source", None),
    ("Cambridge", DEFINITIONS_CSV, "cambridge_definition", "cambridge_definition_source", None),
    ("Oxford", DEFINITIONS_CSV, "oxford_definition", "oxford_definition_source", None),
    ("Merriam-Webster", DEFINITIONS_CSV, "merriam-webster_definition", "merriam-webster_definition_source", None),
    ("WordNet 3.0 (via SentiWordNet)", DEFINITIONS_CSV, "sentiwordnet_definition", "sentiwordnet_definition_source", None),
    ("EMOTIC", "datasets/emotic/emotion_definitions.csv", "emotic_definition", None, "emotic"),
    ("AffectNet", "datasets/affectnet/emotion_definitions.csv", "affectnet_definition", None, "affectnet"),
    ("EmoSet", "datasets/emoset/emotion_definitions.csv", "emoset_definition", None, "emoset"),
    ("GoEmotions", "datasets/goemotions/emotion_definitions.csv", "goemotions_definition", None, "goemotions"),
]

PLACEHOLDERS = {"", "-"}


# --------------------------------------------------------------------------
# Normalisation helpers
# --------------------------------------------------------------------------

def label_key(label: str) -> str:
    """Lexical identity key: whitespace, '_' and case are not significant."""
    return re.sub(r"\s+", " ", label.replace("_", " ").strip()).casefold()


def concept_id(key: str) -> str:
    """Same slug rule as populate_ontology.safe_name (keeps ontology names aligned)."""
    text = re.sub(r"[^a-z0-9]+", "_", key.lower())
    text = re.sub(r"_+", "_", text).strip("_") or "unnamed"
    return "n_" + text if text[0].isdigit() else text


def is_placeholder(value: str) -> bool:
    return value.strip() in PLACEHOLDERS


def read_csv(rel: str):
    """Return (header, [(line_number, row_dict), ...]). Line numbers are 1-based file lines."""
    with open(SOURCES / rel, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = []
        for row in reader:
            rows.append((reader.line_num, dict(zip(header, row))))
    return header, rows


# --------------------------------------------------------------------------
# Collect label occurrences
# --------------------------------------------------------------------------

def collect_occurrences():
    """Every place an emotion label is written in sources/.

    role = "concept"   -> the label names an emotion in its own right
    role = "reference" -> the label refers to another emotion (compound components, closest word)
    role = "category"  -> lexicon category name (NRC)
    """
    occ = []

    def add(file, line, column, raw, role):
        occ.append({"file": file, "line": line, "column": column, "raw": raw, "role": role})

    _, rows = read_csv(DEFINITIONS_CSV)
    for line, row in rows:
        add(DEFINITIONS_CSV, line, "emotion_label", row["emotion_label"], "concept")

    for ds in DATASETS:
        rel = f"datasets/{ds}/emotion_definitions.csv"
        _, rows = read_csv(rel)
        for line, row in rows:
            add(rel, line, "emotion_label", row["emotion_label"], "concept")

    _, rows = read_csv("compound_emotions.csv")
    for line, row in rows:
        add("compound_emotions.csv", line, "emotion_label", row["emotion_label"], "concept")

    _, rows = read_csv("discrete_model_overview.csv")
    for line, row in rows:
        for part in row["emotion_labels"].split(","):
            if part.strip():
                add("discrete_model_overview.csv", line, f"emotion_labels ({row['model_label']})", part.strip(), "concept")

    for model in MODELS:
        rel = f"models/{model}/standard_model.csv"
        _, rows = read_csv(rel)
        for line, row in rows:
            add(rel, line, "emotion", row["emotion"], "concept")

    _, rows = read_csv("compound_emotions.csv")
    for line, row in rows:
        for part in row["components"].split(","):
            if part.strip():
                add("compound_emotions.csv", line, "components", part.strip(), "reference")
        if row["Closest word"].strip():
            add("compound_emotions.csv", line, "Closest word", row["Closest word"].strip(), "reference")

    seen = OrderedDict()
    with zipfile.ZipFile(SOURCES / NRC_ZIP) as archive, archive.open(NRC_MEMBER) as handle:
        for number, raw_line in enumerate(handle, start=1):
            parts = raw_line.decode("utf-8").rstrip("\n").split("\t")
            if len(parts) == 3 and parts[1] not in seen:
                seen[parts[1]] = number
    for category, number in seen.items():
        add(f"{NRC_ZIP}:{NRC_MEMBER}", number, "category (first occurrence)", category, "category")

    return occ


# --------------------------------------------------------------------------
# Build tables
# --------------------------------------------------------------------------

def dataset_references():
    """Dataset label -> original reference recorded in sources/datasets.csv."""
    _, rows = read_csv(DATASETS_CSV)
    return {row["dataset_label"].strip(): row["dataset_source"].strip() for _, row in rows
            if not is_placeholder(row["dataset_source"])}


def build():
    occurrences = collect_occurrences()

    # --- concepts (first-seen order = source priority; display form = first raw form) ---
    concepts = OrderedDict()
    for o in occurrences:
        if o["role"] != "concept":
            continue
        key = label_key(o["raw"])
        if key not in concepts:
            concepts[key] = {"key": key, "id": concept_id(key), "name": o["raw"].strip()}

    ids = defaultdict(list)
    for c in concepts.values():
        ids[c["id"]].append(c["key"])
    collisions = {k: v for k, v in ids.items() if len(v) > 1}
    if collisions:
        raise SystemExit(f"Concept-ID collision, refusing to build: {collisions}")

    # --- definitions: concept key -> source -> [(definition, source reference)] ---
    ds_refs = dataset_references()
    entries = defaultdict(lambda: defaultdict(list))
    for header, rel, def_col, ref_col, dataset in DEFINITION_SOURCES:
        _, rows = read_csv(rel)
        for _, row in rows:
            text = row.get(def_col, "")
            text = "" if is_placeholder(text) else text
            if ref_col:
                ref = row.get(ref_col, "")
                ref = "" if is_placeholder(ref) else ref
            else:  # dataset definitions: provenance is the dataset's reference in datasets.csv
                ref = ds_refs.get(dataset, "") if text else ""
            if not text and not ref:
                continue
            slot = entries[label_key(row["emotion_label"])][header]
            if (text, ref) not in slot:
                slot.append((text, ref))
    # A reference recorded without a definition is redundant if that exact reference
    # already accompanies a definition for the same concept and source.
    for by_source in entries.values():
        for header, slot in by_source.items():
            with_text = {r for t, r in slot if t}
            by_source[header] = [(t, r) for t, r in slot if t or r not in with_text]

    # --- assemble ---
    headers = ["Emotion"]
    pairs = []
    for header, *_ in DEFINITION_SOURCES:
        n = max([len(entries[k].get(header, [])) for k in concepts] + [1])
        for i in range(1, n + 1):
            name = header if i == 1 else f"{header} ({i})"
            headers += [f"{name} definition", f"{name} source"]
            pairs.append((header, i))

    ordered = sorted(concepts.values(), key=lambda c: (c["name"].casefold(), c["id"]))
    dict_rows = [headers]
    for c in ordered:
        row = [c["name"]]
        for header, i in pairs:
            slot = entries[c["key"]].get(header, [])
            row += list(slot[i - 1]) if len(slot) >= i else ["", ""]
        dict_rows.append(row)

    catalogue = [["Emotion", "Concept ID"]] + [[c["name"], c["id"]] for c in ordered]

    write_ods(DICTIONARY_PATH, [("Dictionary", dict_rows, [4.5] + [9.0, 6.0] * len(pairs), True)])
    write_ods(CATALOGUE_PATH, [("Catalogue", catalogue, [5.0, 5.0], True)])

    print(f"Concepts: {len(ordered)}")
    print(f"Definition cells: {sum(1 for r in dict_rows[1:] for v in r[1::2] if v)}")
    print(f"Source cells: {sum(1 for r in dict_rows[1:] for v in r[2::2] if v)}")
    print(f"Wrote {DICTIONARY_PATH.relative_to(SOURCES.parent)}")
    print(f"Wrote {CATALOGUE_PATH.relative_to(SOURCES.parent)}")


# --------------------------------------------------------------------------
# Minimal ODS writer (OpenDocument 1.2 spreadsheet)
# --------------------------------------------------------------------------

NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
      'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
      'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
      'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
      'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
      'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0" '
      'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"')


def text_xml(value: str) -> str:
    """Encode a string for <text:p> so that every character survives (spaces, tabs, newlines)."""
    out = []
    for i, line in enumerate(value.split("\n")):
        if i:
            out.append("<text:line-break/>")
        for j, chunk in enumerate(line.split("\t")):
            if j:
                out.append("<text:tab/>")
            escaped = escape(chunk)

            def spaces(match, length=len(escaped)):
                run = len(match.group(0))
                if match.start() == 0 or match.end() == length:  # leading/trailing: all explicit
                    return f'<text:s text:c="{run}"/>'
                return " " if run == 1 else f' <text:s text:c="{run - 1}"/>'

            out.append(re.sub(r" +", spaces, escaped))
    return "".join(out)


def cell_xml(value, style=None) -> str:
    style_attr = f' table:style-name="{style}"' if style else ""
    if isinstance(value, int):
        return f'<table:table-cell{style_attr} office:value-type="float" office:value="{value}"><text:p>{value}</text:p></table:table-cell>'
    if value == "" or value is None:
        return f"<table:table-cell{style_attr}/>"
    return f'<table:table-cell{style_attr} office:value-type="string"><text:p>{text_xml(str(value))}</text:p></table:table-cell>'


def write_ods(path: Path, sheets):
    col_styles, body = [], []
    for s_index, (name, rows, widths, header) in enumerate(sheets):
        width_count = max(len(r) for r in rows)
        widths = (list(widths) + [widths[-1]] * width_count)[:width_count]
        cols = []
        for c_index, w in enumerate(widths):
            sname = f"co{s_index}_{c_index}"
            col_styles.append(f'<style:style style:name="{sname}" style:family="table-column">'
                              f'<style:table-column-properties style:column-width="{w}cm"/></style:style>')
            cols.append(f'<table:table-column table:style-name="{sname}" table:default-cell-style-name="body"/>')
        lines = [f'<table:table table:name="{escape(name)}">', "".join(cols)]
        for r_index, row in enumerate(rows):
            style = "head" if header and r_index == 0 else None
            cells = "".join(cell_xml(v, style) for v in row)
            lines.append(f"<table:table-row>{cells}</table:table-row>")
        lines.append("</table:table>")
        body.append("".join(lines))

    content = (f'<?xml version="1.0" encoding="UTF-8"?>\n<office:document-content {NS} office:version="1.2">'
               "<office:automatic-styles>" + "".join(col_styles) +
               '<style:style style:name="head" style:family="table-cell">'
               '<style:table-cell-properties fo:background-color="#dde4ee" fo:wrap-option="wrap" style:vertical-align="top"/>'
               '<style:text-properties fo:font-weight="bold"/></style:style>'
               '<style:style style:name="body" style:family="table-cell">'
               '<style:table-cell-properties fo:wrap-option="wrap" style:vertical-align="top"/></style:style>'
               "</office:automatic-styles><office:body><office:spreadsheet>" + "".join(body) +
               "</office:spreadsheet></office:body></office:document-content>")

    freeze = []
    for name, rows, widths, header in sheets:
        if not header:
            continue
        items = {"HorizontalSplitMode": ("short", 2), "VerticalSplitMode": ("short", 2),
                 "HorizontalSplitPosition": ("int", 1), "VerticalSplitPosition": ("int", 1),
                 "ActiveSplitRange": ("short", 2), "PositionLeft": ("int", 0), "PositionRight": ("int", 1),
                 "PositionTop": ("int", 0), "PositionBottom": ("int", 1)}
        freeze.append(f'<config:config-item-map-entry config:name="{escape(name)}">' + "".join(
            f'<config:config-item config:name="{k}" config:type="{t}">{v}</config:config-item>'
            for k, (t, v) in items.items()) + "</config:config-item-map-entry>")
    settings = (f'<?xml version="1.0" encoding="UTF-8"?>\n<office:document-settings {NS} office:version="1.2">'
                '<office:settings><config:config-item-set config:name="ooo:view-settings">'
                '<config:config-item-map-indexed config:name="Views"><config:config-item-map-entry>'
                '<config:config-item config:name="ViewId" config:type="string">view1</config:config-item>'
                '<config:config-item-map-named config:name="Tables">' + "".join(freeze) +
                "</config:config-item-map-named></config:config-item-map-entry></config:config-item-map-indexed>"
                "</config:config-item-set></office:settings></office:document-settings>")
    styles = (f'<?xml version="1.0" encoding="UTF-8"?>\n<office:document-styles {NS} office:version="1.2">'
              "<office:styles/></office:document-styles>")
    meta = (f'<?xml version="1.0" encoding="UTF-8"?>\n<office:document-meta {NS} office:version="1.2">'
            "<office:meta><meta:generator>sources/emotions/build_emotion_tables.py</meta:generator></office:meta>"
            "</office:document-meta>")
    manifest = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">'
                '<manifest:file-entry manifest:full-path="/" manifest:version="1.2" '
                'manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/>'
                '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
                '<manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>'
                '<manifest:file-entry manifest:full-path="settings.xml" manifest:media-type="text/xml"/>'
                '<manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>'
                "</manifest:manifest>")

    def put(archive, name, data, compress=zipfile.ZIP_DEFLATED):
        info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = compress
        archive.writestr(info, data.encode("utf-8"))

    with zipfile.ZipFile(path, "w") as archive:
        put(archive, "mimetype", "application/vnd.oasis.opendocument.spreadsheet", zipfile.ZIP_STORED)
        put(archive, "META-INF/manifest.xml", manifest)
        put(archive, "content.xml", content)
        put(archive, "styles.xml", styles)
        put(archive, "settings.xml", settings)
        put(archive, "meta.xml", meta)


if __name__ == "__main__":
    build()
