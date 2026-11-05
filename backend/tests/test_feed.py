from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.features.auth.api.deps import SESSION_COOKIE
from src.features.feed.domain import FeedCursor
from src.features.upscale.domain import now_utc
from tests.conftest import SettingsFactory, make_png, register


def upload(client: TestClient) -> str:
    response = client.post("/api/upscale", files={"file": ("frame.png", make_png(), "image/png")})
    assert response.status_code == 202, response.text
    return response.json()["id"]


def act_as(client: TestClient, token: str) -> None:
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, token)


def new_user(client: TestClient, email: str, name: str) -> str:
    """Registers another account on the same client and returns its session token."""
    client.cookies.clear()
    register(client, email=email, name=name)
    token = client.cookies.get(SESSION_COOKIE)
    assert token
    return token


@pytest.fixture
def author(client: TestClient) -> str:
    """Session token of the user the `client` fixture registered."""
    token = client.cookies.get(SESSION_COOKIE)
    assert token
    return token


def feed(client: TestClient, **params: str | int) -> dict:
    response = client.get("/api/feed", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_published_job_is_in_everyones_feed(client: TestClient, author: str) -> None:
    job_id = upload(client)
    assert client.get(f"/api/jobs/{job_id}").json()["published"] is False
    assert feed(client) == {"items": [], "next_cursor": None}

    response = client.post(f"/api/jobs/{job_id}/publish")
    assert response.status_code == 200, response.text
    assert response.json()["published"] is True
    assert response.json()["published_at"] is not None
    # The flag is stored: history and status show it too.
    assert client.get(f"/api/jobs/{job_id}").json()["published"] is True
    assert client.get("/api/jobs").json()[0]["published"] is True

    new_user(client, "viewer@example.com", "Viewer")
    items = feed(client)["items"]
    assert len(items) == 1
    item = items[0]
    assert item["author"] == {"name": "Анимешка"}
    assert "anime@example.com" not in str(item)  # the author's email is never shown
    assert item["mine"] is False
    assert item["mode"] == "2k"
    assert (item["input"]["width"], item["output"]["width"]) == (64, 128)
    assert client.get(f"/api/feed/{item['id']}").json() == item

    image = client.get(item["image_url"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert "attachment" not in image.headers.get("content-disposition", "")
    assert client.get(item["original_url"]).status_code == 200
    # The job itself is still private: the viewer can't open or download it by its id.
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert client.get(f"/api/jobs/{job_id}/result").status_code == 404

    act_as(client, author)
    assert feed(client)["items"][0]["mine"] is True


def test_publish_is_idempotent(client: TestClient) -> None:
    job_id = upload(client)
    first = client.post(f"/api/jobs/{job_id}/publish").json()
    second = client.post(f"/api/jobs/{job_id}/publish").json()
    assert first["published_at"] == second["published_at"]
    assert len(feed(client)["items"]) == 1


def test_unpublish_removes_from_feed_but_keeps_job(client: TestClient) -> None:
    job_id = upload(client)
    client.post(f"/api/jobs/{job_id}/publish")
    item = feed(client)["items"][0]

    response = client.delete(f"/api/jobs/{job_id}/publish")
    assert response.status_code == 200
    assert response.json()["published"] is False
    assert feed(client)["items"] == []
    assert client.get(f"/api/feed/{item['id']}").status_code == 404
    assert client.get(item["image_url"]).status_code == 404
    # Still in my history and downloadable for me.
    assert client.get(f"/api/jobs/{job_id}").json()["published"] is False
    assert client.get(f"/api/jobs/{job_id}/result").status_code == 200
    # Unpublishing twice is fine.
    assert client.delete(f"/api/jobs/{job_id}/publish").status_code == 200


def test_deleting_job_removes_its_post(client: TestClient) -> None:
    job_id = upload(client)
    client.post(f"/api/jobs/{job_id}/publish")
    item = feed(client)["items"][0]

    assert client.delete(f"/api/jobs/{job_id}").status_code == 204
    assert feed(client)["items"] == []
    assert client.get(item["image_url"]).status_code == 404


def test_cannot_publish_someone_elses_job(client: TestClient, author: str) -> None:
    job_id = upload(client)

    new_user(client, "other@example.com", "Other")
    assert client.post(f"/api/jobs/{job_id}/publish").status_code == 404
    assert client.delete(f"/api/jobs/{job_id}/publish").status_code == 404
    assert client.post(f"/api/jobs/{uuid4()}/publish").status_code == 404

    act_as(client, author)
    client.post(f"/api/jobs/{job_id}/publish")
    new_user(client, "third@example.com", "Third")
    # Someone else can't take it out of the feed either.
    assert client.delete(f"/api/jobs/{job_id}/publish").status_code == 404
    assert len(feed(client)["items"]) == 1


def test_only_finished_images_can_be_published(make_settings: SettingsFactory) -> None:
    # No embedded worker: uploads stay queued.
    with TestClient(create_app(make_settings(embedded=False))) as client:
        register(client)
        job_id = upload(client)
        response = client.post(f"/api/jobs/{job_id}/publish")
        assert response.status_code == 409
        assert "only finished jobs" in response.json()["detail"]
        assert feed(client)["items"] == []


def test_failed_video_cannot_be_published(client: TestClient) -> None:
    response = client.post("/api/upscale/video", files={"file": ("clip.mp4", b"fake", "video/mp4")})
    job_id = response.json()["id"]
    assert client.post(f"/api/jobs/{job_id}/publish").status_code == 409


def test_feed_pages_newest_first(client: TestClient) -> None:
    job_ids = [upload(client) for _ in range(5)]
    for job_id in job_ids:
        assert client.post(f"/api/jobs/{job_id}/publish").status_code == 200

    everything = feed(client, limit=50)
    assert everything["next_cursor"] is None
    dates = [item["published_at"] for item in everything["items"]]
    assert dates == sorted(dates, reverse=True)

    pages, cursor = [], None
    while True:
        page = feed(client, limit=2, **({"cursor": cursor} if cursor else {}))
        pages.append([item["id"] for item in page["items"]])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert [len(page) for page in pages] == [2, 2, 1]
    # Pages join into exactly the full feed: nothing skipped or repeated.
    assert sum(pages, []) == [item["id"] for item in everything["items"]]


def test_feed_cursor_round_trip() -> None:
    cursor = FeedCursor(published_at=now_utc(), post_id=uuid4())
    assert FeedCursor.decode(cursor.encode()) == cursor


@pytest.mark.parametrize(
    "cursor",
    ["garbage", "123", "abc.def", "1.zz", f"{10**18}.{uuid4().hex}", f"-{10**20}.{uuid4().hex}"],
)
def test_feed_rejects_bad_cursor(client: TestClient, cursor: str) -> None:
    assert client.get("/api/feed", params={"cursor": cursor}).status_code == 400


def test_feed_needs_login(client: TestClient) -> None:
    job_id = upload(client)
    client.post(f"/api/jobs/{job_id}/publish")
    item = feed(client)["items"][0]

    client.cookies.clear()
    for url in ("/api/feed", f"/api/feed/{item['id']}", item["image_url"], item["original_url"]):
        assert client.get(url).status_code == 401, url
    assert client.post(f"/api/jobs/{job_id}/publish").status_code == 401
    assert client.delete(f"/api/jobs/{job_id}/publish").status_code == 401
