"""Extended search: words and hashtags in descriptions, relevance, exclusions, filters."""

import pytest
from fastapi.testclient import TestClient

from src.features.feed.domain import SearchQuery, extract_words
from tests.conftest import make_png
from tests.test_feed import act_as, new_user
from tests.test_feed_tags import publish


def search(client: TestClient, q: str = "", **params: str | int) -> dict:
    response = client.get("/api/feed/search", params={"q": q, **params})
    assert response.status_code == 200, response.text
    return response.json()


def found(client: TestClient, q: str = "", **params: str | int) -> list[str]:
    return [item["description"] for item in search(client, q, **params)["items"]]


def test_parse_query() -> None:
    query = SearchQuery.parse("Арбуз #помидор, -огурец  арбуз -")
    assert query.terms == ("арбуз", "помидор")
    assert query.excluded == ("огурец",)
    # A word both wanted and excluded is excluded.
    assert SearchQuery.parse("арбуз -арбуз").terms == ()
    with pytest.raises(ValueError):
        SearchQuery.parse(" ".join(f"w{i}" for i in range(11)))


def test_extract_words() -> None:
    assert extract_words("Сочный АРБУЗ! #studio_ghibli #арбуз") == [
        "сочный",
        "арбуз",
        "studio_ghibli",
        "studio",
        "ghibli",
    ]
    assert extract_words(None) == []


def test_any_word_both_first(client: TestClient) -> None:
    """The example from the task: "арбуз помидор" shows posts with either and with both."""
    publish(client, "только #арбуз")
    publish(client, "Арбуз и помидор на одном фото")
    publish(client, "свежий помидор")
    publish(client, "огурец")
    publish(client, "#помидор #арбуз вместе, хештегами")

    new_user(client, "viewer@example.com", "Viewer")
    assert found(client, "арбуз помидор") == [
        # Both words, newest first...
        "#помидор #арбуз вместе, хештегами",
        "Арбуз и помидор на одном фото",
        # ...then one word, newest first.
        "свежий помидор",
        "только #арбуз",
    ]
    # Order of words and '#' don't matter.
    assert found(client, "#ПОМИДОР арбуз") == found(client, "арбуз помидор")


def test_word_start_matches_forms(client: TestClient) -> None:
    publish(client, "Арбузы на рынке")
    publish(client, "закусили арбузом")
    publish(client, "#арбузный_сезон")
    publish(client, "карбюратор")  # contains "арб" but not at the start of a word

    assert set(found(client, "арбуз")) == {
        "Арбузы на рынке",
        "закусили арбузом",
        "#арбузный_сезон",
    }
    assert found(client, "сезон") == ["#арбузный_сезон"]  # parts of a hashtag count too


def test_exclude_words(client: TestClient) -> None:
    publish(client, "арбуз")
    publish(client, "арбуз и помидоры")
    publish(client, "помидор")

    assert found(client, "арбуз -помидор") == ["арбуз"]
    # Only exclusions: everything else, newest first.
    assert found(client, "-арбуз") == ["помидор"]
    assert search(client, "арбуз -помидор")["query"] == {
        "terms": ["арбуз"],
        "excluded": ["помидор"],
    }


def test_filters(client: TestClient, author: str) -> None:
    publish(client, "арбуз 2k картинка")
    job_id = client.post(
        "/api/upscale", files={"file": ("a.png", make_png(), "image/png")}, data={"mode": "4k"}
    ).json()["id"]
    client.post(f"/api/jobs/{job_id}/publish", json={"description": "арбуз 4k картинка"})

    new_user(client, "maria@example.com", "Мария")
    publish(client, "арбуз от Марии")

    assert len(found(client, "арбуз")) == 3
    assert found(client, "арбуз", mode="4k") == ["арбуз 4k картинка"]
    assert found(client, "арбуз", kind="video") == []
    assert len(found(client, "арбуз", kind="image")) == 3
    # Author by name, any case (Cyrillic too).
    assert found(client, "арбуз", author="мАРИЯ") == ["арбуз от Марии"]
    assert found(client, author="Мария") == ["арбуз от Марии"]  # filters without words
    assert found(client, "арбуз", author="Никто") == []
    act_as(client, author)
    assert found(client, "картинка", author="анимешка", mode="2k") == ["арбуз 2k картинка"]


def test_filter_video(client: TestClient, video_factory) -> None:
    publish(client, "арбуз картинка")
    video = client.post(
        "/api/upscale/video", files={"file": ("clip.mp4", video_factory(), "video/mp4")}
    ).json()["id"]
    client.post(f"/api/jobs/{video}/publish", json={"description": "арбуз видео"})
    assert found(client, "арбуз", kind="video") == ["арбуз видео"]
    assert found(client, "арбуз", kind="image") == ["арбуз картинка"]


def test_search_pages_keep_relevance_order(client: TestClient) -> None:
    for i in range(3):
        publish(client, f"арбуз {i}")
    for i in range(3):
        publish(client, f"арбуз помидор {i}")
    publish(client, "без совпадений")

    seen, cursor = [], None
    while True:
        page = search(client, "арбуз помидор", limit=2, **({"cursor": cursor} if cursor else {}))
        seen += [item["description"] for item in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == [
        "арбуз помидор 2",
        "арбуз помидор 1",
        "арбуз помидор 0",
        "арбуз 2",
        "арбуз 1",
        "арбуз 0",
    ]


def test_edit_and_unpublish_update_index(client: TestClient) -> None:
    job = publish(client, "арбуз")
    client.patch(f"/api/feed/{job['post_id']}", json={"description": "помидор"})
    assert found(client, "арбуз") == []
    assert found(client, "помидор") == ["помидор"]

    client.delete(f"/api/jobs/{job['id']}/publish")
    assert found(client, "помидор") == []


def test_like_and_underscore_are_literal(client: TestClient) -> None:
    publish(client, "#a_b")
    publish(client, "#axb")
    assert found(client, "a_") == ["#a_b"]
    # No words in the query at all: nothing to filter by, the whole feed by date.
    assert search(client, "% ! #")["query"] == {"terms": [], "excluded": []}
    assert len(found(client, "% ! #")) == 2


def test_bad_search(client: TestClient) -> None:
    get = client.get
    eleven = " ".join(f"w{i}" for i in range(11))
    assert get("/api/feed/search", params={"q": eleven}).status_code == 400
    assert get("/api/feed/search", params={"cursor": "garbage"}).status_code == 400
    assert get("/api/feed/search", params={"cursor": "x:1.ab"}).status_code == 400
    assert get("/api/feed/search", params={"kind": "gif"}).status_code == 422
    assert get("/api/feed/search", params={"q": "x" * 201}).status_code == 422
    client.cookies.clear()
    assert get("/api/feed/search").status_code == 401
