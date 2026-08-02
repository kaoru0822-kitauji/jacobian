"""Typed failures owned by the storage boundary."""

from __future__ import annotations

from jacobian.persistence.migrations import CURRENT_STATE_FORMAT_REVISION


class StorageError(RuntimeError):
    """Base class for bounded artifact-storage failures."""


class StorageCorruptionError(StorageError):
    """A persisted storage record cannot be decoded without repair."""

    def __init__(self, corruption: object) -> None:
        self.corruption = corruption
        super().__init__(str(corruption))


class UnsupportedStateVersionError(StorageError):
    """The persisted state is outside the supported migration floor."""

    code = "UNSUPPORTED_STATE_VERSION"

    def __init__(self, detected_revision: int, *, minimum_revision: int) -> None:
        self.detected_revision = detected_revision
        self.minimum_revision = minimum_revision
        direction = (
            "future" if detected_revision > CURRENT_STATE_FORMAT_REVISION else "legacy"
        )
        super().__init__(
            f"{self.code}: {direction} state revision {detected_revision} is not "
            f"supported; minimum supported revision is {minimum_revision}. "
            "Export the data with a compatible release or start a fresh state "
            "directory."
        )


class ArtifactNotFoundError(StorageError):
    """The requested artifact is not committed in this store."""


class ArtifactIntegrityError(StorageError):
    """Stored bytes do not match their content address."""


class StorageLimitError(StorageError):
    """A bounded storage limit would be exceeded."""


class StorageClosedError(StorageError):
    """An operation targeted storage whose runtime ownership has ended."""


__all__ = [
    "ArtifactIntegrityError",
    "ArtifactNotFoundError",
    "StorageClosedError",
    "StorageCorruptionError",
    "StorageError",
    "StorageLimitError",
    "UnsupportedStateVersionError",
]
