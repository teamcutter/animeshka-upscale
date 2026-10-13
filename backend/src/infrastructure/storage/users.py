from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.features.auth.domain import Session as LoginSession
from src.features.auth.domain import User
from src.infrastructure.db.models import SessionRow, UserRow
from src.infrastructure.storage.sql import aware_utc
from src.shared.errors import ConflictError


def _to_domain(row: UserRow) -> User:
    return User(
        id=row.id,
        email=row.email,
        name=row.name,
        password_hash=row.password_hash,
        created_at=aware_utc(row.created_at),
    )


class SqlUserRepository:
    """Users and their login sessions."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def add(self, user: User) -> None:
        try:
            with self._sessions.begin() as session:
                session.add(
                    UserRow(
                        id=user.id,
                        email=user.email,
                        name=user.name,
                        password_hash=user.password_hash,
                        created_at=user.created_at,
                    )
                )
        except IntegrityError as exc:
            # Two registrations with the same email at once: the unique index decides.
            raise ConflictError("Email is already registered") from exc

    def get(self, user_id: UUID) -> User | None:
        with self._sessions() as session:
            row = session.get(UserRow, user_id)
            return _to_domain(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        with self._sessions() as session:
            row = session.scalar(select(UserRow).where(UserRow.email == email))
            return _to_domain(row) if row else None

    def add_session(self, login: LoginSession) -> None:
        with self._sessions.begin() as session:
            session.add(
                SessionRow(
                    token_hash=login.token_hash,
                    user_id=login.user_id,
                    created_at=login.created_at,
                    expires_at=login.expires_at,
                )
            )

    def get_session_user(self, token_hash: str, now: datetime) -> User | None:
        stmt = select(SessionRow).where(
            SessionRow.token_hash == token_hash, SessionRow.expires_at > now
        )
        with self._sessions() as session:
            row = session.scalar(stmt)
            return _to_domain(row.user) if row else None

    def delete_session(self, token_hash: str) -> None:
        with self._sessions.begin() as session:
            session.execute(delete(SessionRow).where(SessionRow.token_hash == token_hash))

    def delete_expired_sessions(self, now: datetime) -> None:
        with self._sessions.begin() as session:
            session.execute(delete(SessionRow).where(SessionRow.expires_at <= now))
