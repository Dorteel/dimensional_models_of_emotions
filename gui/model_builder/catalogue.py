"""Emotion catalogue and dictionary for the Create Domain Model tab (read-only).

  emotions/emotion_catalogue.ods   sheet "Catalogue":  Emotion | Concept ID
  emotions/emotion_dictionary.ods  sheet "Dictionary": Emotion | <Source> definition | <Source> source | ...

The catalogue is the list of selectable emotions. The dictionary supplies the definitions a user may copy
into a prototype (verbatim, with their source); it is joined to the catalogue by emotion name.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .ods_reader import read_sheet

REPO = Path(__file__).resolve().parents[2]
CATALOGUE = REPO / "emotions" / "emotion_catalogue.ods"
DICTIONARY = REPO / "emotions" / "emotion_dictionary.ods"


def _key(label: str) -> str:
    return re.sub(r"\s+", " ", label.replace("_", " ").strip()).casefold()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_catalogue(catalogue: Path = CATALOGUE, dictionary: Path = DICTIONARY) -> dict:
    rows = read_sheet(catalogue, "Catalogue")
    if not rows or rows[0][:2] != ["Emotion", "Concept ID"]:
        raise ValueError(f"{catalogue}: expected the header 'Emotion | Concept ID'")
    definitions = {}
    if dictionary.exists():
        drows = read_sheet(dictionary, "Dictionary")
        head = drows[0] if drows else []
        for r in drows[1:]:
            r = r + [""] * (len(head) - len(r))
            defs = []
            for i in range(1, len(head) - 1, 2):
                if r[i] != "" and head[i].endswith(" definition"):
                    defs.append({"source": head[i][: -len(" definition")], "text": r[i], "reference": r[i + 1]})
            definitions[_key(r[0])] = defs
    emotions = []
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        name, concept_id = r[0], (r[1] if len(r) > 1 else "")
        emotions.append({"name": name, "concept_id": concept_id, "definitions": definitions.get(_key(name), [])})
    return {
        "emotions": emotions,
        "sources": {
            "catalogue": {"path": str(catalogue.relative_to(REPO)), "sha256": _sha(catalogue)},
            "dictionary": {"path": str(dictionary.relative_to(REPO)), "sha256": _sha(dictionary)}
            if dictionary.exists() else None,
        },
    }
