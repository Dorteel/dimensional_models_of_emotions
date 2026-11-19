"""Domain YAML I/O and the prototype generation entry point."""

from pathlib import Path
from typing import Any, Mapping

import yaml

from ..model_execution import ModelExecutor


def load_domain_model(path: str | Path) -> dict[str, Any]:
    """Read the existing domains/ YAML contract without normalizing its values.

    This checks the document container only; domain validation belongs to the
    existing domain workflow. No definitions, coordinates, or fields are added.
    """
    with Path(path).open(encoding="utf-8") as stream:
        domain = yaml.safe_load(stream)
    if not isinstance(domain, dict):
        raise ValueError("Domain Model YAML must contain a mapping")
    return domain


def save_domain_model(domain: Mapping[str, Any], path: str | Path) -> None:
    """Write the same domain mapping as YAML, refusing to overwrite a file.

    The caller chooses the destination and creates its parent directory. YAML
    formatting may change; values and additional metadata fields are retained.
    """
    text = yaml.safe_dump(dict(domain), allow_unicode=True, sort_keys=False)
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(text)


def generate(domain: Mapping[str, Any], model: ModelExecutor) -> dict[str, Any]:
    """Return a generated Domain Model in the existing YAML structure.

    Prototype selection, prompts, provenance, and response parsing are deferred.
    """
    raise NotImplementedError("Prototype generation is not implemented yet")
