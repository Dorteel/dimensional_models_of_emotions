"""Local server for the Emotional Ontology GUI (Python standard library + RDFLib).

Serves the static dashboard from gui/web/ and a small read-only JSON API. Ontology content is obtained
by loading the OWL file with RDFLib and running the named SPARQL queries in gui/sparql/ (see
gui/sparql/README.md). Every request loads the file afresh, so Reload always shows what is on disk.

  GET /api/ontologies                       OWL files available in the ontology folder
  GET /api/ontology?file=<name>             Emotional Ontology tab model (query explorer/statements)
  GET /api/domains                          Domain Models tab data (queries domains/*), from the populated file
  GET /api/queries                          the named queries (name, description, text)
  GET /api/sparql/<name>[?file=<name>]      raw result rows of one named query (no user-supplied SPARQL)
  GET  /api/catalogue                       emotions/emotion_catalogue.ods (+ dictionary definitions)
  POST /api/models/validate                 check a Create Domain Model form (no files written)
  POST /api/models/save                     save domains/<id>/<id>.yaml + .ods with the builder macros

Model creation never touches the ontology; populating it remains a separate step (ontology/populate_ontology.py).

Ontology folder: `ontology/` (the repository's ontology location). The previous
`owl/` location is supported as a fallback if no ontology files are found there.
The folder is re-resolved on every request unless --owl-dir is given.

Ontology files are only ever opened for reading. Only files listed by
/api/ontologies can be requested, so no other path on disk is reachable.

Usage (from the repository root):
    python3 gui/server.py [--port 8765] [--owl-dir ontology] [--default emotional_ontology_populated.owl] [--open]

RDFLib is installed in gui/.venv (see gui/README.md). If the interpreter running this script cannot import
it, the script restarts itself with gui/.venv/bin/python when that environment exists.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import webbrowser
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

GUI_DIR = Path(__file__).resolve().parent
REPO_DIR = GUI_DIR.parent
VENV_PYTHON = GUI_DIR / ".venv" / "bin" / "python"
sys.path.insert(0, str(GUI_DIR))

try:
    import rdflib  # noqa: F401
except ImportError:
    # The venv's python is a symlink to the system interpreter, so compare environments (sys.prefix), not binaries.
    if __name__ == "__main__" and VENV_PYTHON.exists() and Path(sys.prefix).resolve() != (GUI_DIR / ".venv").resolve():
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
    sys.exit("RDFLib is required. Set it up with:\n"
             "  python3 -m venv gui/.venv && gui/.venv/bin/pip install -r gui/requirements.txt\n"
             "then run:  gui/.venv/bin/python gui/server.py")

from ontology_service import (QueryLibrary, UnknownQuery, build_domains, build_explorer_model,  # noqa: E402
                              find_ontologies, load)
from model_builder import save as model_save  # noqa: E402
from model_builder.catalogue import load_catalogue  # noqa: E402

MAX_POST_BYTES = 1_000_000

# Searched in this order; the first folder that contains .owl files is used.
OWL_DIR_CANDIDATES = [REPO_DIR / "ontology", REPO_DIR / "owl"]
PREFERRED_DEFAULT = "emotional_ontology_populated.owl"
# The Domain Models tab reads only this file.
DOMAIN_SOURCE = "emotional_ontology_populated.owl"


def resolve_owl_dir() -> Path:
    for candidate in OWL_DIR_CANDIDATES:
        if find_ontologies(candidate):
            return candidate
    return OWL_DIR_CANDIDATES[0]


DEFAULT_OWL_DIR = resolve_owl_dir()  # at import time; the server re-resolves per request
QUERIES = QueryLibrary()             # gui/sparql/*.rq, parsed once at start-up


class Handler(SimpleHTTPRequestHandler):
    owl_dir_override: Path | None = None
    default_file: str | None = None
    domains_dir: Path = model_save.DOMAINS     # where the Create Domain Model tab saves models

    @property
    def owl_dir(self) -> Path:
        return self.owl_dir_override or resolve_owl_dir()

    def log_message(self, fmt, *args):  # quieter console: API errors only
        if self.path.startswith("/api/") and args and str(args[1]).startswith(("4", "5")):
            super().log_message(fmt, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def available(self):
        return {p.name: p for p in find_ontologies(self.owl_dir)}

    def do_GET(self):  # noqa: N802
        url = urlparse(self.path)
        if url.path == "/api/ontologies":
            files = self.available()
            default = self.default_file if self.default_file in files else \
                (PREFERRED_DEFAULT if PREFERRED_DEFAULT in files else next(iter(files), None))
            owl_dir = self.owl_dir
            return self.send_json({
                "directory": str(owl_dir),
                "directory_relative": str(owl_dir.relative_to(REPO_DIR)) if owl_dir.is_relative_to(REPO_DIR) else str(owl_dir),
                "searched": [str(c.relative_to(REPO_DIR)) for c in OWL_DIR_CANDIDATES] if not self.owl_dir_override else [],
                "fallback": not self.owl_dir_override and owl_dir != OWL_DIR_CANDIDATES[0],
                "domain_source": DOMAIN_SOURCE,
                "default": default,
                "files": [{"name": n, "size": p.stat().st_size, "mtime": p.stat().st_mtime} for n, p in files.items()],
            })
        query = parse_qs(url.query)
        if url.path == "/api/ontology":
            return self.with_ontology(query.get("file", [None])[0], lambda loaded: build_explorer_model(loaded, QUERIES))
        if url.path == "/api/domains":
            return self.with_ontology(DOMAIN_SOURCE, lambda loaded: build_domains(loaded, QUERIES))
        if url.path == "/api/queries":
            return self.send_json({"directory": str(QUERIES.directory.relative_to(REPO_DIR)), "queries": [
                {"name": q.name, "file": str(q.path.relative_to(REPO_DIR)), "description": q.description, "text": q.text}
                for q in (QUERIES.get(n) for n in QUERIES.names())]})
        if url.path == "/api/catalogue":
            try:
                return self.send_json(load_catalogue())
            except Exception as exc:  # noqa: BLE001
                return self.send_json({"error": f"Could not read the emotion catalogue: {exc}"},
                                      HTTPStatus.UNPROCESSABLE_ENTITY)
        if url.path.startswith("/api/sparql/"):
            name = url.path[len("/api/sparql/"):]
            try:
                QUERIES.get(name)
            except UnknownQuery:
                return self.send_json({"error": f"Unknown query: {name!r}", "available": QUERIES.names()},
                                      HTTPStatus.NOT_FOUND)
            return self.with_ontology(query.get("file", [DOMAIN_SOURCE])[0],
                                      lambda loaded: {"file": loaded.meta["file"], **QUERIES.run_json(name, loaded.graph)})
        if url.path.startswith("/api/"):
            return self.send_json({"error": "Unknown API endpoint"}, HTTPStatus.NOT_FOUND)
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        url = urlparse(self.path)
        if url.path not in ("/api/models/validate", "/api/models/save"):
            return self.send_json({"error": "Unknown API endpoint"}, HTTPStatus.NOT_FOUND)
        # Writes are only accepted as JSON from this dashboard's own origin (no cross-site form posts).
        origin = self.headers.get("Origin")
        if origin is not None and origin != f"http://{self.headers.get('Host', '')}":
            return self.send_json({"error": "Cross-origin requests are not accepted."}, HTTPStatus.FORBIDDEN)
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self.send_json({"error": "Expected application/json."}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_POST_BYTES:
            return self.send_json({"error": "Missing or oversized request body."}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            form = body["model"]
            if not isinstance(form, dict):
                raise TypeError
        except (ValueError, KeyError, TypeError):
            return self.send_json({"error": "Body must be JSON: {\"model\": {...}}."}, HTTPStatus.BAD_REQUEST)
        try:
            if url.path == "/api/models/validate":
                result = model_save.check(form, self.domains_dir)
                return self.send_json({"ok": not result["errors"], **{k: result[k] for k in
                                       ("model_id", "model", "errors", "warnings", "destination")}})
            return self.send_json(model_save.save(form, overwrite=body.get("overwrite") is True,
                                                  domains_dir=self.domains_dir))
        except Exception as exc:  # noqa: BLE001
            return self.send_json({"ok": False, "errors": [{"field": "", "message": f"{type(exc).__name__}: {exc}"}]},
                                  HTTPStatus.INTERNAL_SERVER_ERROR)

    def with_ontology(self, name, build):
        """Load a listed ontology file afresh with RDFLib and answer with build(loaded)."""
        files = self.available()
        if name not in files:
            return self.send_json({"error": f"Unknown ontology file: {name!r}", "available": sorted(files)},
                                  HTTPStatus.NOT_FOUND)
        try:
            return self.send_json(build(load(files[name])))
        except Exception as exc:  # noqa: BLE001  report parse/query errors to the UI instead of failing silently
            return self.send_json({"error": f"Could not read {name}: {exc}"}, HTTPStatus.UNPROCESSABLE_ENTITY)


def make_server(port=8765, owl_dir=None, default_file=None, host="127.0.0.1", domains_dir=None):
    override = Path(owl_dir).resolve() if owl_dir else None
    handler = type("BoundHandler", (Handler,), {"owl_dir_override": override, "default_file": default_file,
                                                "domains_dir": Path(domains_dir).resolve() if domains_dir
                                                else model_save.DOMAINS})
    return ThreadingHTTPServer((host, port), partial(handler, directory=str(GUI_DIR / "web")))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Emotional Ontology GUI (local, read-only)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--owl-dir", default=None,
                        help="folder containing the .owl files (default: ontology/, else owl/)")
    parser.add_argument("--default", dest="default_file", help="OWL file shown first (file name in --owl-dir)")
    parser.add_argument("--domains-dir", default=None,
                        help="where Create Domain Model saves models (default: domains/; e.g. a scratch folder for tests)")
    parser.add_argument("--open", action="store_true", help="open the dashboard in the default browser")
    args = parser.parse_args(argv)

    server = make_server(args.port, args.owl_dir, args.default_file, domains_dir=args.domains_dir)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    owl_dir = Path(args.owl_dir).resolve() if args.owl_dir else resolve_owl_dir()
    found = [p.name for p in find_ontologies(owl_dir)]
    print(f"Emotional Ontology GUI: {url}")
    print(f"Ontology folder: {owl_dir} ({', '.join(found) or 'no .owl files found'})")
    if not args.owl_dir and owl_dir != OWL_DIR_CANDIDATES[0]:
        print(f"Note: {OWL_DIR_CANDIDATES[0]} has no .owl files yet; using {owl_dir}")
    print(f"Create Domain Model saves to: {Path(args.domains_dir).resolve() if args.domains_dir else model_save.DOMAINS}")
    print("Press Ctrl+C to stop.")
    if args.open:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
