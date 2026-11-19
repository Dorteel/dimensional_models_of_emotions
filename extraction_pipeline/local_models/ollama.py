"""Placeholder for an Ollama implementation of ModelExecutor."""

from pathlib import Path
from typing import Mapping, Sequence


class OllamaModel:
    """Select a local model without importing an SDK or contacting a server."""

    def __init__(self, model: str):
        self.model = model

    def execute(
        self,
        prompt: str,
        *,
        images: Sequence[Path] = (),
        options: Mapping[str, object] | None = None,
    ) -> str:
        raise NotImplementedError("Ollama execution is not implemented yet")
