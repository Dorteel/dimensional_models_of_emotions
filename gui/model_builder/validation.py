"""Validation of a domain model entered in the Create Domain Model tab.

The rules are those of the existing builder workbook (domains/create_custom_domain_model.ods, Basic module
Module1): SaveModel, AddDimension, AddPrototype and BuildDomainYAML, plus the template's capacity (9
dimensions, 30 prototypes). They are checked here first so the form can point at the offending field; the
YAML itself is still produced by the macro's BuildDomainYAML when saving (see office_save.py), which applies
the same rules again.

Input (JSON from the form):
  {name, description, notes,
   dimensions: [{name, definition, notes, min, max, circular: "yes"|"no"}],
   emotions:   [{name, concept_id?: str, definition, notes, coordinates: {<dimension index or id>: value}}]}

Coordinates are keyed by the dimension's position ("0", "1", …) so renaming a dimension in the form keeps
its values; the normalised model keys them by dimension ID, as the YAML does.

Output: {"model": normalised model in the YAML schema, "model_id", "errors": [...], "warnings": [...]}
with every message as {"field": "dimensions.0.min", "message": "..."}.
"""

from __future__ import annotations

import math

MAX_DIMENSIONS = 9     # DomainModel rows 10-29, coordinate columns D-L
MAX_PROTOTYPES = 30    # DomainModel rows 34-63
SIGNIFICANT_DIGITS = 15


def safe_id(label: str) -> str:
    """Python mirror of the macro's SafeID (lowercase; a-z 0-9 _ kept; space and '-' become '_')."""
    out = []
    for ch in str(label).strip(" ").lower():
        if ch in "abcdefghijklmnopqrstuvwxyz0123456789_":
            out.append(ch)
        elif ch in " -":
            out.append("_")
    return "".join(out)


def basic_trim(text) -> str:
    return str(text or "").strip(" ")


def representable(value: float) -> bool:
    """The macro's YAMLNumber refuses values that do not survive LibreOffice's 15-significant-digit
    decimal conversion (e.g. 1/3 or 0.12345678901234566) instead of rounding them silently."""
    return float(f"{value:.{SIGNIFICANT_DIGITS}g}") == value


def _number(raw):
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
    else:
        text = str(raw).strip()
        if text == "":
            return None
        try:
            value = float(text)
        except ValueError:
            return None
    return value if math.isfinite(value) else None


def validate(form: dict, catalogue_ids: set[str] | None = None) -> dict:
    errors, warnings = [], []
    err = lambda field, message: errors.append({"field": field, "message": message})  # noqa: E731
    warn = lambda field, message: warnings.append({"field": field, "message": message})  # noqa: E731

    # ---------------------------------------------------------------- Step 1: model (SaveModel)
    name = basic_trim(form.get("name"))
    model_id = safe_id(name)
    if not name:
        err("name", "Please enter a domain model name.")
    elif not model_id:
        err("name", "The model name must contain letters or digits to form an identifier.")

    # ---------------------------------------------------------------- Step 2: dimensions (AddDimension)
    dims_in = form.get("dimensions") or []
    dims = []
    if not dims_in:
        err("dimensions", "Please add at least one quality dimension.")
    if len(dims_in) > MAX_DIMENSIONS:
        err("dimensions", f"This version supports up to {MAX_DIMENSIONS} dimensions.")
    seen_names, seen_ids = {}, {}
    for i, d in enumerate(dims_in):
        f = f"dimensions.{i}"
        dname, definition = basic_trim(d.get("name")), basic_trim(d.get("definition"))
        did = safe_id(dname)
        if not dname:
            err(f"{f}.name", "Dimension name is required.")
        elif not did:
            err(f"{f}.name", "The dimension name must contain letters or digits to form an identifier.")
        elif dname.lower() in seen_names:
            err(f"{f}.name", f"A dimension with this name already exists (dimension {seen_names[dname.lower()] + 1}).")
        elif did in seen_ids:
            err(f"{f}.name", f"Duplicate dimension ID '{did}' (also dimension {seen_ids[did] + 1}).")
        seen_names.setdefault(dname.lower(), i)
        if did:
            seen_ids.setdefault(did, i)
        if not definition:
            err(f"{f}.definition", "Dimension definition/description is required.")
        lo, hi = _number(d.get("min")), _number(d.get("max"))
        if lo is None:
            err(f"{f}.min", "Minimum must be a number.")
        if hi is None:
            err(f"{f}.max", "Maximum must be a number.")
        if lo is not None and hi is not None and lo >= hi:
            err(f"{f}.max", "Minimum must be lower than maximum.")
        for key, v in (("min", lo), ("max", hi)):
            if v is not None and not representable(v):
                err(f"{f}.{key}", "This value exceeds the lossless decimal precision of ODS (15 significant digits).")
        circular = basic_trim(d.get("circular")).lower()
        if circular not in ("yes", "no"):
            err(f"{f}.circular", "Circular must be Yes or No.")
        dims.append({"id": did, "name": dname, "definition": definition, "notes": str(d.get("notes") or ""),
                     "min": lo, "max": hi, "circular": circular == "yes"})

    # ---------------------------------------------------------------- Step 3: prototypes (AddPrototype)
    emo_in = form.get("emotions") or []
    emotions = []
    if len(emo_in) > MAX_PROTOTYPES:
        err("emotions", f"This version supports up to {MAX_PROTOTYPES} emotions.")
    seen_names, seen_ids = {}, {}
    for j, e in enumerate(emo_in):
        f = f"emotions.{j}"
        ename, definition = basic_trim(e.get("name")), basic_trim(e.get("definition"))
        concept = basic_trim(e.get("concept_id"))
        eid = concept if concept else safe_id(ename)
        if not ename:
            err(f"{f}.name", "Emotion name is required.")
        elif not eid:
            err(f"{f}.name", "The emotion name must contain letters or digits to form an identifier.")
        elif ename.lower() in seen_names:
            err(f"{f}.name", f"That emotion already has a prototype in this model (emotion {seen_names[ename.lower()] + 1}).")
        elif eid in seen_ids:
            err(f"{f}.name", f"Duplicate emotion ID '{eid}' (also emotion {seen_ids[eid] + 1}).")
        seen_names.setdefault(ename.lower(), j)
        if eid:
            seen_ids.setdefault(eid, j)
        if not definition:
            err(f"{f}.definition", "Emotion definition is required.")
        if concept and catalogue_ids is not None and concept not in catalogue_ids:
            err(f"{f}.name", f"Concept ID '{concept}' is not in emotions/emotion_catalogue.ods.")
        if not concept and ename:
            warn(f"{f}.name", f"'{ename}' is a new emotion, not in the catalogue. The model can be saved, but "
                              "ontology population requires every emotion to be in emotions/emotion_dictionary.ods.")
        raw = e.get("coordinates") or {}
        known = {str(i) for i in range(len(dims))} | {d["id"] for d in dims if d["id"]}
        extra = [k for k in raw if str(k) not in known and str(raw[k]).strip() != ""]
        if extra:
            err(f"{f}.coordinates", f"Coordinates for undefined dimensions: {', '.join(map(str, extra))}.")
        coords = {}
        for i, d in enumerate(dims):
            value = _number(raw.get(str(i), raw.get(d["id"])))
            field = f"{f}.coordinates.{i}"
            label = d["name"] or f"dimension {i + 1}"
            if value is None:
                err(field, f"A numeric value for {label} is required.")
                continue
            if d["min"] is not None and d["max"] is not None and not (d["min"] <= value <= d["max"]):
                err(field, f"Coordinate is outside the permitted range of {label} ({_fmt(d['min'])} to {_fmt(d['max'])}).")
            if not representable(value):
                err(field, "This value exceeds the lossless decimal precision of ODS (15 significant digits).")
            coords[d["id"]] = value
        emotions.append({"id": eid, "name": ename, "definition": definition, "notes": str(e.get("notes") or ""),
                         "coordinates": coords, "concept_id": concept or None})

    model = {"schema_version": "1.0", "id": model_id, "name": name,
             "description": str(form.get("description") or ""), "notes": str(form.get("notes") or ""),
             "dimensions": dims,
             "emotions": [{k: v for k, v in e.items() if k != "concept_id"} for e in emotions]}
    return {"model": model, "model_id": model_id, "errors": errors, "warnings": warnings,
            "catalogue_links": {e["id"]: e["concept_id"] for e in emotions if e["concept_id"]}}


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else repr(v)
