import logging
from pathlib import Path
from uuid import UUID

from src.features.feed.domain import FeedCursor, FeedItem, FeedPage, Post
from src.features.feed.ports import PostRepository
from src.features.upscale.domain import FileRole, Job, JobStatus, MediaKind
from src.features.upscale.service import UpscaleService
from src.shared.errors import BadRequestError, ConflictError, JobNotReadyError, NotFoundError

logger = logging.getLogger(__name__)


class FeedService:
    def __init__(self, posts: PostRepository, upscale: UpscaleService) -> None:
        self._posts = posts
        self._upscale = upscale

    def publish(self, job_id: UUID, owner_id: UUID) -> Job:
        """Shares a finished image in the feed; publishing it again changes nothing."""
        job = self._upscale.get_job(job_id, owner_id)
        if job.kind is not MediaKind.IMAGE:
            raise ConflictError("Only images can be published for now")
        if job.status is not JobStatus.DONE or job.output is None:
            raise JobNotReadyError(
                f"Job {job_id} is {job.status}, only finished jobs can be published"
            )
        post = self._posts.add(Post(job_id=job.id))
        if post is None:
            # Deleted by its owner between the check above and the insert.
            raise NotFoundError(f"Job {job_id} not found")
        if job.published_at is None:
            logger.info("Published job %s as post %s", job.id, post.id)
        job.published_at = post.published_at
        return job

    def unpublish(self, job_id: UUID, owner_id: UUID) -> Job:
        """Removes the job from the feed; the job itself and its files stay."""
        job = self._upscale.get_job(job_id, owner_id)
        self._posts.delete_by_job(job.id)
        job.published_at = None
        return job

    def page(self, *, limit: int, cursor: str | None = None) -> FeedPage:
        before = None
        if cursor:
            try:
                before = FeedCursor.decode(cursor)
            except ValueError as exc:
                raise BadRequestError("Invalid feed cursor") from exc
        # One extra row tells whether there is a next page without a COUNT query.
        items = self._posts.list_items(limit=limit + 1, before=before)
        if len(items) <= limit:
            return FeedPage(items=items, next_cursor=None)
        items = items[:limit]
        return FeedPage(items=items, next_cursor=FeedCursor.after(items[-1].post))

    def get_item(self, post_id: UUID) -> FeedItem:
        item = self._posts.get_item(post_id)
        if item is None:
            raise NotFoundError(f"Post {post_id} not found")
        return item

    def media_path(self, post_id: UUID, role: FileRole) -> Path:
        """The upscaled result (OUTPUT) or the original upload (INPUT) of a published post."""
        job = self.get_item(post_id).job
        media = job.output if role is FileRole.OUTPUT else job.input
        if media is None:
            raise NotFoundError(f"Post {post_id} has no {role} file")
        return media.path
