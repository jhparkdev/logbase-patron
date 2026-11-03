"""시뮬레이터의 생성 종류(텍스트·이미지)와 이미지 생성 결과의 계약."""

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# 한 칸에서 만들 이미지 수의 상한. OpenRouter 는 10장까지 받지만 한 번의 실수로 큰 비용이 나가지 않게 줄였다
MAX_OUTPUT_IMAGE_COUNT = 4
# 해상도는 모델마다 이름이 달라("2K", "1024x1024") 글자 모양과 길이만 막고 값은 OpenRouter 가 판단한다
MAX_RESOLUTION_LENGTH = 16


class OutputType(StrEnum):
    """실행 한 건이 만드는 결과. 한 실행의 모든 칸이 같은 종류다."""

    TEXT = "TEXT"
    IMAGE = "IMAGE"


class ImageQuality(StrEnum):
    """OpenRouter 이미지 생성의 quality 값."""

    AUTO = "auto"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ImageConfig(BaseModel):
    """이미지 생성 옵션. 모든 칸에 같은 값을 보낸다. 보내지 않은 항목은 모델 기본값을 쓴다."""

    model_config = ConfigDict(extra="forbid")

    # strict: "2" 나 1.5 처럼 정수가 아닌 값은 변환하지 않고 거절한다
    n: Annotated[int, Field(strict=True, ge=1, le=MAX_OUTPUT_IMAGE_COUNT)] | None = None
    aspect_ratio: Annotated[str, Field(pattern=r"^\d{1,2}:\d{1,2}$")] | None = None
    resolution: (
        Annotated[str, Field(pattern=rf"^[0-9A-Za-z]{{1,{MAX_RESOLUTION_LENGTH}}}$")]
        | None
    ) = None
    quality: ImageQuality | None = None


class OutputImageRead(BaseModel):
    """칸 하나가 만든 결과 이미지 한 장. 파일은 GET /simulations/output-images/{output_asset_id} 로 받는다."""

    output_asset_id: UUID
    sort_order: Annotated[int, Field(ge=0)]  # 모델이 돌려준 순서(0부터)
    mime_type: str
    file_size_bytes: Annotated[int, Field(ge=0)]
