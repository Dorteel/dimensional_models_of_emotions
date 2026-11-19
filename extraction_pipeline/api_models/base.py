"""Placeholder for remote implementations of ModelExecutor."""

from pathlib import Path
from typing import Mapping, Sequence


class APIModel:
    """Select a remote model without reading credentials or making requests."""

    def __init__(self, model: str):
        self.model = model

    def execute(
        self,
        prompt: str,
        *,
        images: Sequence[Path] = (),
        options: Mapping[str, object] | None = None,
    ) -> str:
        raise NotImplementedError("Remote API execution is not implemented yet")
