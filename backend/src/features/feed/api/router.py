from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse

from src.features.auth.api.deps import CurrentUser
from src.features.feed.api.schemas import FeedItemResponse, FeedPageResponse
from src.features.feed.service import FeedService
from src.features.upscale.api.schemas import JobResponse
from src.features.upscale.domain import FileRole

router = APIRouter(prefix="/api", tags=["feed"])


def get_feed_service(request: Request) -> FeedService:
    return request.app.state.container.feed_service


Service = Annotated[FeedService, Depends(get_feed_service)]


@router.post("/jobs/{job_id}/publish", response_model=JobResponse)
def publish_job(job_id: UUID, user: CurrentUser, service: Service) -> JobResponse:
    """Share a finished image of mine in the feed (409 if it is not done yet)."""
    return JobResponse.from_job(service.publish(job_id, user.id))


@router.delete("/jobs/{job_id}/publish", response_model=JobResponse)
def unpublish_job(job_id: UUID, user: CurrentUser, service: Service) -> JobResponse:
    """Remove my job from the feed; the job stays in my history."""
    return JobResponse.from_job(service.unpublish(job_id, user.id))


@router.get("/feed", response_model=FeedPageResponse)
def get_feed(
    user: CurrentUser,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query(max_length=64)] = None,
) -> FeedPageResponse:
    """Published works of all users, newest first."""
    return FeedPageResponse.from_page(service.page(limit=limit, cursor=cursor), user.id)


@router.get("/feed/{post_id}", response_model=FeedItemResponse)
def get_post(post_id: UUID, user: CurrentUser, service: Service) -> FeedItemResponse:
    return FeedItemResponse.from_item(service.get_item(post_id), user.id)


# Shown inline (no Content-Disposition: attachment): downloading from the feed comes later.
@router.get("/feed/{post_id}/image", response_class=FileResponse)
def get_post_image(post_id: UUID, _: CurrentUser, service: Service) -> FileResponse:
    return FileResponse(service.media_path(post_id, FileRole.OUTPUT))


@router.get("/feed/{post_id}/original", response_class=FileResponse)
def get_post_original(post_id: UUID, _: CurrentUser, service: Service) -> FileResponse:
    return FileResponse(service.media_path(post_id, FileRole.INPUT))
