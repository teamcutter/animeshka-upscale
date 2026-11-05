from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from src.features.feed.domain import FeedItem, FeedPage
from src.features.upscale.api.schemas import FileInfo
from src.features.upscale.domain import Mode


class Author(BaseModel):
    # Name only: the email of other users is never shown.
    name: str


class FeedItemResponse(BaseModel):
    id: UUID
    author: Author
    mine: bool
    mode: Mode
    input: FileInfo
    output: FileInfo
    image_url: str
    original_url: str
    published_at: datetime

    @classmethod
    def from_item(cls, item: FeedItem, viewer_id: UUID) -> "FeedItemResponse":
        job, post_id = item.job, item.post.id
        # Only finished jobs can be published, so the output is always there.
        assert job.output is not None
        return cls(
            id=post_id,
            author=Author(name=item.author_name),
            mine=job.owner_id == viewer_id,
            mode=job.mode,
            input=FileInfo.from_media(job.input),
            output=FileInfo.from_media(job.output),
            image_url=f"/api/feed/{post_id}/image",
            original_url=f"/api/feed/{post_id}/original",
            published_at=item.post.published_at,
        )


class FeedPageResponse(BaseModel):
    items: list[FeedItemResponse]
    # Pass as ?cursor= to get the next page; null on the last page.
    next_cursor: str | None

    @classmethod
    def from_page(cls, page: FeedPage, viewer_id: UUID) -> "FeedPageResponse":
        return cls(
            items=[FeedItemResponse.from_item(item, viewer_id) for item in page.items],
            next_cursor=page.next_cursor.encode() if page.next_cursor else None,
        )
