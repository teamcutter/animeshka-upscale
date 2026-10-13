from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from src.features.upscale.domain import now_utc


@dataclass
class User:
    email: str
    name: str
    password_hash: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class Session:
    """A login. Only the token's hash is stored: a database leak doesn't log anyone in."""

    token_hash: str
    user_id: UUID
    expires_at: datetime
    created_at: datetime = field(default_factory=now_utc)
