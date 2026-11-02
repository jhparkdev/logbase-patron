"""생성 종류와 이미지 옵션을 execution_config 에 담고 다시 읽는다. DB 없이 쓰는 순수 함수다.

simulation_runs 에 생성 종류 칸이 없어 execution_config(JSON)에 함께 남긴다. 텍스트 실행은
예전 기록과 같게 output_type 을 담지 않는다. 그래서 output_type 이 없으면 텍스트 실행이다.
"""

from collections.abc import Mapping
from typing import Any

from app.schemas.simulation_output import ImageConfig, OutputType

OUTPUT_TYPE_KEY = "output_type"


def build_image_execution_config(image_config: ImageConfig | None) -> dict[str, Any]:
    """이미지 실행의 execution_config. 실제로 보내는 옵션만 담는다."""
    options = (
        image_config.model_dump(mode="json", exclude_none=True) if image_config else {}
    )
    return {OUTPUT_TYPE_KEY: OutputType.IMAGE.value, **options}


def stored_output_type(config: Mapping[str, Any]) -> OutputType:
    """기록된 설정의 생성 종류. 모르는 값이면 ValueError 다."""
    return OutputType(config.get(OUTPUT_TYPE_KEY, OutputType.TEXT.value))


def image_call_options(config: Mapping[str, Any]) -> dict[str, Any]:
    """generate_image 에 넘길 옵션(n, aspect_ratio, resolution, quality)."""
    return {key: value for key, value in config.items() if key != OUTPUT_TYPE_KEY}


def split_stored_config(
    config: Mapping[str, Any],
) -> tuple[OutputType, dict[str, Any], ImageConfig | None]:
    """기록된 설정을 요청 모양(생성 종류, 텍스트 실행 설정, 이미지 옵션)으로 나눈다. 재실행 초안이 쓴다."""
    output_type = stored_output_type(config)
    if output_type == OutputType.TEXT:
        return output_type, dict(config), None
    options = image_call_options(config)
    return output_type, {}, ImageConfig.model_validate(options) if options else None
