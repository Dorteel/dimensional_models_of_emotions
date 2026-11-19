"""Named SPARQL queries from gui/sparql/*.rq, executed with RDFLib.

Only the queries in the library can be run: a query is addressed by its name (its path below
gui/sparql/ without ".rq", e.g. "domains/coordinates"). There is no way to submit SPARQL text.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rdflib import BNode, Literal, URIRef
from rdflib.plugins.sparql import prepareQuery

SPARQL_DIR = Path(__file__).resolve().parents[1] / "sparql"


class UnknownQuery(KeyError):
    pass


@dataclass(frozen=True)
class NamedQuery:
    name: str
    path: Path
    text: str
    description: str
    prepared: object


def _description(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if not line.startswith("#"):
            break
        body = line.lstrip("#").strip()
        if not body:
            break
        lines.append(body)
    return " ".join(lines)


class QueryLibrary:
    def __init__(self, directory: Path = SPARQL_DIR):
        self.directory = Path(directory)
        self.queries: dict[str, NamedQuery] = {}
        for path in sorted(self.directory.rglob("*.rq")):
            name = path.relative_to(self.directory).with_suffix("").as_posix()
            text = path.read_text(encoding="utf-8")
            # Parsed once at start-up: a syntax error in a .rq file fails loudly, not at request time.
            self.queries[name] = NamedQuery(name, path, text, _description(text), prepareQuery(text))

    def names(self) -> list[str]:
        return sorted(self.queries)

    def get(self, name: str) -> NamedQuery:
        if name not in self.queries:
            raise UnknownQuery(name)
        return self.queries[name]

    def run(self, name: str, graph) -> tuple[list[str], list[dict]]:
        """Execute a named query; return (column names, rows as {column: RDFLib term or None})."""
        query = self.get(name)
        result = graph.query(query.prepared)
        columns = [str(v) for v in result.vars]
        rows = [{c: row[c] for c in columns} for row in result]
        return columns, rows

    def run_json(self, name: str, graph) -> dict:
        columns, rows = self.run(name, graph)
        return {"query": name, "description": self.get(name).description, "columns": columns,
                "rows": [{c: term_json(r[c]) for c in columns} for r in rows]}


def term_json(term):
    """JSON form of an RDF term, modelled on the SPARQL 1.1 JSON results format."""
    if term is None:
        return None
    if isinstance(term, URIRef):
        return {"type": "uri", "value": str(term)}
    if isinstance(term, BNode):
        return {"type": "bnode", "value": str(term)}
    if isinstance(term, Literal):
        out = {"type": "literal", "value": str(term)}
        if term.datatype is not None:
            out["datatype"] = str(term.datatype)
        if term.language:
            out["lang"] = term.language
        return out
    return {"type": "unknown", "value": str(term)}


def term_id(term) -> str:
    """Stable identifier used by the GUI: the IRI, or '_:<id>' for blank nodes."""
    return "_:" + str(term) if isinstance(term, BNode) else str(term)
