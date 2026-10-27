"""
Abstract base class for all AI providers.

Every provider must implement `generate()` which takes system + user
prompts and returns a raw JSON string from the model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """Contract that every AI provider implementation must satisfy."""

    name: str = "base"
    model: str = "unknown"
    is_mock: bool = False

    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call the AI model and return the raw response text.

        Args:
            system_prompt: Instructions and JSON schema for the model.
            user_prompt:   The user-facing request (topic / level / language).

        Returns:
            Raw text from the model — expected to be a JSON string.

        Raises:
            ProviderError:   On API errors or unexpected responses.
            TimeoutError:    If the call exceeds the configured timeout.
        """


class ProviderError(Exception):
    """Raised when the AI provider returns an error or invalid response."""

    def __init__(self, message: str, provider: str, cause: Exception | None = None) -> None:
        self.provider = provider
        self.cause    = cause
        super().__init__(message)
