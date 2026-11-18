from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from src.features.upscale.domain import Job, now_utc

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_MICROSECOND = timedelta(microseconds=1)

COMMENT_MAX_LENGTH = 1000


@dataclass
class Post:
    """A finished job its owner shared in the public feed."""

    job_id: UUID
    id: UUID = field(default_factory=uuid4)
    published_at: datetime = field(default_factory=now_utc)


@dataclass
class FeedItem:
    post: Post
    job: Job
    # Only the display name: the feed never shows the author's email.
    author_name: str
    like_count: int = 0
    comment_count: int = 0
    # Whether the user reading the feed liked this post.
    liked: bool = False


@dataclass
class Comment:
    post_id: UUID
    author_id: UUID
    text: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class CommentView:
    comment: Comment
    author_name: str
    # The owner of the commented post: they may delete any comment under it.
    post_owner_id: UUID | None


@dataclass(frozen=True)
class Cursor:
    """Where the next page starts: rows strictly past (at, id) in the listing order.

    Paging by (timestamp, id) instead of offset keeps pages stable while new rows arrive.
    The feed uses it for posts (published_at), comments for their created_at.
    """

    at: datetime
    id: UUID

    def encode(self) -> str:
        micros = (self.at - _EPOCH) // _MICROSECOND
        return f"{micros}.{self.id.hex}"

    @classmethod
    def decode(cls, value: str) -> "Cursor":
        """Raises ValueError if the cursor was not made by encode()."""
        micros, _, row_id = value.partition(".")
        try:
            at = _EPOCH + int(micros) * _MICROSECOND
        except OverflowError as exc:  # a number far outside the datetime range
            raise ValueError(f"Cursor date out of range: {micros}") from exc
        return cls(at=at, id=UUID(hex=row_id))


@dataclass
class FeedPage:
    items: list[FeedItem]
    next_cursor: Cursor | None


@dataclass
class CommentPage:
    items: list[CommentView]
    next_cursor: Cursor | None
