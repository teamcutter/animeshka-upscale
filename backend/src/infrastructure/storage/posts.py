from uuid import UUID

from sqlalchemy import Select, and_, delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager, sessionmaker

from src.features.feed.domain import FeedCursor, FeedItem, Post
from src.infrastructure.db.models import JobRow, PostRow, UserRow
from src.infrastructure.storage.sql import aware_utc, job_from_row


def _to_post(row: PostRow) -> Post:
    return Post(id=row.id, job_id=row.job_id, published_at=aware_utc(row.published_at))


def _feed_query() -> Select[tuple[PostRow, str]]:
    # Inner joins: posts of jobs without an owner (pre-accounts) can't exist, see FeedService.
    return (
        select(PostRow, UserRow.name)
        .join(PostRow.job)
        .join(UserRow, UserRow.id == JobRow.user_id)
        .options(contains_eager(PostRow.job))
    )


class SqlPostRepository:
    """Posts of the public feed, read together with their job, files and author."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def add(self, post: Post) -> Post | None:
        try:
            with self._sessions.begin() as session:
                session.add(PostRow(id=post.id, job_id=post.job_id, published_at=post.published_at))
            return post
        except IntegrityError:
            # Unique job_id: already published (also two publishes at once);
            # foreign key: the job was deleted meanwhile.
            with self._sessions() as session:
                row = session.scalar(select(PostRow).where(PostRow.job_id == post.job_id))
                return _to_post(row) if row else None

    def delete_by_job(self, job_id: UUID) -> None:
        with self._sessions.begin() as session:
            session.execute(delete(PostRow).where(PostRow.job_id == job_id))

    def get_item(self, post_id: UUID) -> FeedItem | None:
        with self._sessions() as session:
            row = session.execute(_feed_query().where(PostRow.id == post_id)).first()
            return self._to_item(*row) if row else None

    def list_items(self, *, limit: int, before: FeedCursor | None = None) -> list[FeedItem]:
        stmt = _feed_query().order_by(PostRow.published_at.desc(), PostRow.id.desc()).limit(limit)
        if before is not None:
            stmt = stmt.where(
                or_(
                    PostRow.published_at < before.published_at,
                    and_(PostRow.published_at == before.published_at, PostRow.id < before.post_id),
                )
            )
        with self._sessions() as session:
            return [self._to_item(post, name) for post, name in session.execute(stmt)]

    @staticmethod
    def _to_item(row: PostRow, author_name: str) -> FeedItem:
        return FeedItem(post=_to_post(row), job=job_from_row(row.job), author_name=author_name)
