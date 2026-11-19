"""ODS-to-YAML export support used by domain validation.

Retains the established exporter and LibreOffice helpers without source-model
regeneration. Run: python3 domains/ods_export.py --export <model.ods>
"""
from __future__ import annotations

import contextlib
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "domains" / "domain_model_template.ods"
MACRO_DOC = ROOT / "domains" / "create_custom_domain_model.ods"
UNKNOWN = "unknown"
DIM_ROWS = range(9, 29)
PROTO_ROWS = range(33, 63)
PROTO_NOTES_COL = 12
MAX_DIMS = 9

def basic_trim(text: str) -> str:
    return text.strip(" ")



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
    out = ods.with_name(f"{name}.yaml")
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out}")



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
    else:
        raise SystemExit("usage: ods_export.py --export <edited DomainModel .ods>")
