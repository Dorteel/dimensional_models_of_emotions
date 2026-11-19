"""Build dimension ODS tables from domain YAML, using the emotion table layout.

Run from the repository root: python3 dimensions/build_dimension_tables.py
Only the two dimension spreadsheets are written; input files are read-only.
"""

from collections import defaultdict
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
MISSING_DEFINITIONS = {"", "undefined", "no known definitions"}
# The legacy testing workbook contains example prose and a 'dsad' definition.
# It is not a research model; do not promote its text to the official vocabulary.
EXAMPLE_FILES = {"yourdomainmodel.yaml", "yourdomainmodel2.yaml", "testingmodel.yaml"}
NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
}


def tag(prefix, name):
    return f"{{{NS[prefix]}}}{name}"


def read_models(root=ROOT):
    """Discover YAML recursively, including incomplete/draft research models."""
    models = []
    for path in sorted((root / "domains").rglob("*")):
        if path.suffix not in {".yaml", ".yml"}:
            continue
        if "examples" in path.relative_to(root / "domains").parts[:-1] or path.name in EXAMPLE_FILES:
            continue
        model = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(model, dict) or "dimensions" not in model:
            continue  # Non-model YAML is not a vocabulary source.
        if str(model.get("schema_version")) != "1.0" or not isinstance(model["dimensions"], list):
            raise ValueError(f"{path}: expected a standardized version 1.0 Domain Model")
        if not model.get("id") or not model.get("name"):
            raise ValueError(f"{path}: missing model id/name")
        seen = set()
        for dimension in model["dimensions"]:
            if not isinstance(dimension, dict) or any(
                not isinstance(dimension.get(key), str) or not dimension[key].strip() for key in ("id", "name")
            ):
                raise ValueError(f"{path}: every dimension needs an established string id/name")
            if dimension["id"] in seen:
                raise ValueError(f"{path}: duplicate dimension id {dimension['id']!r}")
            seen.add(dimension["id"])
            if dimension.get("definition") is not None and not isinstance(dimension["definition"], str):
                raise ValueError(f"{path}: dimension definitions must be strings or null")
        models.append((path.relative_to(root), model))
    return models


def definition_text(dimension):
    value = dimension.get("definition")
    return "" if value is None or value.strip().casefold() in MISSING_DEFINITIONS else value


def provenance(path, model, dimension):
    """Retain the exact notes in which standardized models document sources."""
    lines = [f"Domain Model: {model['name']} (id: {model['id']})",
             f"YAML: {path.as_posix()}",
             f"Dimension: {dimension['name']} (id: {dimension['id']})"]
    for label, record in (("Dimension", dimension), ("Domain Model", model)):
        # 'notes' is the existing standardized source field. Also retain explicit
        # source strings if a model supplies one, without interpreting its text.
        for key in ("source", "notes"):
            value = record.get(key)
            if value:
                if not isinstance(value, str):
                    raise ValueError(f"{path}: {label} {key} must be text")
                lines.append(f"{label} {key}:\n{value}")
    return "\n".join(lines)


def table_rows(models):
    """One concept per exact ID; one definition/source pair per model file.

    Names never establish identity. For a shared ID with different names, the
    first encountered name labels the row; every original name remains in its
    Source cell. Dictionary rows follow the catalogue's name/ID order.
    """
    concepts = {}
    for _, model in models:
        for dimension in model["dimensions"]:
            concepts.setdefault(dimension["id"], dimension["name"])
    identifiers = sorted(concepts, key=lambda identifier: (concepts[identifier].casefold(), identifier))
    catalogue = [["Dimension", "Dimension ID"]] + [[concepts[i], i] for i in identifiers]
    dictionary = [["Dimension"] + [f"{model['id']} {kind}" for _, model in models
                                    for kind in ("definition", "source")]]
    for identifier in identifiers:
        row = [concepts[identifier]]
        for path, model in models:
            dimension = next((d for d in model["dimensions"] if d["id"] == identifier), None)
            row.extend([definition_text(dimension), provenance(path, model, dimension)] if dimension else ["", ""])
        dictionary.append(row)
    return catalogue, dictionary


def write_ods(reference, sheet_name, rows, destination):
    """Reuse the existing emotion spreadsheet's simple formatting and package."""
    with ZipFile(reference) as archive:
        content = ET.fromstring(archive.read("content.xml"))
        sheet = content.find(f".//{tag('table', 'table')}")
        columns = list(sheet.findall(tag("table", "table-column")))
        sheet.clear()
        sheet.set(tag("table", "name"), sheet_name)
        for index in range(len(rows[0])):
            # Reuse the name column, then repeat the definition/source styles.
            column = columns[0 if index == 0 else 1 + (index - 1) % (len(columns) - 1)]
            sheet.append(deepcopy(column))
        for index, values in enumerate(rows):
            row = ET.SubElement(sheet, tag("table", "table-row"))
            for value in values:
                cell = ET.SubElement(row, tag("table", "table-cell"),
                                     {tag("office", "value-type"): "string"})
                if index == 0:
                    cell.set(tag("table", "style-name"), "head")
                # Explicit ODF whitespace nodes keep tabs and repeated spaces
                # unchanged when LibreOffice reads definitions and provenance.
                paragraph = ET.SubElement(cell, tag("text", "p"))
                for character in value:
                    if character in " \t\n":
                        ET.SubElement(paragraph, tag("text", {" ": "s", "\t": "tab", "\n": "line-break"}[character]))
                    elif len(paragraph):
                        child = paragraph[-1]
                        child.tail = (child.tail or "") + character
                    else:
                        paragraph.text = (paragraph.text or "") + character
        meta = ET.fromstring(archive.read("meta.xml"))
        meta.find(f".//{tag('meta', 'generator')}").text = "dimensions/build_dimension_tables.py"
        replacements = {
            "content.xml": ET.tostring(content, encoding="utf-8", xml_declaration=True),
            "meta.xml": ET.tostring(meta, encoding="utf-8", xml_declaration=True),
        }
        output = BytesIO()
        with ZipFile(output, "w") as target:
            for entry in archive.infolist():
                target.writestr(entry, replacements.get(entry.filename, archive.read(entry.filename)))
    destination.write_bytes(output.getvalue())


def build(root=ROOT, output=None):
    output = output or root / "dimensions"
    models = read_models(root)
    catalogue, dictionary = table_rows(models)
    output.mkdir(parents=True, exist_ok=True)
    for kind, rows in (("catalogue", catalogue), ("dictionary", dictionary)):
        write_ods(root / "emotions" / f"emotion_{kind}.ods", kind.title(), rows,
                  output / f"dimension_{kind}.ods")
    definitions = defaultdict(set)
    for _, model in models:
        for dimension in model["dimensions"]:
            if definition_text(dimension):
                definitions[dimension["id"]].add(definition_text(dimension))
    return models, catalogue, definitions


if __name__ == "__main__":
    models, catalogue, definitions = build()
    print(f"{len(models)} models; {len(catalogue) - 1} dimensions; "
          f"{sum(map(len, definitions.values()))} distinct dimension definitions")
    print("Missing definitions: " + ", ".join(identifier for _, identifier in catalogue[1:] if not definitions[identifier]))
