"""Interfaces for locally hosted models; no model downloads or startup."""

from .ollama import OllamaModel

__all__ = ["OllamaModel"]
