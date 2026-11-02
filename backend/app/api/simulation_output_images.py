"""이미지 생성 결과 내려받기 라우터. 비교 실행 라우터(simulations.py)에 합쳐져 /simulations/output-images 가 된다.

결과 조회 응답의 칸마다 output_images 의 output_asset_id 로 이 주소를 만든다.
"""

import uuid

from fastapi import APIRouter, Response

from app.api.simulation_deps import ImageStorageDep
from app.api.simulation_errors import SimulationRoute
from app.api.simulation_images import IMAGE_FILE_RESPONSES, image_file_response
from app.db import SessionDep
from app.services.simulation_output_assets import read_output_image

router = APIRouter(
    prefix="/output-images", tags=["simulation-images"], route_class=SimulationRoute
)


@router.get(
    "/{output_asset_id}", response_class=Response, responses=IMAGE_FILE_RESPONSES
)
async def download_output_image(
    output_asset_id: uuid.UUID, session: SessionDep, storage: ImageStorageDep
) -> Response:
    """모델이 만든 이미지 파일. 화면은 <img src> 로 이 주소를 쓴다."""
    return image_file_response(
        await read_output_image(session, storage, output_asset_id)
    )
