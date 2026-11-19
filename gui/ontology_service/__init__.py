"""Ontology access for the GUI: RDFLib graph loading + named SPARQL queries (gui/sparql/*.rq)."""

from pathlib import Path

from .domains import build_domains
from .explorer import build_explorer_model
from .queries import QueryLibrary, UnknownQuery
from .store import load


def find_ontologies(directory) -> list[Path]:
    directory = Path(directory)
    return sorted(p for p in directory.glob("*.owl") if p.is_file()) if directory.is_dir() else []


__all__ = ["QueryLibrary", "UnknownQuery", "build_domains", "build_explorer_model", "find_ontologies", "load"]
