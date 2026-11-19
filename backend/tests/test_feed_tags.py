"""Post descriptions, hashtags and search by tag."""

import pytest
from fastapi.testclient import TestClient

from src.features.feed.domain import extract_tags, normalize_tag
from tests.test_feed import act_as, feed, new_user, upload


def publish(client: TestClient, description: str | None = None) -> dict:
    """Uploads and publishes a job; returns the job response."""
    job_id = upload(client)
    body = {"description": description} if description is not None else None
    response = client.post(f"/api/jobs/{job_id}/publish", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def search(client: TestClient, *tags: str) -> list[str]:
    """Descriptions of the posts found by the tags, newest first."""
    response = client.get("/api/feed", params={"tag": list(tags)})
    assert response.status_code == 200, response.text
    return [item["description"] for item in response.json()["items"]]


@pytest.mark.parametrize(
    ("text", "tags"),
    [
        ("Закат над городом #аниме #4K #studio_ghibli", ["аниме", "4k", "studio_ghibli"]),
        ("#Anime и снова #anime, #ANIME!", ["anime"]),
        ("#first,#second.#third", ["first", "second", "third"]),
        ("no tags here, C# and a#b and # alone", []),
        ("#" + "x" * 51, []),  # longer than a tag may be
        ("", []),
    ],
)
def test_extract_tags(text: str, tags: list[str]) -> None:
    assert extract_tags(text) == tags


def test_normalize_tag() -> None:
    assert normalize_tag(" #Аниме ") == "аниме"
    for bad in ("", "#", "two words", "a-b", "x" * 51):
        with pytest.raises(ValueError):
            normalize_tag(bad)


def test_publish_with_description(client: TestClient) -> None:
    job = publish(client, "  Ночной Токио #аниме #night  ")
    assert job["published"] is True
    assert job["post_id"] is not None

    item = client.get(f"/api/feed/{job['post_id']}").json()
    assert item["description"] == "Ночной Токио #аниме #night"
    assert item["tags"] == ["аниме", "night"]
    assert feed(client)["items"][0] == item


def test_publish_without_body_still_works(client: TestClient) -> None:
    job_id = upload(client)
    assert client.post(f"/api/jobs/{job_id}/publish").status_code == 200
    item = feed(client)["items"][0]
    assert (item["description"], item["tags"]) == (None, [])
    assert client.get(f"/api/jobs/{job_id}").json()["post_id"] == item["id"]


def test_republish_replaces_description_keeps_post(client: TestClient) -> None:
    job = publish(client, "old #old")
    client.put(f"/api/feed/{job['post_id']}/like")

    again = client.post(f"/api/jobs/{job['id']}/publish", json={"description": "new #new"})
    assert again.json()["post_id"] == job["post_id"]
    assert again.json()["published_at"] == job["published_at"]
    item = feed(client)["items"][0]
    assert (item["description"], item["tags"], item["like_count"]) == ("new #new", ["new"], 1)
    assert search(client, "old") == []

    # Without a description the old one stays.
    client.post(f"/api/jobs/{job['id']}/publish")
    assert feed(client)["items"][0]["description"] == "new #new"


def test_author_edits_description_in_feed(client: TestClient, author: str) -> None:
    post_id = publish(client, "Первый вариант #draft")["post_id"]

    response = client.patch(f"/api/feed/{post_id}", json={"description": "Готово #final #art"})
    assert response.status_code == 200, response.text
    assert response.json()["tags"] == ["final", "art"]
    assert search(client, "draft") == []
    assert search(client, "final") == ["Готово #final #art"]

    # Clearing it removes the tags too.
    for empty in ({"description": ""}, {"description": "   "}, {"description": None}, {}):
        response = client.patch(f"/api/feed/{post_id}", json=empty)
        assert (response.json()["description"], response.json()["tags"]) == (None, [])
    assert search(client, "final") == []

    new_user(client, "other@example.com", "Other")
    response = client.patch(f"/api/feed/{post_id}", json={"description": "hacked #spam"})
    assert response.status_code == 403
    act_as(client, author)
    assert client.get(f"/api/feed/{post_id}").json()["description"] is None


def test_search_by_tags(client: TestClient) -> None:
    publish(client, "один #аниме #закат")
    publish(client, "два #Аниме #город")
    publish(client, "три #город")
    publish(client, "без тегов")

    new_user(client, "viewer@example.com", "Viewer")
    assert search(client, "аниме") == ["два #Аниме #город", "один #аниме #закат"]
    # With or without '#', any case.
    assert search(client, "#АНИМЕ") == search(client, "аниме")
    # Several tags: posts having all of them.
    assert search(client, "аниме", "город") == ["два #Аниме #город"]
    assert search(client, "нет_такого") == []
    assert len(feed(client)["items"]) == 4


def test_search_pages(client: TestClient) -> None:
    for i in range(5):
        publish(client, f"post {i} #paged")
    publish(client, "other #other")

    seen, cursor = [], None
    while True:
        page = feed(client, tag="paged", limit=2, **({"cursor": cursor} if cursor else {}))
        seen += [item["description"] for item in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == [f"post {i} #paged" for i in reversed(range(5))]


def test_bad_search_and_description(client: TestClient) -> None:
    for bad in ("two words", "a-b", "#", "x" * 51):
        assert client.get("/api/feed", params={"tag": bad}).status_code in (400, 422), bad
    assert client.get("/api/feed", params={"tag": [f"t{i}" for i in range(11)]}).status_code == 422

    job_id = upload(client)
    too_long = {"description": "x" * 2001}
    assert client.post(f"/api/jobs/{job_id}/publish", json=too_long).status_code == 422
    assert client.get(f"/api/jobs/{job_id}").json()["published"] is False


def test_unpublish_drops_tags(client: TestClient) -> None:
    job = publish(client, "#gone")
    client.delete(f"/api/jobs/{job['id']}/publish")
    assert client.get(f"/api/jobs/{job['id']}").json()["post_id"] is None
    assert search(client, "gone") == []
    assert client.get("/api/tags").json() == []


def test_popular_tags(client: TestClient) -> None:
    publish(client, "#аниме #art")
    publish(client, "#аниме #animals")
    publish(client, "#аниме #art #a_b")

    tags = client.get("/api/tags").json()
    assert tags[:2] == [{"tag": "аниме", "posts": 3}, {"tag": "art", "posts": 2}]
    assert {t["tag"] for t in tags} == {"аниме", "art", "animals", "a_b"}

    by_prefix = client.get("/api/tags", params={"prefix": "#AN"}).json()
    assert [t["tag"] for t in by_prefix] == ["animals"]
    # '_' is matched literally, not as a LIKE wildcard.
    assert [t["tag"] for t in client.get("/api/tags", params={"prefix": "a_"}).json()] == ["a_b"]
    assert len(client.get("/api/tags", params={"limit": 1}).json()) == 1


def test_tags_need_login(client: TestClient) -> None:
    post_id = publish(client, "#x")["post_id"]
    client.cookies.clear()
    assert client.get("/api/tags").status_code == 401
    assert client.get("/api/feed", params={"tag": "x"}).status_code == 401
    assert client.patch(f"/api/feed/{post_id}", json={"description": "y"}).status_code == 401
