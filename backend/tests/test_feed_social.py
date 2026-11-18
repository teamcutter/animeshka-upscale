"""Likes and comments on feed posts."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.test_feed import act_as, feed, new_user, upload


@pytest.fixture
def post(client: TestClient) -> dict:
    """A post published by the `client` user (the author)."""
    job_id = upload(client)
    assert client.post(f"/api/jobs/{job_id}/publish").status_code == 200
    item = feed(client)["items"][0]
    item["job_id"] = job_id
    return item


def like(client: TestClient, post_id: str) -> dict:
    response = client.put(f"/api/feed/{post_id}/like")
    assert response.status_code == 200, response.text
    return response.json()


def comment(client: TestClient, post_id: str, text: str) -> dict:
    response = client.post(f"/api/feed/{post_id}/comments", json={"text": text})
    assert response.status_code == 201, response.text
    return response.json()


def comments(client: TestClient, post_id: str, **params: str | int) -> dict:
    response = client.get(f"/api/feed/{post_id}/comments", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_users_like_each_others_posts(client: TestClient, author: str, post: dict) -> None:
    post_id = post["id"]
    alice = new_user(client, "alice@example.com", "Alice")
    item = like(client, post_id)
    assert (item["like_count"], item["liked"]) == (1, True)
    # Liking twice counts once.
    assert like(client, post_id)["like_count"] == 1

    new_user(client, "bob@example.com", "Bob")
    item = feed(client)["items"][0]
    assert (item["like_count"], item["liked"]) == (1, False)
    assert like(client, post_id)["like_count"] == 2

    # The author may like their own post too.
    act_as(client, author)
    assert like(client, post_id)["like_count"] == 3
    assert client.get(f"/api/feed/{post_id}").json()["liked"] is True

    act_as(client, alice)
    response = client.delete(f"/api/feed/{post_id}/like")
    assert response.status_code == 200
    assert (response.json()["like_count"], response.json()["liked"]) == (2, False)
    # Unliking again is fine.
    assert client.delete(f"/api/feed/{post_id}/like").json()["like_count"] == 2


def test_like_missing_post(client: TestClient) -> None:
    assert client.put(f"/api/feed/{uuid4()}/like").status_code == 404
    assert client.delete(f"/api/feed/{uuid4()}/like").status_code == 404


def test_users_comment_on_others_posts(client: TestClient, author: str, post: dict) -> None:
    post_id = post["id"]
    assert comments(client, post_id) == {"items": [], "next_cursor": None}

    new_user(client, "alice@example.com", "Alice")
    created = comment(client, post_id, "  Очень красиво!  ")
    assert created["text"] == "Очень красиво!"
    assert created["author"] == {"name": "Alice"}
    assert "alice@example.com" not in str(created)
    assert (created["mine"], created["can_delete"]) == (True, True)

    act_as(client, author)
    comment(client, post_id, "Спасибо")
    thread = comments(client, post_id)["items"]
    assert [c["text"] for c in thread] == ["Очень красиво!", "Спасибо"]  # oldest first
    assert [c["author"]["name"] for c in thread] == ["Alice", "Анимешка"]
    # The post's owner may delete anyone's comment under it, but it isn't theirs.
    assert (thread[0]["mine"], thread[0]["can_delete"]) == (False, True)
    assert feed(client)["items"][0]["comment_count"] == 2


def test_comment_validation(client: TestClient, post: dict) -> None:
    url = f"/api/feed/{post['id']}/comments"
    assert client.post(url, json={"text": ""}).status_code == 422
    assert client.post(url, json={"text": "   \n "}).status_code == 400
    assert client.post(url, json={"text": "x" * 1001}).status_code == 422
    assert client.post(url, json={}).status_code == 422
    assert client.post(f"/api/feed/{uuid4()}/comments", json={"text": "hi"}).status_code == 404
    assert client.get(f"/api/feed/{uuid4()}/comments").status_code == 404


def test_who_can_delete_a_comment(client: TestClient, author: str, post: dict) -> None:
    post_id = post["id"]
    alice = new_user(client, "alice@example.com", "Alice")
    by_alice = comment(client, post_id, "first")
    second = comment(client, post_id, "second")

    # A third user can neither delete nor see a delete button.
    new_user(client, "bob@example.com", "Bob")
    assert comments(client, post_id)["items"][0]["can_delete"] is False
    url = f"/api/feed/{post_id}/comments/{by_alice['id']}"
    assert client.delete(url).status_code == 403

    # The comment's author can.
    act_as(client, alice)
    assert client.delete(url).status_code == 204
    assert client.delete(url).status_code == 404

    # The post's owner can delete someone else's comment.
    act_as(client, author)
    assert client.delete(f"/api/feed/{post_id}/comments/{second['id']}").status_code == 204
    assert comments(client, post_id)["items"] == []
    # A comment id under a different post is not found.
    other = comment(client, post_id, "mine")
    assert client.delete(f"/api/feed/{uuid4()}/comments/{other['id']}").status_code == 404


def test_comments_page_oldest_first(client: TestClient, post: dict) -> None:
    post_id = post["id"]
    texts = [f"c{i}" for i in range(5)]
    for text in texts:
        comment(client, post_id, text)

    seen, cursor = [], None
    while True:
        page = comments(client, post_id, limit=2, **({"cursor": cursor} if cursor else {}))
        seen += [c["text"] for c in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == texts
    assert (
        client.get(f"/api/feed/{post_id}/comments", params={"cursor": "garbage"}).status_code == 400
    )


def test_unpublish_drops_likes_and_comments(client: TestClient, post: dict) -> None:
    post_id = post["id"]
    like(client, post_id)
    comment(client, post_id, "hi")

    client.delete(f"/api/jobs/{post['job_id']}/publish")
    assert client.get(f"/api/feed/{post_id}/comments").status_code == 404
    assert client.put(f"/api/feed/{post_id}/like").status_code == 404

    # Published again it is a fresh post with no reactions.
    client.post(f"/api/jobs/{post['job_id']}/publish")
    item = feed(client)["items"][0]
    assert (item["like_count"], item["comment_count"]) == (0, 0)


def test_deleting_job_with_reactions(client: TestClient, post: dict) -> None:
    like(client, post["id"])
    comment(client, post["id"], "hi")
    assert client.delete(f"/api/jobs/{post['job_id']}").status_code == 204
    assert feed(client)["items"] == []


def test_reactions_need_login(client: TestClient, post: dict) -> None:
    post_id = post["id"]
    created = comment(client, post_id, "hi")
    client.cookies.clear()
    assert client.put(f"/api/feed/{post_id}/like").status_code == 401
    assert client.delete(f"/api/feed/{post_id}/like").status_code == 401
    assert client.get(f"/api/feed/{post_id}/comments").status_code == 401
    assert client.post(f"/api/feed/{post_id}/comments", json={"text": "x"}).status_code == 401
    assert client.delete(f"/api/feed/{post_id}/comments/{created['id']}").status_code == 401
