"""Local server for the Emotional Ontology GUI (Python standard library only).

Serves the static dashboard from gui/web/ and a small read-only JSON API:

  GET /api/ontologies              OWL files available in the ontology folder
  GET /api/ontology?file=<name>    the parsed ontology (re-read from disk on every request)

Ontology files are only ever opened for reading. Only files listed by
/api/ontologies can be requested, so no other path on disk is reachable.

Usage (from the repository root):
    python3 gui/server.py [--port 8765] [--owl-dir owl] [--default emotional_ontology_populated.owl] [--open]
"""

from __future__ import annotations

import argparse
import json
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
sys.path.insert(0, str(GUI_DIR))

from owl_loader import find_ontologies, load_ontology  # noqa: E402

DEFAULT_OWL_DIR = REPO_DIR / "owl"
PREFERRED_DEFAULT = "emotional_ontology_populated.owl"


class Handler(SimpleHTTPRequestHandler):
    owl_dir: Path = DEFAULT_OWL_DIR
    default_file: str | None = None

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
            return self.send_json({
                "directory": str(self.owl_dir),
                "default": default,
                "files": [{"name": n, "size": p.stat().st_size, "mtime": p.stat().st_mtime} for n, p in files.items()],
            })
        if url.path == "/api/ontology":
            name = parse_qs(url.query).get("file", [None])[0]
            files = self.available()
            if name not in files:
                return self.send_json({"error": f"Unknown ontology file: {name!r}",
                                       "available": sorted(files)}, HTTPStatus.NOT_FOUND)
            try:
                return self.send_json(load_ontology(files[name]))
            except Exception as exc:  # noqa: BLE001  report parse errors to the UI instead of failing silently
                return self.send_json({"error": f"Could not read {name}: {exc}"}, HTTPStatus.UNPROCESSABLE_ENTITY)
        if url.path.startswith("/api/"):
            return self.send_json({"error": "Unknown API endpoint"}, HTTPStatus.NOT_FOUND)
        return super().do_GET()


def make_server(port=8765, owl_dir=DEFAULT_OWL_DIR, default_file=None, host="127.0.0.1"):
    handler = type("BoundHandler", (Handler,), {"owl_dir": Path(owl_dir).resolve(), "default_file": default_file})
    return ThreadingHTTPServer((host, port), partial(handler, directory=str(GUI_DIR / "web")))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Emotional Ontology GUI (local, read-only)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--owl-dir", default=str(DEFAULT_OWL_DIR), help="folder containing the .owl files")
    parser.add_argument("--default", dest="default_file", help="OWL file shown first (file name in --owl-dir)")
    parser.add_argument("--open", action="store_true", help="open the dashboard in the default browser")
    args = parser.parse_args(argv)

    server = make_server(args.port, args.owl_dir, args.default_file)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    found = [p.name for p in find_ontologies(args.owl_dir)]
    print(f"Emotional Ontology GUI: {url}")
    print(f"Ontology folder: {Path(args.owl_dir).resolve()} ({', '.join(found) or 'no .owl files found'})")
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
