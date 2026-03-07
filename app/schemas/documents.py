
"""
Document schema system.

How it works:
  1. BaseSchema defines the core fields every document has (id, text, metadata).
  2. Versioned schemas (SchemaV1, SchemaV2, ...) extend BaseSchema and add version-specific fields.
  3. Each versioned schema auto-registers itself in SCHEMA_REGISTRY via __init_subclass__.
  4. Document is an alias that always points to the currently active schema version (from config).
  5. When reading from storage, the _schema_version tag tells us which class to use.

To add a new version:
  - Create a new class: class SchemaV4(BaseSchema, version="v4"): ...
  - It auto-registers. No other changes needed (unless you want it as the active version).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Dict, Optional, Type

from pydantic import BaseModel, Field, field_serializer, field_validator

from app.core.config import settings


# ── Schema registry ─────────────────────────────────────────────────────────
# Maps version tag (e.g. "v1") → schema class (e.g. SchemaV1).
# Auto-populated when Python loads the versioned schema classes below.
SCHEMA_REGISTRY: Dict[str, Type[BaseSchema]] = {}


# ── Base schema ──────────────────────────────────────────────────────────────

class BaseSchema(BaseModel):
    """
    Base document schema — every versioned schema extends this.
    Contains the minimum fields every document must have.
    Never modify this after data is stored — add new fields in a new version instead.
    """

    # Each subclass gets its own version tag (e.g. "v1", "v2").
    # Empty string means "not a registered version" (i.e. BaseSchema itself).
    _version_tag: ClassVar[str] = ""

    id: str                        # Unique document ID
    text: str                      # The actual text content
    metadata: DocumentMetadata     # Channel, author, timestamp, schema version, etc.

    def __init_subclass__(cls, version: str = "", **kwargs: Any) -> None:
        """
        Called automatically when a class inherits from BaseSchema.
        If the subclass passes version="v1", it registers itself in SCHEMA_REGISTRY.
        Raises ValueError if two classes try to use the same version tag.
        """
        super().__init_subclass__(**kwargs)
        if version:
            if version in SCHEMA_REGISTRY:
                raise ValueError(
                    f"Duplicate schema version {version!r}: "
                    f"{SCHEMA_REGISTRY[version].__name__} and {cls.__name__}"
                )
            cls._version_tag = version
            SCHEMA_REGISTRY[version] = cls


# ── Document metadata ────────────────────────────────────────────────────────

def _default_schema_class() -> Type[BaseSchema]:
    """Return the currently active schema class from config. Called at runtime, not import time."""
    return SCHEMA_REGISTRY[settings.CURRENT_SCHEMA_VERSION]


class DocumentMetadata(BaseModel):
    """
    Metadata attached to every document.
    The schema_version field stores which schema class this document belongs to.
    """
    model_config = {"arbitrary_types_allowed": True}

    channel: Optional[str] = None                  # e.g. "general", "announcements"
    author: Optional[str] = None                   # Who created the document
    timestamp: Optional[datetime] = None           # When it was created
    attributes: Dict[str, Any] = Field(default_factory=dict)  # Flexible key-value store

    # Stores the schema CLASS (e.g. SchemaV2), not a string.
    # Defaults to whatever CURRENT_SCHEMA_VERSION points to in config.
    schema_version: Type[BaseSchema] = Field(default_factory=_default_schema_class)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _coerce_schema_version(cls, v: Any) -> Type[BaseSchema]:
        """
        Accept either a string ("v2") or a class (SchemaV2) as input.
        Strings are looked up in the registry. Invalid values raise ValueError.
        """
        if isinstance(v, str) and v in SCHEMA_REGISTRY:
            return SCHEMA_REGISTRY[v]
        if isinstance(v, type) and issubclass(v, BaseSchema):
            return v
        raise ValueError(f"Invalid schema_version: {v!r}")

    @field_serializer("schema_version")
    def _serialize_schema_version(self, v: Type[BaseSchema], _info: Any) -> str:
        """When serializing to JSON/dict, convert the class back to its version tag string."""
        return v._version_tag


# BaseSchema references DocumentMetadata, which is defined after it.
# model_rebuild() resolves this forward reference.
BaseSchema.model_rebuild()


# ── Versioned schemas ────────────────────────────────────────────────────────
# Each version is a frozen snapshot. Don't modify after data is stored — create a new version.

class SchemaV1(BaseSchema, version="v1"):
    """Version 1: base fields only (id, text, metadata)."""
    pass


class SchemaV2(BaseSchema, version="v2"):
    """Version 2: adds embedding tracking fields."""
    embedding_model: Optional[str] = None   # Which model generated the embedding (e.g. "gemini-embedding-001")
    embedding_dim: Optional[int] = None     # Dimensionality of the embedding vector (e.g. 768)


class SchemaV3(BaseSchema, version="v3"):
    """Version 3: reserved for future fields."""
    pass


# ── Active document alias ────────────────────────────────────────────────────

def get_document_class(version: Optional[str] = None) -> Type[BaseSchema]:
    """
    Get the schema class for a given version tag.
    If no version is specified, returns the currently active version from config.
    """
    tag = version or settings.CURRENT_SCHEMA_VERSION
    if tag not in SCHEMA_REGISTRY:
        raise ValueError(f"Unknown schema version: {tag!r}")
    return SCHEMA_REGISTRY[tag]


# Convenience alias — always points to the active schema version.
# Evaluated once at import time. Use get_document_class() if you need runtime resolution.
Document = get_document_class()


__all__ = [
    "BaseSchema",
    "Document",
    "DocumentMetadata",
    "SCHEMA_REGISTRY",
    "SchemaV1",
    "SchemaV2",
    "SchemaV3",
    "get_document_class",
]