"""Independently verify emotion_dictionary.ods and emotion_catalogue.ods.

This script does not import the builder. It re-reads the raw files in sources/,
opens both ODS files with headless LibreOffice (exporting every sheet to CSV),
and compares what LibreOffice reads back against the raw sources: every
definition and every available source reference must be present verbatim,
in the right concept row and the right (definition, source) column pair.

Usage (from the repository root):
    python3 sources/emotions/verify_emotion_tables.py

Exit code 0 = all checks passed.
"""

from __future__ import annotations

import csv
import re
import shutil
import subprocess
import sys
import tempfile
import xml.dom.minidom
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = HERE.parent
DICT_ODS = HERE / "emotion_dictionary.ods"
CAT_ODS = HERE / "emotion_catalogue.ods"

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def key(label):
    return re.sub(r"\s+", " ", label.replace("_", " ").strip()).casefold()


def raw_rows(rel):
    with open(SOURCES / rel, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        out = []
        for row in reader:
            out.append((reader.line_num, dict(zip(header, row))))
        return out


# ---------------------------------------------------------------- raw sources
LABEL_COLUMNS = [("emotion_definitions.csv", "emotion_label")] + \
    [(f"datasets/{d}/emotion_definitions.csv", "emotion_label") for d in ["affectnet", "emoset", "emotic", "goemotions"]] + \
    [("compound_emotions.csv", "emotion_label")] + \
    [(f"models/{m}/standard_model.csv", "emotion") for m in ["circumplex", "pad"]]

raw_concept_occ = []  # (file, line, column, raw)
for rel, col in LABEL_COLUMNS:
    for line, row in raw_rows(rel):
        raw_concept_occ.append((rel, line, col, row[col]))
for line, row in raw_rows("discrete_model_overview.csv"):
    for part in row["emotion_labels"].split(","):
        if part.strip():
            raw_concept_occ.append(("discrete_model_overview.csv", line, f"emotion_labels ({row['model_label']})", part.strip()))

DEF_SOURCES = {  # source -> (file, definition column, reference column or None, dataset label)
    "APA": ("emotion_definitions.csv", "apa_definition", "apa_definition_source", None),
    "Cambridge": ("emotion_definitions.csv", "cambridge_definition", "cambridge_definition_source", None),
    "Oxford": ("emotion_definitions.csv", "oxford_definition", "oxford_definition_source", None),
    "Merriam-Webster": ("emotion_definitions.csv", "merriam-webster_definition", "merriam-webster_definition_source", None),
    "WordNet 3.0 (via SentiWordNet)": ("emotion_definitions.csv", "sentiwordnet_definition", "sentiwordnet_definition_source", None),
    "EMOTIC": ("datasets/emotic/emotion_definitions.csv", "emotic_definition", None, "emotic"),
    "AffectNet": ("datasets/affectnet/emotion_definitions.csv", "affectnet_definition", None, "affectnet"),
    "EmoSet": ("datasets/emoset/emotion_definitions.csv", "emoset_definition", None, "emoset"),
    "GoEmotions": ("datasets/goemotions/emotion_definitions.csv", "goemotions_definition", None, "goemotions"),
}
EMPTY = {"", "-"}
ds_ref = {r["dataset_label"].strip(): r["dataset_source"].strip() for _, r in raw_rows("datasets.csv")}
raw_defs = []  # (concept key, source, definition text, file, line)
raw_refs = []  # (concept key, source, reference text, file, line)
for source, (rel, dcol, rcol, ds) in DEF_SOURCES.items():
    for line, row in raw_rows(rel):
        k = key(row["emotion_label"])
        if row[dcol].strip() not in EMPTY:
            raw_defs.append((k, source, row[dcol], rel, line))
        if rcol and row[rcol].strip() not in EMPTY:
            raw_refs.append((k, source, row[rcol], rel, line))
        elif not rcol and row[dcol].strip() not in EMPTY and ds_ref.get(ds, "").strip() not in EMPTY:
            raw_refs.append((k, source, ds_ref[ds].strip(), f"datasets.csv ({ds})", line))
def_ref_pairs = []  # (concept key, source, definition, reference recorded with it in the same row)
for source, (rel, dcol, rcol, ds) in DEF_SOURCES.items():
    for line, row in raw_rows(rel):
        if row[dcol].strip() in EMPTY:
            continue
        ref = (row[rcol] if row[rcol].strip() not in EMPTY else "") if rcol else \
              (ds_ref.get(ds, "").strip() if ds_ref.get(ds, "").strip() not in EMPTY else "")
        def_ref_pairs.append((key(row["emotion_label"]), source, row[dcol], ref))

# ------------------------------------------------------------- ODS structure
for path in (DICT_ODS, CAT_ODS):
    try:
        with zipfile.ZipFile(path) as z:
            first = z.infolist()[0]
            ok = (first.filename == "mimetype" and first.compress_type == zipfile.ZIP_STORED and
                  z.read("mimetype") == b"application/vnd.oasis.opendocument.spreadsheet" and z.testzip() is None)
            for name in z.namelist():
                if name.endswith(".xml"):
                    xml.dom.minidom.parseString(z.read(name))
        check(f"{path.name}: valid ODF package (mimetype first/stored, CRC ok, XML well-formed)", ok)
    except Exception as exc:  # noqa: BLE001
        check(f"{path.name}: valid ODF package", False, repr(exc))

# ------------------------------------------------------- open with LibreOffice
soffice = shutil.which("soffice") or shutil.which("libreoffice")
work = Path(tempfile.mkdtemp(prefix="emotion_ods_verify_"))
sheets = {}
for path, expected in ((DICT_ODS, ["Dictionary"]),
                       (CAT_ODS, ["Catalogue"])):
    cmd = [soffice, f"-env:UserInstallation=file://{work}/profile", "--headless", "--convert-to",
           "csv:Text - txt - csv (StarCalc):44,34,76,1,,0,false,true,false,false,false,-1",
           "--outdir", str(work / "out"), str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    found = []
    for sheet in expected:
        out = work / "out" / f"{path.stem}-{sheet}.csv"
        if out.exists():
            with open(out, newline="", encoding="utf-8") as handle:
                sheets[(path.name, sheet)] = list(csv.reader(handle))
            found.append(sheet)
    check(f"{path.name}: opened by LibreOffice headless, all sheets exported", proc.returncode == 0 and found == expected,
          f"sheets read back: {found}")

with zipfile.ZipFile(DICT_ODS) as z:
    tables = re.findall(r'<table:table table:name="([^"]*)"', z.read("content.xml").decode())
check("emotion_dictionary.ods contains exactly one sheet, 'Dictionary'", tables == ["Dictionary"], f"sheets: {tables}")

D = sheets[("emotion_dictionary.ods", "Dictionary")]
CAT = sheets[("emotion_catalogue.ods", "Catalogue")]
head = D[0]
body = D[1:]

# ------------------------------------------------------------- inventory
expected_keys = {key(r[3]) for r in raw_concept_occ}
dict_keys = [key(r[0]) for r in body]
check("Column A header is 'Emotion'", head[0] == "Emotion")
check("One row per concept (no duplicate concepts in dictionary)", len(dict_keys) == len(set(dict_keys)),
      f"{len(dict_keys)} rows")
check("Every emotion label from the source label columns is a dictionary concept", set(dict_keys) == expected_keys,
      f"expected {len(expected_keys)}, missing {sorted(expected_keys - set(dict_keys))}, extra {sorted(set(dict_keys) - expected_keys)}")
names = [r[0] for r in body]
check("Dictionary sorted alphabetically (case-insensitive)", names == sorted(names, key=str.casefold))

# ------------------------------------------------------------- column layout
pairs = defaultdict(list)  # source -> [(definition column index, source column index)]
layout_ok = len(head) % 2 == 1
for i in range(1, len(head), 2):
    m = re.fullmatch(r"(.+?)(?: \((\d+)\))? definition", head[i])
    m2 = re.fullmatch(r"(.+?)(?: \((\d+)\))? source", head[i + 1]) if i + 1 < len(head) else None
    if not (m and m2 and m.group(1) == m2.group(1) and m.group(2) == m2.group(2) and m.group(1) in DEF_SOURCES):
        layout_ok = False
        continue
    pairs[m.group(1)].append((i, i + 1))
check("Columns after A are adjacent (definition, source) pairs, one pair per definition source, nothing else",
      layout_ok and list(pairs) == list(DEF_SOURCES) and all(len(v) == 1 for v in pairs.values()),
      f"{len(head)} columns: " + ", ".join(head[1::2]))
check("Every row has the same number of cells as the header (no extra columns)",
      all(len(r) == len(head) for r in body))

# ------------------------------------------------------------- definitions and provenance
row_of = {key(r[0]): r for r in body}
lost = [d for d in raw_defs if d[2] not in [row_of[d[0]][di] for di, _ in pairs[d[1]]]]
check("Every source definition appears verbatim in its concept's row, in its source's definition column", not lost,
      f"{len(raw_defs)} definition cells checked; lost/altered: {[(d[0], d[1], d[3], d[4]) for d in lost]}")
present = [(key(r[0]), s, r[di]) for r in body for s, ps in pairs.items() for di, _ in ps if r[di] != ""]
check("No definition text in the dictionary that is not in the sources (and no duplicates)",
      Counter(present) == Counter({(d[0], d[1], d[2]) for d in raw_defs}),
      f"{len(present)} non-empty definition cells")
lost_ref = [r for r in raw_refs if r[2] not in [row_of[r[0]][si] for _, si in pairs[r[1]]]]
check("Every available source reference appears verbatim in its concept's row, in its source's source column",
      not lost_ref, f"{len(raw_refs)} reference cells checked; lost/altered: {[(r[0], r[1], r[3], r[4]) for r in lost_ref]}")
present_ref = {(key(r[0]), s, r[si]) for r in body for s, ps in pairs.items() for _, si in ps if r[si] != ""}
check("No source reference in the dictionary that is not in the sources",
      present_ref == {(r[0], r[1], r[2]) for r in raw_refs}, f"{len(present_ref)} distinct non-empty source cells")
paired = all(any(row_of[k][di] == d and row_of[k][si] == ref for di, si in pairs[s]) for k, s, d, ref in def_ref_pairs)
check("Each definition sits next to the reference recorded with it in the same source row", paired,
      f"{len(def_ref_pairs)} definition/reference pairs checked")
placeholders = [(r[0], c) for r in body for c in r[1:] if c.strip() == "-"]
check("Placeholder '-' cells are left blank", not placeholders, f"{len(placeholders)} found")

# ------------------------------------------------------------- catalogue
check("Catalogue header is ['Emotion', 'Concept ID']", CAT[0] == ["Emotion", "Concept ID"])
check("Catalogue and dictionary have identical concept inventories (names, order)",
      [r[0] for r in CAT[1:]] == names, f"{len(CAT) - 1} rows")
cat_ids = [r[1] for r in CAT[1:]]
check("Catalogue concept IDs unique and non-empty", len(set(cat_ids)) == len(cat_ids) and all(cat_ids))
check("Catalogue contains no definitions (two columns only)", all(len(r) == 2 for r in CAT))

shutil.rmtree(work, ignore_errors=True)
print(f"\n{sum(RESULTS)}/{len(RESULTS)} checks passed.")
sys.exit(0 if all(RESULTS) else 1)
