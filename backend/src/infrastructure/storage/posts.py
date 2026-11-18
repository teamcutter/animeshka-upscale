from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, Select, and_, delete, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import InstrumentedAttribute, Session, contains_eager, sessionmaker

from src.features.feed.domain import Comment, CommentView, Cursor, FeedItem, Post
from src.features.upscale.domain import now_utc
from src.infrastructure.db.models import CommentRow, JobRow, LikeRow, PostRow, UserRow
from src.infrastructure.storage.sql import aware_utc, job_from_row


def _to_post(row: PostRow) -> Post:
    return Post(id=row.id, job_id=row.job_id, published_at=aware_utc(row.published_at))


def _feed_query(viewer_id: UUID) -> Select[tuple[PostRow, str, int, int, bool]]:
    like_count = (
        select(func.count()).where(LikeRow.post_id == PostRow.id).correlate(PostRow)
    ).scalar_subquery()
    comment_count = (
        select(func.count()).where(CommentRow.post_id == PostRow.id).correlate(PostRow)
    ).scalar_subquery()
    liked = exists().where(LikeRow.post_id == PostRow.id, LikeRow.user_id == viewer_id)
    # Inner joins: posts of jobs without an owner (pre-accounts) can't exist, see FeedService.
    return (
        select(PostRow, UserRow.name, like_count, comment_count, liked)
        .join(PostRow.job)
        .join(UserRow, UserRow.id == JobRow.user_id)
        .options(contains_eager(PostRow.job))
    )


def _past(
    at_column: InstrumentedAttribute[datetime],
    id_column: InstrumentedAttribute[UUID],
    cursor: Cursor,
    *,
    older: bool,
) -> ColumnElement[bool]:
    """Rows strictly before (older=True) or after the cursor in (timestamp, id) order."""
    if older:
        return or_(at_column < cursor.at, and_(at_column == cursor.at, id_column < cursor.id))
    return or_(at_column > cursor.at, and_(at_column == cursor.at, id_column > cursor.id))


class SqlPostRepository:
    """Posts of the public feed, read together with their job, files, author and reactions."""

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

    def get_item(self, post_id: UUID, viewer_id: UUID) -> FeedItem | None:
        with self._sessions() as session:
            row = session.execute(_feed_query(viewer_id).where(PostRow.id == post_id)).first()
            return self._to_item(*row) if row else None

    def list_items(
        self, *, viewer_id: UUID, limit: int, before: Cursor | None = None
    ) -> list[FeedItem]:
        stmt = (
            _feed_query(viewer_id)
            .order_by(PostRow.published_at.desc(), PostRow.id.desc())
            .limit(limit)
        )
        if before is not None:
            stmt = stmt.where(_past(PostRow.published_at, PostRow.id, before, older=True))
        with self._sessions() as session:
            return [self._to_item(*row) for row in session.execute(stmt)]

    @staticmethod
    def _to_item(
        row: PostRow, author_name: str, like_count: int, comment_count: int, liked: bool
    ) -> FeedItem:
        return FeedItem(
            post=_to_post(row),
            job=job_from_row(row.job),
            author_name=author_name,
            like_count=like_count,
            comment_count=comment_count,
            liked=bool(liked),
        )


class SqlLikeRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def add(self, post_id: UUID, user_id: UUID) -> bool:
        try:
            with self._sessions.begin() as session:
                session.add(LikeRow(post_id=post_id, user_id=user_id, created_at=now_utc()))
            return True
        except IntegrityError:
            # Primary key: liked already (or two likes at once); foreign key: no such post.
            with self._sessions() as session:
                return session.get(PostRow, post_id) is not None

    def remove(self, post_id: UUID, user_id: UUID) -> None:
        with self._sessions.begin() as session:
            session.execute(
                delete(LikeRow).where(LikeRow.post_id == post_id, LikeRow.user_id == user_id)
            )


def _comment_query() -> Select[tuple[CommentRow, str, UUID | None]]:
    return (
        select(CommentRow, UserRow.name, JobRow.user_id)
        .join(UserRow, UserRow.id == CommentRow.user_id)
        .join(PostRow, PostRow.id == CommentRow.post_id)
        .join(JobRow, JobRow.id == PostRow.job_id)
    )


def _to_comment_view(row: CommentRow, author_name: str, post_owner_id: UUID | None) -> CommentView:
    return CommentView(
        comment=Comment(
            id=row.id,
            post_id=row.post_id,
            author_id=row.user_id,
            text=row.text,
            created_at=aware_utc(row.created_at),
        ),
        author_name=author_name,
        post_owner_id=post_owner_id,
    )


class SqlCommentRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def add(self, comment: Comment) -> bool:
        try:
            with self._sessions.begin() as session:
                session.add(
                    CommentRow(
                        id=comment.id,
                        post_id=comment.post_id,
                        user_id=comment.author_id,
                        text=comment.text,
                        created_at=comment.created_at,
                    )
                )
            return True
        except IntegrityError:  # foreign key: the post doesn't exist (anymore)
            return False

    def get(self, comment_id: UUID) -> CommentView | None:
        with self._sessions() as session:
            row = session.execute(_comment_query().where(CommentRow.id == comment_id)).first()
            return _to_comment_view(*row) if row else None

    def delete(self, comment_id: UUID) -> None:
        with self._sessions.begin() as session:
            session.execute(delete(CommentRow).where(CommentRow.id == comment_id))

    def list_for_post(
        self, post_id: UUID, *, limit: int, after: Cursor | None = None
    ) -> list[CommentView]:
        stmt = (
            _comment_query()
            .where(CommentRow.post_id == post_id)
            .order_by(CommentRow.created_at, CommentRow.id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(_past(CommentRow.created_at, CommentRow.id, after, older=False))
        with self._sessions() as session:
            return [_to_comment_view(*row) for row in session.execute(stmt)]
