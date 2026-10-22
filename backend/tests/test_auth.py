from datetime import timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.core.config import AuthSettings
from src.features.auth.api.deps import SESSION_COOKIE
from src.features.auth.domain import Session
from src.features.auth.security import hash_password, hash_token, verify_password
from src.features.auth.service import GUEST_EMAIL
from src.features.upscale.domain import now_utc
from src.infrastructure.db.engine import create_session_factory
from src.infrastructure.storage.users import SqlUserRepository
from tests.conftest import SettingsFactory, make_png, register


def login(client: TestClient, email: str = "anime@example.com", password: str = "secret-pass"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def upload(client: TestClient) -> str:
    response = client.post("/api/upscale", files={"file": ("frame.png", make_png(), "image/png")})
    assert response.status_code == 202, response.text
    return response.json()["id"]


def test_password_hashing() -> None:
    first, second = hash_password("secret-pass"), hash_password("secret-pass")
    assert first != second  # random salt
    assert verify_password("secret-pass", first)
    assert not verify_password("wrong-pass", first)
    assert not verify_password("secret-pass", "garbage")


def test_register_logs_in(client: TestClient) -> None:
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "anime@example.com"
    assert me.json()["name"] == "Анимешка"
    assert "password_hash" not in me.json()


def test_session_cookie_is_http_only(client: TestClient) -> None:
    response = login(client)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie


def test_email_is_case_insensitive_and_unique(client: TestClient) -> None:
    client.cookies.clear()
    response = client.post(
        "/api/auth/register",
        json={"email": "  ANIME@Example.com ", "password": "other-pass", "name": "Copy"},
    )
    assert response.status_code == 409

    assert login(client, email="Anime@EXAMPLE.com").status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"email": "not-an-email", "password": "secret-pass", "name": "X"},
        {"email": "a@b.co", "password": "short", "name": "X"},
        {"email": "a@b.co", "password": "secret-pass", "name": ""},
    ],
)
def test_register_validation(client: TestClient, body: dict) -> None:
    assert client.post("/api/auth/register", json=body).status_code == 422


def test_wrong_credentials(client: TestClient) -> None:
    client.cookies.clear()
    assert login(client, password="wrong-pass").status_code == 401
    assert login(client, email="nobody@example.com").status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_logout_kills_the_session(client: TestClient) -> None:
    token = client.cookies[SESSION_COOKIE]
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    # The old cookie must not work any more, even if someone kept a copy.
    client.cookies.set(SESSION_COOKIE, token)
    assert client.get("/api/auth/me").status_code == 401


def test_expired_session_is_rejected(client: TestClient) -> None:
    user_id = UUID(client.get("/api/auth/me").json()["id"])
    users = SqlUserRepository(create_session_factory(client.app.state.container.engine))
    users.add_session(
        Session(
            token_hash=hash_token("old-token"),
            user_id=user_id,
            expires_at=now_utc() - timedelta(seconds=1),
        )
    )

    client.cookies.set(SESSION_COOKIE, "old-token")
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("get", "/api/jobs"),
        ("post", "/api/upscale"),
        ("post", "/api/upscale/video"),
        ("get", "/api/jobs/00000000-0000-0000-0000-000000000000"),
        ("get", "/api/jobs/00000000-0000-0000-0000-000000000000/result"),
        ("delete", "/api/jobs/00000000-0000-0000-0000-000000000000"),
    ],
)
def test_job_endpoints_require_login(client: TestClient, method: str, url: str) -> None:
    client.cookies.clear()
    assert client.request(method, url).status_code == 401


def test_health_is_public(client: TestClient) -> None:
    client.cookies.clear()
    assert client.get("/health").status_code == 200


def test_users_see_only_their_own_jobs(client: TestClient) -> None:
    job_id = upload(client)

    client.cookies.clear()
    register(client, email="other@example.com", name="Other")
    assert client.get("/api/jobs").json() == []
    # Someone else's job looks exactly like a missing one.
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert client.get(f"/api/jobs/{job_id}/result").status_code == 404
    assert client.delete(f"/api/jobs/{job_id}").status_code == 404

    own_id = upload(client)
    assert [job["id"] for job in client.get("/api/jobs").json()] == [own_id]

    client.cookies.clear()
    assert login(client).status_code == 200
    assert [job["id"] for job in client.get("/api/jobs").json()] == [job_id]
    assert client.get(f"/api/jobs/{job_id}/result").status_code == 200


def test_auth_not_required_runs_as_guest(make_settings: SettingsFactory) -> None:
    settings = make_settings()
    settings.auth = AuthSettings(required=False)
    with TestClient(create_app(settings)) as anonymous:
        assert anonymous.get("/health").json()["auth"] == "open"

        # No cookie at all: everything works as the guest.
        me = anonymous.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == GUEST_EMAIL
        job_id = upload(anonymous)
        assert [job["id"] for job in anonymous.get("/api/jobs").json()] == [job_id]
        assert anonymous.get(f"/api/jobs/{job_id}/result").status_code == 200

        # A stale cookie does not block anonymous access either.
        anonymous.cookies.set(SESSION_COOKIE, "expired-or-garbage")
        assert anonymous.get("/api/auth/me").json()["email"] == GUEST_EMAIL
        anonymous.cookies.clear()

        # Real logins still work and keep their own history.
        register(anonymous, email="real@example.com")
        assert anonymous.get("/api/auth/me").json()["email"] == "real@example.com"
        assert anonymous.get("/api/jobs").json() == []
        assert anonymous.get(f"/api/jobs/{job_id}").status_code == 404

        # The guest cannot be logged into.
        assert login(anonymous, email=GUEST_EMAIL, password="").status_code in (401, 422)
