from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool

from src.features.auth.api.deps import (
    SESSION_COOKIE,
    AuthServiceDep,
    CurrentUser,
    session_cookie,
)
from src.features.auth.api.schemas import LoginRequest, RegisterRequest, UserResponse
from src.features.auth.service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def set_session_cookie(request: Request, response: Response, auth: AuthService, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(auth.session_ttl.total_seconds()),
        httponly=True,  # not readable from JS
        samesite="lax",  # not sent with cross-site POSTs (CSRF)
        secure=request.app.state.container.settings.auth.cookie_secure,
        path="/",
    )


@router.post("/register", status_code=201, response_model=UserResponse)
async def register(
    body: RegisterRequest, request: Request, response: Response, auth: AuthServiceDep
) -> UserResponse:
    """Creates the account and logs in right away."""
    user = await run_in_threadpool(auth.register, body.email, body.password, body.name)
    token = await run_in_threadpool(auth.start_session, user)
    set_session_cookie(request, response, auth, token)
    return UserResponse.from_user(user)


@router.post("/login", response_model=UserResponse)
async def login(
    body: LoginRequest, request: Request, response: Response, auth: AuthServiceDep
) -> UserResponse:
    user, token = await run_in_threadpool(auth.login, body.email, body.password)
    set_session_cookie(request, response, auth, token)
    return UserResponse.from_user(user)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    auth: AuthServiceDep,
    token: Annotated[str | None, Depends(session_cookie)],
) -> None:
    if token:
        auth.logout(token)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return UserResponse.from_user(user)
