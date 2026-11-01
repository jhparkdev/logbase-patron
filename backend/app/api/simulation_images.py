"""시뮬레이터 이미지 업로드 라우터. 비교 실행 라우터(simulations.py)에 합쳐져 /simulations/images 가 된다.

이미지는 한 장씩 올려 asset_id 를 받고, 비교 실행 요청에는 asset_id 목록만 보낸다.
"""

import uuid
from typing import Any

from fastapi import APIRouter, UploadFile, status

from app.api.deps import DevUserDep
from app.api.simulation_deps import ImageStorageDep
from app.api.simulation_errors import SimulationRoute
from app.db import SessionDep
from app.schemas.simulation_error import (
    OriginNotAllowedResponse,
    SimulationErrorResponse,
    SimulationRequestErrorResponse,
)
from app.schemas.simulation_image import MAX_IMAGE_BYTES, ImageAssetRead, ImageLimits
from app.services.simulation_assets import save_image

_UPLOAD_ERRORS: dict[int | str, dict[str, Any]] = {
    status.HTTP_403_FORBIDDEN: {"model": OriginNotAllowedResponse},
    status.HTTP_413_CONTENT_TOO_LARGE: {"model": SimulationErrorResponse},
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": SimulationErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": SimulationRequestErrorResponse},
}

router = APIRouter(
    prefix="/images", tags=["simulation-images"], route_class=SimulationRoute
)


@router.post("", status_code=status.HTTP_201_CREATED, responses=_UPLOAD_ERRORS)
async def upload_simulation_image(
    file: UploadFile,
    user: DevUserDep,
    session: SessionDep,
    storage: ImageStorageDep,
) -> ImageAssetRead:
    """이미지 한 장을 올린다. 파일은 저장소에 두고 DB 에는 경로·해시만 남긴다."""
    # 한도보다 한 바이트만 더 읽는다. 큰 파일은 전부 읽지 않고도 거절할 수 있다
    data = await file.read(MAX_IMAGE_BYTES + 1)
    asset = await save_image(
        session,
        storage,
        data=data,
        filename=file.filename,
        uploaded_by=user.user_id,
        asset_id=uuid.uuid7(),
    )
    await session.commit()
    return ImageAssetRead(
        asset_id=asset.asset_id,
        mime_type=asset.mime_type,
        file_size_bytes=asset.file_size_bytes,
        original_filename=asset.original_filename,
    )


@router.get("/limits")
async def read_image_limits() -> ImageLimits:
    """이미지 입력 한도. 화면이 숫자를 따로 정하지 않고 이 값을 쓴다."""
    return ImageLimits.current()
