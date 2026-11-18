from functools import partial
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from src.features.auth.api.deps import CurrentUser
from src.features.qop.models import Source
from src.features.qop.service import ModelsUnavailableError, bundle_path, load_models, predict
from src.features.upscale.api.router import read_upload

router = APIRouter(prefix="/api/qop", tags=["QoP models"])


@router.get("/models")
def catalog(request: Request, user: CurrentUser, source: Annotated[Source, Query()] = "trained"):
    container = request.app.state.container
    bundle = load_models(container.settings.storage.dir, source)
    automatic = {"automatic": container.qop.status()} if source == "trained" else {}
    if bundle is None:
        return {"available": False, "source": source, **automatic}
    return {"available": True, **bundle.model_dump(mode="json"), **automatic}


@router.get("/models/download")
def download(request: Request, user: CurrentUser, source: Annotated[Source, Query()] = "trained"):
    storage = request.app.state.container.settings.storage.dir
    if load_models(storage, source) is None:
        raise ModelsUnavailableError("No trained QoP models are available yet.")
    return FileResponse(bundle_path(storage, source), filename=f"qop-{source}-models.json")


@router.post("/predict")
async def prediction(
    request: Request,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    content_type: Annotated[str, Form(min_length=1, max_length=64)],
    max_size: Annotated[int, Form(ge=64, le=4096)] = 2048,
    source: Annotated[Source, Query()] = "trained",
):
    settings = request.app.state.container.settings
    data = await read_upload(file, settings.image.max_size_mb * 1024 * 1024)
    return await run_in_threadpool(
        partial(
            predict,
            settings.storage.dir,
            source,
            data,
            content_type,
            max_size,
            settings.image,
        )
    )
