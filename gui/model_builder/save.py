"""Server-side orchestration of "Save domain model" (runs in the GUI server's Python).

validate -> check destination -> run office_save.py with a Python that has LibreOffice's UNO bridge.

Destination rules (the GUI only writes the model being created):
  * files go to domains/<model_id>/<model_id>.yaml and .ods (model_id = SafeID(name), as the builder does);
  * the reference research models and the non-model folders below are never written by the GUI;
  * an existing domains/<model_id>/ pair is replaced only when the request says overwrite=true, which the
    form sends after an explicit confirmation (as SAVE DOMAIN MODEL asks "Replace the existing model files?").
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from functools import lru_cache
from pathlib import Path

from .catalogue import load_catalogue
from .validation import validate

REPO = Path(__file__).resolve().parents[2]
DOMAINS = REPO / "domains"
BUILDER = DOMAINS / "create_custom_domain_model.ods"
TEMPLATE = DOMAINS / "domain_model_template.ods"
OFFICE_SAVE = Path(__file__).resolve().parent / "office_save.py"
PROTECTED = {"circumplex", "pad", "plutchik_model", "vector_model",          # reference research models
             "examples", "drafts", "yourdomainmodel", "yourdomainmodel2"}    # not active models
_lock = threading.Lock()


@lru_cache(maxsize=1)
def uno_python() -> str | None:
    """A Python interpreter that can import LibreOffice's UNO bridge (usually the system python3)."""
    candidates = [os.environ.get("GUI_UNO_PYTHON"), "/usr/bin/python3", shutil.which("python3"), sys.executable]
    for c in dict.fromkeys(x for x in candidates if x):
        try:
            if subprocess.run([c, "-c", "import uno, yaml"], capture_output=True, timeout=30).returncode == 0:
                return c
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def destination(model_id: str, domains_dir: Path = DOMAINS) -> dict:
    folder = domains_dir / model_id
    files = [folder / f"{model_id}.yaml", folder / f"{model_id}.ods"] if model_id else []
    info = {"folder": _rel(folder), "yaml": _rel(files[0]) if files else None, "ods": _rel(files[1]) if files else None,
            "exists": [_rel(p) for p in files if p.exists()], "protected": model_id in PROTECTED, "problem": None}
    if not model_id:
        info["problem"] = "No model ID yet."
    elif model_id in PROTECTED:
        info["problem"] = f"'{model_id}' is reserved (reference model or non-model folder); choose another name."
    elif folder.exists() and not folder.is_dir():
        info["problem"] = f"domains/{model_id} exists and is not a folder."
    return info


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        return str(p)


def check(form: dict, domains_dir: Path = DOMAINS) -> dict:
    catalogue = load_catalogue()
    result = validate(form, {e["concept_id"] for e in catalogue["emotions"]})
    result["destination"] = destination(result["model_id"], domains_dir)
    if result["destination"]["problem"] and result["model_id"]:
        result["errors"].append({"field": "name", "message": result["destination"]["problem"]})
    return result


def save(form: dict, overwrite: bool = False, domains_dir: Path = DOMAINS,
         builder: Path = BUILDER, template: Path = TEMPLATE, _test_fail_commit: bool = False) -> dict:
    result = check(form, domains_dir)
    if result["errors"]:
        return {"ok": False, "errors": result["errors"], "warnings": result["warnings"]}
    dest = result["destination"]
    if dest["exists"] and not overwrite:
        return {"ok": False, "needs_confirmation": True, "destination": dest, "warnings": result["warnings"],
                "errors": [{"field": "name", "message": "Model files already exist: " + ", ".join(dest["exists"])}]}
    python = uno_python()
    if python is None:
        return {"ok": False, "errors": [{"field": "", "message":
                "Saving needs LibreOffice and its Python UNO bridge (python3-uno); none was found."}]}
    request = {"model": result["model"], "overwrite": overwrite, "domains_dir": str(domains_dir),
               "builder": str(builder), "template": str(template), "_test_fail_commit": _test_fail_commit}
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONHOME", "VIRTUAL_ENV")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with _lock:   # one LibreOffice save at a time
        proc = subprocess.run([python, str(OFFICE_SAVE)], input=json.dumps(request), capture_output=True,
                              text=True, timeout=300, env=env, cwd=str(REPO))
    lines = [line for line in proc.stdout.splitlines() if line.startswith("{")]
    if not lines:
        return {"ok": False, "errors": [{"field": "", "message": f"Save process failed: {proc.stderr[-1500:]}"}]}
    out = json.loads(lines[-1])
    if not out.get("ok"):
        return {"ok": False, "errors": [{"field": "", "message": out.get("error", "unknown error")}],
                "warnings": result["warnings"], "trace": out.get("trace")}
    out.pop("trace", None)
    return {**out, "warnings": result["warnings"], "catalogue_links": result["catalogue_links"],
            "folder": _rel(Path(out["folder"])), "yaml": _rel(Path(out["yaml"])), "ods": _rel(Path(out["ods"])),
            "replaced": [_rel(Path(p)) for p in out["replaced"]]}
