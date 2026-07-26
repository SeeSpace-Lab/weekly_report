"""Core contracts for the automated weekly-intelligence pipeline."""
from .contracts import (
    BatchStatus,
    CollectionBatch,
    CollectionWindow,
    CollectedDocument,
    DocumentType,
    SourceConfig,
)

__all__ = [
    "BatchStatus",
    "CollectionBatch",
    "CollectionWindow",
    "CollectedDocument",
    "DocumentType",
    "SourceConfig",
]
