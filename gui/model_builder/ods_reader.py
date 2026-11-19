"""Read the cell texts of one sheet of an ODS file (standard library only, read-only).

Handles what LibreOffice and other writers produce: repeated rows/columns, covered cells, several
paragraphs per cell, and the text:s / text:tab / text:line-break whitespace elements. Trailing empty
cells and rows are dropped.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
T = "{%s}" % NS["table"]
X = "{%s}" % NS["text"]
O = "{%s}" % NS["office"]
MAX_REPEAT = 10000   # guard against a "repeat to the end of the sheet" filler row/column


def _text(el) -> str:
    parts = [el.text or ""]
    for child in el:
        if child.tag == X + "s":
            parts.append(" " * int(child.get(X + "c", "1")))
        elif child.tag == X + "tab":
            parts.append("\t")
        elif child.tag == X + "line-break":
            parts.append("\n")
        else:
            parts.append(_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _cell_text(cell, values: bool = False) -> str:
    if values and cell.get(O + "value-type") in ("float", "percentage", "currency"):
        return cell.get(O + "value")   # the stored number, not its displayed (possibly rounded) text
    return "\n".join(_text(p) for p in cell.findall("text:p", NS))


def read_sheet(path, sheet: str, values: bool = False) -> list[list[str]]:
    """Cell texts row by row. values=True returns numeric cells' stored office:value instead of their text."""
    with zipfile.ZipFile(Path(path)) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    table = next((t for t in root.iter(T + "table") if t.get(T + "name") == sheet), None)
    if table is None:
        raise KeyError(f"{Path(path).name} has no sheet named {sheet!r}")
    rows = []
    for row in table.iter(T + "table-row"):
        cells = []
        for cell in row:
            if cell.tag not in (T + "table-cell", T + "covered-table-cell"):
                continue
            repeat = min(int(cell.get(T + "number-columns-repeated", "1")), MAX_REPEAT)
            cells.extend([_cell_text(cell, values)] * repeat)
        while cells and cells[-1] == "":
            cells.pop()
        repeat = min(int(row.get(T + "number-rows-repeated", "1")), MAX_REPEAT)
        rows.extend([list(cells) for _ in range(repeat)] if cells else [[]] * repeat)
    while rows and not rows[-1]:
        rows.pop()
    return rows


def sheet_names(path) -> list[str]:
    with zipfile.ZipFile(Path(path)) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    return [t.get(T + "name") for t in root.iter(T + "table")]
