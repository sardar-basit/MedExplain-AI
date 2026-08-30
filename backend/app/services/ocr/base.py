"""Pluggable OCR providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class OCRResult:
    """Raw OCR output. Prefer line-oriented text that keeps marker/value/unit alignment."""

    raw_text: str


class OCRService(ABC):
    @abstractmethod
    async def extract(self, file_url: str) -> OCRResult:
        """Extract text from a stored file URL."""
