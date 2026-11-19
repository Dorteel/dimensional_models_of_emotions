"""Save a domain model as domains/<model_id>/<model_id>.{yaml,ods} with the builder workbook's own macros.

Runs under a Python that has LibreOffice's UNO bridge (the system python3), as a subprocess of the GUI
server. Input: one JSON object on stdin; output: one JSON object on stdout.

  {"model": <validated model, YAML schema>, "overwrite": bool,
   "domains_dir": ".../domains", "builder": ".../create_custom_domain_model.ods",
   "template": ".../domain_model_template.ods"}

Steps (no second exporter: every format decision is the workbook's):
  1. Copy the builder workbook to a scratch folder and open the copy (macros enabled; never saved).
  2. Fill its DomainModel sheet exactly where the builder's Main-form actions write (B4:B6 model,
     rows 10-29 dimensions + row 32 coordinate headers, rows 34-63 prototypes).
  3. YAML  = the workbook's BuildDomainYAML(DomainModel) — the function behind SAVE DOMAIN MODEL.
     ODS   = domain_model_template.ods with only its DomainModel sheet, filled by the workbook's
             CopyDomainModelValues — as SAVE DOMAIN MODEL does.
  4. Check: the YAML loads back as exactly the validated model, and re-exporting the staged ODS with the
     established Python exporter (domains/ods_export.py, export_yaml) reproduces the YAML byte for byte.
  5. Install the pair like SAVE DOMAIN MODEL: write "<file>.saving", move existing files to
     "<file>.previous", move the new pair in, delete the backups; on any failure restore the previous pair.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "domains"))

import ods_export as ox  # noqa: E402  (LibreOffice session helpers + established ODS->YAML exporter)
import yaml  # noqa: E402

CLEAR = 23   # VALUE | DATETIME | STRING | FORMULA, as the builder tests use


class SaveError(Exception):
    pass


def fill_domain_model(sheet, model):
    for address in ("B4:B6", "A10:M29", "D32:L32", "A34:M63"):
        sheet.getCellRangeByName(address).clearContents(CLEAR)
    sheet.getCellRangeByName("B4").String = model["name"]
    sheet.getCellRangeByName("B5").String = model["description"]
    sheet.getCellRangeByName("B6").String = model["notes"]
    for i, d in enumerate(model["dimensions"]):            # AddDimension: A id, B name, C definition, D min,
        row = ox.DIM_ROWS[i]                               # E max, F circular, G notes; row 32 header
        sheet.getCellByPosition(0, row).String = d["id"]
        sheet.getCellByPosition(1, row).String = d["name"]
        sheet.getCellByPosition(2, row).String = d["definition"]
        sheet.getCellByPosition(3, row).Value = d["min"]
        sheet.getCellByPosition(4, row).Value = d["max"]
        sheet.getCellByPosition(5, row).String = "yes" if d["circular"] else "no"
        sheet.getCellByPosition(6, row).String = d["notes"]
        sheet.getCellByPosition(3 + i, 31).String = d["name"]
    for j, e in enumerate(model["emotions"]):              # AddPrototype: A id, B name, C definition,
        row = ox.PROTO_ROWS[j]                             # D.. coordinates, M notes
        sheet.getCellByPosition(0, row).String = e["id"]
        sheet.getCellByPosition(1, row).String = e["name"]
        sheet.getCellByPosition(2, row).String = e["definition"]
        for i, d in enumerate(model["dimensions"]):
            sheet.getCellByPosition(3 + i, row).Value = e["coordinates"][d["id"]]
        sheet.getCellByPosition(ox.PROTO_NOTES_COL, row).String = e["notes"]


def as_numbers(model):
    """Compare numbers as floats (YAML may load 1 as int)."""
    def norm(x):
        if isinstance(x, bool) or x is None:
            return x
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, dict):
            return {k: norm(v) for k, v in x.items()}
        if isinstance(x, list):
            return [norm(v) for v in x]
        return x
    return norm(model)


def save(request: dict) -> dict:
    model = request["model"]
    domains_dir = Path(request["domains_dir"])
    builder, template = Path(request["builder"]), Path(request["template"])
    if not template.is_file():
        raise SaveError(f"Cannot find the structural template: {template}")
    model_id = model["id"]
    folder = domains_dir / model_id
    yaml_path, ods_path = folder / f"{model_id}.yaml", folder / f"{model_id}.ods"
    stage = {p: p.with_name(p.name + ".saving") for p in (yaml_path, ods_path)}
    backup = {p: p.with_name(p.name + ".previous") for p in (yaml_path, ods_path)}
    if folder.exists() and not folder.is_dir():
        raise SaveError(f"The model destination is not a folder: {folder}")
    if any(p.exists() for p in [*stage.values(), *backup.values()]):
        raise SaveError(f"Temporary files from an earlier save exist in {folder}. Review them before saving again.")
    existing = [p for p in (yaml_path, ods_path) if p.exists()]
    if existing and not request.get("overwrite"):
        raise SaveError("exists: " + ", ".join(str(p) for p in existing))

    with ox.office() as session:
        scratch = session.work / "builder.ods"
        shutil.copyfile(builder, scratch)
        doc = ox.load(session, scratch, MacroExecutionMode=4)
        try:
            provider = doc.getScriptProvider()
            script = lambda name: provider.getScript(  # noqa: E731
                f"vnd.sun.star.script:Standard.Module1.{name}?language=Basic&location=document")
            call = lambda name, *args: script(name).invoke(args, (), ())[0]  # noqa: E731

            # The macro's SafeID decides the identifiers and the folder; the form used the Python mirror.
            if call("SafeID", model["name"]) != model_id:
                raise SaveError(f"Model ID mismatch: SafeID gives {call('SafeID', model['name'])!r}, form gave {model_id!r}")
            for d in model["dimensions"]:
                if call("SafeID", d["name"]) != d["id"]:
                    raise SaveError(f"Dimension ID mismatch for {d['name']!r}")

            sheet = doc.Sheets.getByName("DomainModel")
            fill_domain_model(sheet, model)
            text = call("BuildDomainYAML", sheet)
            if not text:
                raise SaveError("The builder's BuildDomainYAML refused the model (see its validation rules).")
            if as_numbers(yaml.safe_load(text)) != as_numbers(model):
                raise SaveError("The YAML produced by BuildDomainYAML does not match the entered model.")

            model_doc = ox.load(session, template, AsTemplate=True)
            created_folder = False
            try:
                for name in list(model_doc.Sheets.getElementNames()):
                    if name != "DomainModel":
                        model_doc.Sheets.removeByName(name)
                script("CopyDomainModelValues").invoke((sheet, model_doc.Sheets.getByName("DomainModel")), (), ())
                if not folder.exists():
                    folder.mkdir(parents=True)
                    created_folder = True
                staged_ods = session.work / f"{model_id}.ods"          # stored with an .ods name, then staged
                model_doc.storeToURL(ox.uno.systemPathToFileUrl(str(staged_ods)), (ox.prop("FilterName", "calc8"),))
            finally:
                model_doc.close(True)

            # Independent re-export of the stored ODS with the established exporter must give the same YAML.
            macro = lambda name, value: call(name, value)  # noqa: E731
            reexport, errors = ox.export_yaml(session, macro, staged_ods)
            if errors or reexport != text:
                raise SaveError("Re-exporting the new ODS does not reproduce the YAML: " + "; ".join(errors))
        finally:
            doc.close(True)

        # ---------------------------------------------------------------- install the pair
        moved, installed = {}, []
        try:
            shutil.copyfile(staged_ods, stage[ods_path])
            stage[yaml_path].write_text(text, encoding="utf-8", newline="\n")
            for p in (yaml_path, ods_path):
                if p.exists():
                    os.replace(p, backup[p])
                    moved[p] = backup[p]
            if request.get("_test_fail_commit"):
                raise SaveError("Injected commit failure")
            for p in (ods_path, yaml_path):
                os.replace(stage[p], p)
                installed.append(p)
        except Exception:
            for p in installed:
                p.unlink(missing_ok=True)
            for p, b in moved.items():
                os.replace(b, p)
            for s in stage.values():
                s.unlink(missing_ok=True)
            if created_folder and not any(folder.iterdir()):
                folder.rmdir()
            raise
        for b in moved.values():
            b.unlink(missing_ok=True)

    return {"ok": True, "model_id": model_id, "folder": str(folder), "yaml": str(yaml_path), "ods": str(ods_path),
            "yaml_text": text, "replaced": [str(p) for p in moved]}


def main():
    request = json.loads(sys.stdin.read())
    try:
        result = save(request)
    except SaveError as exc:
        result = {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()}
    sys.stdout.write("\n" + json.dumps(result) + "\n")


if __name__ == "__main__":
    main()
