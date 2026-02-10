"""Public ID generation using ULID."""

import uuid

from ulid import ULID


def new_public_id(prefix: str) -> str:
    """Return a prefixed ULID string, e.g. ``set_01J5K…``."""
    return f"{prefix}{ULID()}"


def new_uuid() -> uuid.UUID:
    """Return a new random UUID v4."""
    return uuid.uuid4()
