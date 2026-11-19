from typing import Protocol
from uuid import UUID

from src.features.feed.domain import (
    Comment,
    CommentView,
    Cursor,
    FeedItem,
    Post,
    SearchCursor,
    SearchFilters,
    TagCount,
)


class PostRepository(Protocol):
    def add(self, post: Post) -> Post | None:
        """Publish a job. Returns the existing post if the job is already published,
        None if the job no longer exists."""
        ...

    def delete_by_job(self, job_id: UUID) -> None: ...

    def set_description(self, post_id: UUID, description: str | None) -> bool:
        """Replaces the description and re-indexes its tags. False if the post is gone."""
        ...

    def get_item(self, post_id: UUID, viewer_id: UUID) -> FeedItem | None:
        """The post with its like/comment counts and whether `viewer_id` liked it."""
        ...

    def list_items(
        self,
        *,
        viewer_id: UUID,
        limit: int,
        before: Cursor | None = None,
        tags: list[str] | None = None,
    ) -> list[FeedItem]:
        """Newest first; with `before`, only posts older than that cursor;
        with `tags`, only posts that have every one of them."""
        ...

    def search(
        self,
        filters: SearchFilters,
        *,
        viewer_id: UUID,
        limit: int,
        after: SearchCursor | None = None,
    ) -> list[FeedItem]:
        """Posts having any of the query's terms (all posts if there are none), none of the
        excluded words, matching the filters; most matched terms first, then newest.
        Each item's `relevance` is its number of matched terms."""
        ...

    def popular_tags(self, *, prefix: str = "", limit: int) -> list[TagCount]:
        """Tags by number of posts, most used first; with `prefix`, only tags starting with it."""
        ...


class LikeRepository(Protocol):
    def add(self, post_id: UUID, user_id: UUID) -> bool:
        """Likes the post; liking it again changes nothing. False if the post is gone."""
        ...

    def remove(self, post_id: UUID, user_id: UUID) -> None: ...


class CommentRepository(Protocol):
    def add(self, comment: Comment) -> bool:
        """False if the post was deleted meanwhile."""
        ...

    def get(self, comment_id: UUID) -> CommentView | None: ...

    def delete(self, comment_id: UUID) -> None: ...

    def list_for_post(
        self, post_id: UUID, *, limit: int, after: Cursor | None = None
    ) -> list[CommentView]:
        """Oldest first, so a thread reads top to bottom; with `after`, only newer ones."""
        ...
