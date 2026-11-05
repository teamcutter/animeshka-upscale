from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from src.features.upscale.domain import Job, now_utc

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_MICROSECOND = timedelta(microseconds=1)


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


@dataclass(frozen=True)
class FeedCursor:
    """Where the next feed page starts: posts strictly older than this one.

    Paging by (published_at, id) instead of offset keeps pages stable while new posts arrive.
    """

    published_at: datetime
    post_id: UUID

    @classmethod
    def after(cls, post: Post) -> "FeedCursor":
        return cls(published_at=post.published_at, post_id=post.id)

    def encode(self) -> str:
        micros = (self.published_at - _EPOCH) // _MICROSECOND
        return f"{micros}.{self.post_id.hex}"

    @classmethod
    def decode(cls, value: str) -> "FeedCursor":
        """Raises ValueError if the cursor was not made by encode()."""
        micros, _, post_id = value.partition(".")
        try:
            published_at = _EPOCH + int(micros) * _MICROSECOND
        except OverflowError as exc:  # a number far outside the datetime range
            raise ValueError(f"Cursor date out of range: {micros}") from exc
        return cls(published_at=published_at, post_id=UUID(hex=post_id))


@dataclass
class FeedPage:
    items: list[FeedItem]
    next_cursor: FeedCursor | None
