"""The only interface shared by the two extraction pipelines."""

from pathlib import Path
from typing import Mapping, Protocol, Sequence, runtime_checkable


@runtime_checkable
class ModelExecutor(Protocol):
    """Execute a caller-supplied prompt and return the provider's text response.

    Images are optional local paths. Options are provider-specific execution
    settings; this interface supplies no prompt, defaults, or parsing strategy.
    """

    def execute(
        self,
        prompt: str,
        *,
        images: Sequence[Path] = (),
        options: Mapping[str, object] | None = None,
    ) -> str:
        ...
