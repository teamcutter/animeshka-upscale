from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import FileResponse

from src.features.auth.api.deps import CurrentUser
from src.features.feed.api.schemas import (
    CommentPageResponse,
    CommentRequest,
    CommentResponse,
    FeedItemResponse,
    FeedPageResponse,
)
from src.features.feed.service import FeedService
from src.features.upscale.api.schemas import JobResponse
from src.features.upscale.domain import FileRole

router = APIRouter(prefix="/api", tags=["feed"])


def get_feed_service(request: Request) -> FeedService:
    return request.app.state.container.feed_service


Service = Annotated[FeedService, Depends(get_feed_service)]
Limit = Annotated[int, Query(ge=1, le=50)]
CursorParam = Annotated[str | None, Query(max_length=64)]


@router.post("/jobs/{job_id}/publish", response_model=JobResponse)
def publish_job(job_id: UUID, user: CurrentUser, service: Service) -> JobResponse:
    """Share any finished job of mine, image or video, new or old (409 if not done yet)."""
    return JobResponse.from_job(service.publish(job_id, user.id))


@router.delete("/jobs/{job_id}/publish", response_model=JobResponse)
def unpublish_job(job_id: UUID, user: CurrentUser, service: Service) -> JobResponse:
    """Remove my job from the feed together with its likes and comments; the job stays."""
    return JobResponse.from_job(service.unpublish(job_id, user.id))


@router.get("/feed", response_model=FeedPageResponse)
def get_feed(
    user: CurrentUser, service: Service, limit: Limit = 20, cursor: CursorParam = None
) -> FeedPageResponse:
    """Published works of all users, newest first."""
    return FeedPageResponse.from_page(service.page(user.id, limit=limit, cursor=cursor), user.id)


@router.get("/feed/{post_id}", response_model=FeedItemResponse)
def get_post(post_id: UUID, user: CurrentUser, service: Service) -> FeedItemResponse:
    return FeedItemResponse.from_item(service.get_item(post_id, user.id), user.id)


# Shown inline (no Content-Disposition: attachment): downloading from the feed comes later.
@router.get("/feed/{post_id}/media", response_class=FileResponse)
def get_post_media(post_id: UUID, user: CurrentUser, service: Service) -> FileResponse:
    """The upscaled image (PNG) or video (MP4) of the post."""
    return FileResponse(service.media_path(post_id, user.id, FileRole.OUTPUT))


@router.get("/feed/{post_id}/original", response_class=FileResponse)
def get_post_original(post_id: UUID, user: CurrentUser, service: Service) -> FileResponse:
    return FileResponse(service.media_path(post_id, user.id, FileRole.INPUT))


@router.put("/feed/{post_id}/like", response_model=FeedItemResponse)
def like_post(post_id: UUID, user: CurrentUser, service: Service) -> FeedItemResponse:
    """Like the post; liking it again changes nothing. Returns the post with new counts."""
    return FeedItemResponse.from_item(service.like(post_id, user.id), user.id)


@router.delete("/feed/{post_id}/like", response_model=FeedItemResponse)
def unlike_post(post_id: UUID, user: CurrentUser, service: Service) -> FeedItemResponse:
    return FeedItemResponse.from_item(service.unlike(post_id, user.id), user.id)


@router.get("/feed/{post_id}/comments", response_model=CommentPageResponse)
def list_comments(
    post_id: UUID,
    user: CurrentUser,
    service: Service,
    limit: Limit = 50,
    cursor: CursorParam = None,
) -> CommentPageResponse:
    """Comments of the post, oldest first."""
    page = service.comments(post_id, user.id, limit=limit, cursor=cursor)
    return CommentPageResponse.from_page(page, user.id)


@router.post(
    "/feed/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    post_id: UUID, body: CommentRequest, user: CurrentUser, service: Service
) -> CommentResponse:
    """Any logged-in user can comment on any post, their own included."""
    return CommentResponse.from_view(service.add_comment(post_id, user.id, body.text), user.id)


@router.delete("/feed/{post_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    post_id: UUID, comment_id: UUID, user: CurrentUser, service: Service
) -> Response:
    """Delete a comment: allowed for its author and for the post's owner (403 otherwise)."""
    service.delete_comment(post_id, comment_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
