from typing import Protocol
from uuid import UUID

from src.features.feed.domain import FeedCursor, FeedItem, Post


class PostRepository(Protocol):
    def add(self, post: Post) -> Post | None:
        """Publish a job. Returns the existing post if the job is already published,
        None if the job no longer exists."""
        ...

    def delete_by_job(self, job_id: UUID) -> None: ...

    def get_item(self, post_id: UUID) -> FeedItem | None: ...

    def list_items(self, *, limit: int, before: FeedCursor | None = None) -> list[FeedItem]:
        """Newest first; with `before`, only posts older than that cursor."""
        ...
