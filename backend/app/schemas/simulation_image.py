"""시뮬레이터 이미지 입력의 계약. 한도는 여기 한 곳에서 정하고 OpenAPI 로 화면에 전달한다."""

from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel

# 화면이 먼저 정한 값(frontend/src/features/simulator/lib/limits.ts)이다. 바꾸면 화면도 이 값을 받아 쓴다
MAX_IMAGE_COUNT = 4
MAX_IMAGE_BYTES = 5 * 1024 * 1024


class ImageMimeType(StrEnum):
    """받는 이미지 형식. 파일 내용의 머리 바이트로 판단한다."""

    JPEG = "image/jpeg"
    PNG = "image/png"
    WEBP = "image/webp"


class ImageAssetRead(BaseModel):
    """올린 이미지 한 장. 비교 실행 요청에는 asset_id 만 보낸다."""

    asset_id: UUID
    mime_type: str
    file_size_bytes: int
    original_filename: str | None


class ImageLimits(BaseModel):
    """이미지 입력 한도. 화면은 하드코딩하지 않고 이 응답을 쓴다."""

    max_count: int
    max_bytes: int
    mime_types: list[ImageMimeType]

    @classmethod
    def current(cls) -> Self:
        return cls(
            max_count=MAX_IMAGE_COUNT,
            max_bytes=MAX_IMAGE_BYTES,
            mime_types=list(ImageMimeType),
        )
