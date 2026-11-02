"""시뮬레이터 이미지 업로드·내려받기 라우터. 비교 실행 라우터(simulations.py)에 합쳐져 /simulations/images 가 된다.

이미지는 한 장씩 올려 asset_id 를 받고, 비교 실행 요청에는 asset_id 목록만 보낸다.
이력·재실행 화면은 asset_id 로 파일을 다시 받아 그린다.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Response, UploadFile, status

from app.api.deps import DevUserDep
from app.api.simulation_deps import ImageStorageDep
from app.api.simulation_errors import SimulationRoute
from app.db import SessionDep
from app.schemas.simulation_error import (
    OriginNotAllowedResponse,
    SimulationErrorResponse,
    SimulationRequestErrorResponse,
)
from app.schemas.simulation_image import (
    MAX_IMAGE_BYTES,
    ImageAssetRead,
    ImageLimits,
    ImageMimeType,
)
from app.services.simulation_assets import read_input_image, save_image
from app.services.simulation_image_source import StoredImage

_UPLOAD_ERRORS: dict[int | str, dict[str, Any]] = {
    status.HTTP_403_FORBIDDEN: {"model": OriginNotAllowedResponse},
    status.HTTP_413_CONTENT_TOO_LARGE: {"model": SimulationErrorResponse},
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": SimulationErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": SimulationRequestErrorResponse},
}

# 파일은 덮어쓰지 않으므로 같은 주소의 내용이 바뀌지 않는다. 화면 밖 공용 캐시에는 남기지 않는다
_IMMUTABLE_PRIVATE = "private, max-age=31536000, immutable"
# 그림이 아닌 내용이 섞여 와도 이 주소를 문서로 열어 스크립트가 도는 일이 없게 한다
_NO_ACTIVE_CONTENT = "default-src 'none'; sandbox"

IMAGE_FILE_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_200_OK: {
        "content": {mime.value: {} for mime in ImageMimeType},
        "description": "이미지 파일 내용",
    },
    status.HTTP_404_NOT_FOUND: {"model": SimulationErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": SimulationRequestErrorResponse},
}


def image_file_response(image: StoredImage) -> Response:
    """저장된 이미지를 기록된 형식 그대로 내려 준다. 브라우저가 형식을 추측하지 않게 한다."""
    return Response(
        content=image.data,
        media_type=image.mime_type,
        headers={
            "Cache-Control": _IMMUTABLE_PRIVATE,
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": _NO_ACTIVE_CONTENT,
        },
    )


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


# /limits 보다 뒤에 둔다. 앞에 두면 "limits" 를 asset_id 로 읽으려다 422 가 난다
@router.get("/{asset_id}", response_class=Response, responses=IMAGE_FILE_RESPONSES)
async def download_simulation_image(
    asset_id: uuid.UUID, session: SessionDep, storage: ImageStorageDep
) -> Response:
    """올린 이미지 파일. 화면은 <img src> 로 이 주소를 쓴다."""
    return image_file_response(await read_input_image(session, storage, asset_id))
