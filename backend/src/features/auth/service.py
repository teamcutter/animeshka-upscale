import logging
from datetime import timedelta

from src.core.config import AuthSettings
from src.features.auth.domain import Session, User
from src.features.auth.ports import UserRepository
from src.features.auth.security import (
    hash_password,
    hash_token,
    new_session_token,
    verify_password,
)
from src.features.upscale.domain import now_utc
from src.shared.errors import ConflictError, UnauthorizedError

logger = logging.getLogger(__name__)

# Checked when the email is unknown, so a wrong email takes as long as a wrong password.
_DUMMY_HASH = hash_password("not-a-real-password")

# The account anonymous requests run as when auth.required is False. Its password is random and
# never shown, so nobody can log in as the guest once auth is required again.
GUEST_EMAIL = "guest@animeshka.local"
GUEST_NAME = "Гость"


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(self, users: UserRepository, settings: AuthSettings) -> None:
        self._users = users
        self._settings = settings
        self._guest: User | None = None

    @property
    def session_ttl(self) -> timedelta:
        return timedelta(days=self._settings.session_days)

    @property
    def required(self) -> bool:
        return self._settings.required

    def guest(self) -> User:
        """The shared guest account (created on first use); only used when auth is not required."""
        if self._guest is None:
            user = self._users.get_by_email(GUEST_EMAIL)
            if user is None:
                user = User(
                    email=GUEST_EMAIL,
                    name=GUEST_NAME,
                    password_hash=hash_password(new_session_token()),
                )
                try:
                    self._users.add(user)
                    logger.warning("Auth is disabled: anonymous requests run as %s", GUEST_EMAIL)
                except ConflictError:
                    # Another process created it first.
                    user = self._users.get_by_email(GUEST_EMAIL)
                    assert user is not None
            self._guest = user
        return self._guest

    def register(self, email: str, password: str, name: str) -> User:
        email = normalize_email(email)
        if self._users.get_by_email(email) is not None:
            raise ConflictError("Email is already registered")
        user = User(email=email, name=name.strip(), password_hash=hash_password(password))
        self._users.add(user)
        logger.info("Registered user %s", user.id)
        return user

    def login(self, email: str, password: str) -> tuple[User, str]:
        """Returns the user and a new session token (goes into the cookie)."""
        user = self._users.get_by_email(normalize_email(email))
        if user is None:
            verify_password(password, _DUMMY_HASH)
            raise UnauthorizedError("Invalid email or password")
        if not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")
        return user, self.start_session(user)

    def start_session(self, user: User) -> str:
        now = now_utc()
        self._users.delete_expired_sessions(now)
        token = new_session_token()
        self._users.add_session(
            Session(
                token_hash=hash_token(token), user_id=user.id, expires_at=now + self.session_ttl
            )
        )
        return token

    def logout(self, token: str) -> None:
        self._users.delete_session(hash_token(token))

    def authenticate(self, token: str) -> User:
        user = self._users.get_session_user(hash_token(token), now_utc())
        if user is None:
            raise UnauthorizedError("Session expired, log in again")
        return user
