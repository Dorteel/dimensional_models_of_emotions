"""Independent domain loading and the image estimation entry point."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from ..model_execution import ModelExecutor


@dataclass
class ObservedInstance:
    """In-memory estimate, independent of OWL identity or persistence format.

    Coordinate keys refer to dimension IDs in the input Domain Model.
    """

    image: Path
    domain_id: str
    coordinates: Mapping[str, float]


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


def estimate(
    image: str | Path, domain: Mapping[str, Any], model: ModelExecutor
) -> ObservedInstance:
    """Estimate coordinates for an image using the supplied domain dimensions."""
    raise NotImplementedError("Emotion estimation is not implemented yet")


def save_observation(observation: ObservedInstance, path: str | Path) -> None:
    """Serialization interface, pending agreement on observed-result storage.

    Observations are not domain prototype rows. No new YAML schema or ontology
    individual format is chosen by this scaffold.
    """
    raise NotImplementedError("ObservedInstance serialization is not defined yet")
