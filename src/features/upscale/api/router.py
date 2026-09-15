from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from src.features.upscale.api.schemas import JobResponse
from src.features.upscale.domain import Mode
from src.features.upscale.service import UpscaleService
from src.shared.errors import PayloadTooLargeError

router = APIRouter(prefix="/api", tags=["upscale"])

CHUNK_SIZE = 1024 * 1024


def get_service(request: Request) -> UpscaleService:
    return request.app.state.container.upscale_service


Service = Annotated[UpscaleService, Depends(get_service)]


async def read_upload(file: UploadFile, limit: int) -> bytes:
    """Read the upload in chunks so oversized files are rejected early."""
    buffer = bytearray()
    while chunk := await file.read(CHUNK_SIZE):
        buffer.extend(chunk)
        if len(buffer) > limit:
            raise PayloadTooLargeError(f"File exceeds {limit // CHUNK_SIZE} MB")
    return bytes(buffer)


@router.post("/upscale", status_code=202, response_model=JobResponse)
async def upscale_image(
    service: Service,
    background: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    mode: Annotated[Mode, Form()] = Mode.X2K,
    max_size: Annotated[int, Form(ge=64, le=4096)] = 1920,
) -> JobResponse:
    data = await read_upload(file, service.image_limit_bytes)
    job = await run_in_threadpool(service.create_image_job, file.filename or "upload", data, mode)
    background.add_task(service.process_image, job.id, max_size)
    return JobResponse.from_job(job)


@router.post("/upscale/video", status_code=202, response_model=JobResponse)
async def upscale_video(
    service: Service,
    background: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    mode: Annotated[Mode, Form()] = Mode.X2K,
) -> JobResponse:
    data = await read_upload(file, service.video_limit_bytes)
    job = await run_in_threadpool(service.create_video_job, file.filename or "upload", data, mode)
    background.add_task(service.process_video, job.id)
    return JobResponse.from_job(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID, service: Service) -> JobResponse:
    return JobResponse.from_job(service.get_job(job_id))


@router.get("/jobs/{job_id}/result", response_class=FileResponse)
def get_job_result(job_id: UUID, service: Service) -> FileResponse:
    return FileResponse(service.get_result_path(job_id))
