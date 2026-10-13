from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.features.auth.domain import Session, User


class UserRepository(Protocol):
    def add(self, user: User) -> None:
        """Raises ConflictError if the email is already registered."""
        ...

    def get(self, user_id: UUID) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def add_session(self, login: Session) -> None: ...

    def get_session_user(self, token_hash: str, now: datetime) -> User | None:
        """The owner of an unexpired session; None if the token is unknown or expired."""
        ...

    def delete_session(self, token_hash: str) -> None: ...

    def delete_expired_sessions(self, now: datetime) -> None: ...
