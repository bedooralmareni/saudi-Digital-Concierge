"""Base loader interface for raw data sources.

Every raw data source (reviews, places, events, ...) is loaded by a subclass of
:class:`BaseLoader`. Keeping a common interface means the ingestion driver can
iterate over loaders without knowing the details of each source format.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator


@dataclass
class Document:
    """A single unit of raw content plus its provenance metadata."""

    text: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseLoader(ABC):
    """Abstract base class for a raw data source loader."""

    #: Name of the source, e.g. ``"tourism_reviews"``. Used for provenance.
    source_name: str = "base"

    def __init__(self, raw_dir: str | Path) -> None:
        self.raw_dir = Path(raw_dir)

    @abstractmethod
    def load(self) -> Iterator[Document]:
        """Yield :class:`Document` objects parsed from ``self.raw_dir``."""
        raise NotImplementedError
