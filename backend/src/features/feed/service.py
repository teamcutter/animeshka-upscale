import logging
from pathlib import Path
from uuid import UUID

from src.features.feed.domain import (
    COMMENT_MAX_LENGTH,
    DESCRIPTION_MAX_LENGTH,
    Comment,
    CommentPage,
    CommentView,
    Cursor,
    FeedItem,
    FeedPage,
    Post,
    TagCount,
    normalize_tag,
)
from src.features.feed.ports import CommentRepository, LikeRepository, PostRepository
from src.features.upscale.domain import FileRole, Job, JobStatus
from src.features.upscale.service import UpscaleService
from src.shared.errors import BadRequestError, ForbiddenError, JobNotReadyError, NotFoundError

logger = logging.getLogger(__name__)


def _parse_cursor(value: str | None) -> Cursor | None:
    if not value:
        return None
    try:
        return Cursor.decode(value)
    except ValueError as exc:
        raise BadRequestError("Invalid cursor") from exc


def _clean_description(value: str | None) -> str | None:
    """Trimmed text; empty means no description."""
    value = (value or "").strip()
    if len(value) > DESCRIPTION_MAX_LENGTH:
        raise BadRequestError(f"Description is longer than {DESCRIPTION_MAX_LENGTH} characters")
    return value or None


def _parse_tags(values: list[str] | None) -> list[str]:
    try:
        return list(dict.fromkeys(normalize_tag(value) for value in values or []))
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc


class FeedService:
    def __init__(
        self,
        posts: PostRepository,
        upscale: UpscaleService,
        likes: LikeRepository,
        comments: CommentRepository,
    ) -> None:
        self._posts = posts
        self._upscale = upscale
        self._likes = likes
        self._comments = comments

    # --- publishing -------------------------------------------------------------------------

    def publish(self, job_id: UUID, owner_id: UUID, description: str | None = None) -> Job:
        """Shares any finished job (image or video, new or old) in the feed.

        The description's #hashtags make the post findable by tag. Publishing an already
        published job keeps the post (likes, comments, date); a description given then
        replaces the old one, None leaves it as it is.
        """
        text = _clean_description(description) if description is not None else None
        job = self._upscale.get_job(job_id, owner_id)
        if job.status is not JobStatus.DONE or job.output is None:
            raise JobNotReadyError(
                f"Job {job_id} is {job.status}, only finished jobs can be published"
            )
        new = Post(job_id=job.id, description=text)
        post = self._posts.add(new)
        if post is None:
            # Deleted by its owner between the check above and the insert.
            raise NotFoundError(f"Job {job_id} not found")
        if post.id == new.id:
            logger.info("Published job %s as post %s", job.id, post.id)
        elif description is not None and post.description != text:
            self._set_description(post.id, text)
        job.published_at = post.published_at
        job.post_id = post.id
        return job

    def edit_description(self, post_id: UUID, user_id: UUID, description: str | None) -> FeedItem:
        """Only the post's author can change its description (and with it the tags)."""
        text = _clean_description(description)
        item = self.get_item(post_id, user_id)
        if item.job.owner_id != user_id:
            raise ForbiddenError("Only the author of the post can edit its description")
        self._set_description(post_id, text)
        return self.get_item(post_id, user_id)

    def _set_description(self, post_id: UUID, text: str | None) -> None:
        if not self._posts.set_description(post_id, text):
            raise NotFoundError(f"Post {post_id} not found")

    def unpublish(self, job_id: UUID, owner_id: UUID) -> Job:
        """Removes the job from the feed (with its likes and comments); the job and files stay."""
        job = self._upscale.get_job(job_id, owner_id)
        self._posts.delete_by_job(job.id)
        job.published_at = None
        job.post_id = None
        return job

    # --- reading the feed -------------------------------------------------------------------

    def page(
        self,
        viewer_id: UUID,
        *,
        limit: int,
        cursor: str | None = None,
        tags: list[str] | None = None,
    ) -> FeedPage:
        """Newest first; with `tags` ('anime' or '#anime'), only posts having all of them."""
        before = _parse_cursor(cursor)
        wanted = _parse_tags(tags)
        # One extra row tells whether there is a next page without a COUNT query.
        items = self._posts.list_items(
            viewer_id=viewer_id, limit=limit + 1, before=before, tags=wanted
        )
        if len(items) <= limit:
            return FeedPage(items=items, next_cursor=None)
        items = items[:limit]
        last = items[-1].post
        return FeedPage(items=items, next_cursor=Cursor(at=last.published_at, id=last.id))

    def popular_tags(self, *, prefix: str = "", limit: int) -> list[TagCount]:
        """For search suggestions: tags by number of posts, optionally by prefix."""
        prefix = prefix.strip().removeprefix("#").lower()
        return self._posts.popular_tags(prefix=prefix, limit=limit)

    def get_item(self, post_id: UUID, viewer_id: UUID) -> FeedItem:
        item = self._posts.get_item(post_id, viewer_id)
        if item is None:
            raise NotFoundError(f"Post {post_id} not found")
        return item

    def media_path(self, post_id: UUID, viewer_id: UUID, role: FileRole) -> Path:
        """The upscaled result (OUTPUT) or the original upload (INPUT) of a published post."""
        job = self.get_item(post_id, viewer_id).job
        if role is FileRole.INPUT:
            return self._upscale.get_original_path(job)
        media = job.output if role is FileRole.OUTPUT else job.input
        if media is None:
            raise NotFoundError(f"Post {post_id} has no {role} file")
        return media.path

    # --- likes ------------------------------------------------------------------------------

    def like(self, post_id: UUID, user_id: UUID) -> FeedItem:
        """Any logged-in user, the author included, can like a post once."""
        if not self._likes.add(post_id, user_id):
            raise NotFoundError(f"Post {post_id} not found")
        return self.get_item(post_id, user_id)

    def unlike(self, post_id: UUID, user_id: UUID) -> FeedItem:
        self._likes.remove(post_id, user_id)
        return self.get_item(post_id, user_id)

    # --- comments ---------------------------------------------------------------------------

    def comments(
        self, post_id: UUID, viewer_id: UUID, *, limit: int, cursor: str | None = None
    ) -> CommentPage:
        after = _parse_cursor(cursor)
        self.get_item(post_id, viewer_id)  # 404 for a missing post, not an empty list
        items = self._comments.list_for_post(post_id, limit=limit + 1, after=after)
        if len(items) <= limit:
            return CommentPage(items=items, next_cursor=None)
        items = items[:limit]
        last = items[-1].comment
        return CommentPage(items=items, next_cursor=Cursor(at=last.created_at, id=last.id))

    def add_comment(self, post_id: UUID, author_id: UUID, text: str) -> CommentView:
        text = text.strip()
        if not text:
            raise BadRequestError("Comment is empty")
        if len(text) > COMMENT_MAX_LENGTH:
            raise BadRequestError(f"Comment is longer than {COMMENT_MAX_LENGTH} characters")
        comment = Comment(post_id=post_id, author_id=author_id, text=text)
        if not self._comments.add(comment):
            raise NotFoundError(f"Post {post_id} not found")
        view = self._comments.get(comment.id)
        if view is None:  # the post was unpublished right after the insert
            raise NotFoundError(f"Post {post_id} not found")
        return view

    def delete_comment(self, post_id: UUID, comment_id: UUID, user_id: UUID) -> None:
        """The comment's author or the post's owner can delete it."""
        view = self._comments.get(comment_id)
        if view is None or view.comment.post_id != post_id:
            raise NotFoundError(f"Comment {comment_id} not found")
        if user_id not in (view.comment.author_id, view.post_owner_id):
            raise ForbiddenError("Only the author of the comment or of the post can delete it")
        self._comments.delete(comment_id)
