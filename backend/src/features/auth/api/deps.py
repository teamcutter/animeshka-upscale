from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie

from src.features.auth.domain import User
from src.features.auth.service import AuthService
from src.shared.errors import UnauthorizedError

# A cookie (not an Authorization header) so <img src>, <video src> and download links
# to /api/jobs/{id}/result work in the browser without extra frontend code.
SESSION_COOKIE = "animeshka_session"

session_cookie = APIKeyCookie(name=SESSION_COOKIE, auto_error=False)


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.container.auth_service


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def current_user(
    auth: AuthServiceDep, token: Annotated[str | None, Depends(session_cookie)]
) -> User:
    if not token:
        raise UnauthorizedError("Not authenticated")
    return auth.authenticate(token)


CurrentUser = Annotated[User, Depends(current_user)]
