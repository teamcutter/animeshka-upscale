from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from src.features.upscale.api.schemas import JobResponse
from src.features.upscale.domain import Job, JobStatus, Mode
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


def schedule(
    request: Request, background: BackgroundTasks, service: UpscaleService, job: Job
) -> None:
    """Embedded mode runs the job in this process; otherwise it waits for src.worker."""
    if request.app.state.container.settings.worker.embedded:
        background.add_task(service.process_job, job.id)


@router.post("/upscale", status_code=202, response_model=JobResponse)
async def upscale_image(
    request: Request,
    service: Service,
    background: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    mode: Annotated[Mode, Form()] = Mode.X2K,
    max_size: Annotated[int, Form(ge=64, le=4096)] = 1920,
) -> JobResponse:
    data = await read_upload(file, service.image_limit_bytes)
    job = await run_in_threadpool(
        service.create_image_job, file.filename or "upload", data, mode, max_size
    )
    schedule(request, background, service, job)
    return JobResponse.from_job(job)


@router.post("/upscale/video", status_code=202, response_model=JobResponse)
async def upscale_video(
    request: Request,
    service: Service,
    background: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    mode: Annotated[Mode, Form()] = Mode.X2K,
) -> JobResponse:
    data = await read_upload(file, service.video_limit_bytes)
    job = await run_in_threadpool(service.create_video_job, file.filename or "upload", data, mode)
    schedule(request, background, service, job)
    return JobResponse.from_job(job)


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs(
    service: Service,
    status: JobStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[JobResponse]:
    jobs = service.list_jobs(status=status, limit=limit, offset=offset)
    return [JobResponse.from_job(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID, service: Service) -> JobResponse:
    return JobResponse.from_job(service.get_job(job_id))


@router.get("/jobs/{job_id}/result", response_class=FileResponse)
def get_job_result(job_id: UUID, service: Service) -> FileResponse:
    return FileResponse(service.get_result_path(job_id))
