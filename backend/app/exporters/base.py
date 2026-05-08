"""Abstract exporter base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseExporter(ABC):
    @abstractmethod
    def export(self, test_case: dict[str, Any]) -> str:
        """Convert a structured test case dict to the target format string."""
        ...
