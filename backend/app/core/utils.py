import uuid
from uuid_utils import uuid7 as _uuid7


def new_uuid() -> uuid.UUID:
    """Generate a UUIDv7 — time-ordered and monotonically increasing for efficient DB indexing."""
    return uuid.UUID(str(_uuid7()))
