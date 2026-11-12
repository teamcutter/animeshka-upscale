from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from src.features.feed.domain import (
    COMMENT_MAX_LENGTH,
    CommentPage,
    CommentView,
    FeedItem,
    FeedPage,
)
from src.features.upscale.api.schemas import FileInfo
from src.features.upscale.domain import MediaKind, Mode


class Author(BaseModel):
    # Name only: the email of other users is never shown.
    name: str


class FeedItemResponse(BaseModel):
    id: UUID
    author: Author
    mine: bool
    kind: MediaKind
    mode: Mode
    input: FileInfo
    output: FileInfo
    # The upscaled image or video; the browser picks the type from Content-Type.
    media_url: str
    original_url: str
    like_count: int
    liked: bool
    comment_count: int
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
            kind=job.kind,
            mode=job.mode,
            input=FileInfo.from_media(job.input),
            output=FileInfo.from_media(job.output),
            media_url=f"/api/feed/{post_id}/media",
            original_url=f"/api/feed/{post_id}/original",
            like_count=item.like_count,
            liked=item.liked,
            comment_count=item.comment_count,
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


class CommentRequest(BaseModel):
    # Whitespace-only text is rejected by the service after stripping.
    text: Annotated[str, Field(min_length=1, max_length=COMMENT_MAX_LENGTH)]


class CommentResponse(BaseModel):
    id: UUID
    post_id: UUID
    author: Author
    mine: bool
    # The comment's author and the post's owner may delete it.
    can_delete: bool
    text: str
    created_at: datetime

    @classmethod
    def from_view(cls, view: CommentView, viewer_id: UUID) -> "CommentResponse":
        comment = view.comment
        mine = comment.author_id == viewer_id
        return cls(
            id=comment.id,
            post_id=comment.post_id,
            author=Author(name=view.author_name),
            mine=mine,
            can_delete=mine or view.post_owner_id == viewer_id,
            text=comment.text,
            created_at=comment.created_at,
        )


class CommentPageResponse(BaseModel):
    items: list[CommentResponse]
    next_cursor: str | None

    @classmethod
    def from_page(cls, page: CommentPage, viewer_id: UUID) -> "CommentPageResponse":
        return cls(
            items=[CommentResponse.from_view(view, viewer_id) for view in page.items],
            next_cursor=page.next_cursor.encode() if page.next_cursor else None,
        )
