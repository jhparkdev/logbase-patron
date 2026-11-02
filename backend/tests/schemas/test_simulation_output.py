"""이미지 생성 실행의 요청 계약. 생성 종류와 이미지 옵션, 텍스트 전용 설정과의 충돌을 검증한다."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.simulation import SimulationCreateRequest
from app.schemas.simulation_output import (
    MAX_OUTPUT_IMAGE_COUNT,
    ImageConfig,
    ImageQuality,
    OutputType,
)


def body(**overrides: Any) -> dict[str, Any]:
    request: dict[str, Any] = {
        "test_type": "CUSTOM",
        "prompt_text": "빨간 원피스를 입은 모델 사진",
        "models": [
            {"model_id": 1, "execution_provider": "A"},
            {"model_id": 2, "execution_provider": "B"},
        ],
    }
    request.update(overrides)
    return request


def image_body(**overrides: Any) -> dict[str, Any]:
    return body(output_type="IMAGE", **overrides)


def test_a_request_without_output_type_is_a_text_run() -> None:
    request = SimulationCreateRequest(**body())

    assert request.output_type == OutputType.TEXT
    assert request.image_config is None


def test_an_image_run_may_omit_image_options() -> None:
    request = SimulationCreateRequest(**image_body())

    assert request.output_type == OutputType.IMAGE
    assert request.image_config is None


def test_an_image_run_keeps_all_four_image_options() -> None:
    request = SimulationCreateRequest(
        **image_body(
            image_config={
                "n": 2,
                "aspect_ratio": "16:9",
                "resolution": "2K",
                "quality": "high",
            }
        )
    )

    assert request.image_config == ImageConfig(
        n=2, aspect_ratio="16:9", resolution="2K", quality=ImageQuality.HIGH
    )


@pytest.mark.parametrize("n", [1, MAX_OUTPUT_IMAGE_COUNT])
def test_image_count_at_the_bounds_is_accepted(n: int) -> None:
    assert ImageConfig(n=n).n == n


@pytest.mark.parametrize("n", [0, MAX_OUTPUT_IMAGE_COUNT + 1, "2", 1.5])
def test_image_count_outside_the_bounds_or_not_an_integer_is_refused(n: Any) -> None:
    with pytest.raises(ValidationError):
        ImageConfig(n=n)


@pytest.mark.parametrize("ratio", ["1:1", "16:9", "21:9"])
def test_aspect_ratio_in_width_colon_height_form_is_accepted(ratio: str) -> None:
    assert ImageConfig(aspect_ratio=ratio).aspect_ratio == ratio


@pytest.mark.parametrize("ratio", ["", "16x9", "16:", ":9", "1:1;", "100:1"])
def test_aspect_ratio_in_another_form_is_refused(ratio: str) -> None:
    with pytest.raises(ValidationError):
        ImageConfig(aspect_ratio=ratio)


@pytest.mark.parametrize("resolution", ["1K", "2K", "4K", "1024x1024"])
def test_resolution_tier_or_pixel_size_is_accepted(resolution: str) -> None:
    assert ImageConfig(resolution=resolution).resolution == resolution


@pytest.mark.parametrize("resolution", ["", "2 K", "2K;drop", "x" * 17])
def test_resolution_with_other_characters_or_too_long_is_refused(
    resolution: str,
) -> None:
    with pytest.raises(ValidationError):
        ImageConfig(resolution=resolution)


def test_quality_outside_the_allowed_values_is_refused() -> None:
    with pytest.raises(ValidationError):
        ImageConfig(quality="ultra")  # type: ignore[arg-type]


def test_unknown_image_option_is_refused() -> None:
    with pytest.raises(ValidationError):
        ImageConfig.model_validate({"seed": 1})


def test_image_options_on_a_text_run_are_refused() -> None:
    with pytest.raises(ValidationError):
        SimulationCreateRequest(**body(image_config={"n": 1}))


def test_an_image_run_with_a_json_schema_is_refused() -> None:
    # 이미지 응답에는 JSON 이 없어 Schema 검증이 의미 없다
    with pytest.raises(ValidationError):
        SimulationCreateRequest(**image_body(json_schema={"type": "object"}))


@pytest.mark.parametrize(
    "config", [{"max_tokens": 100}, {"temperature": 0.5}, {"reasoning_effort": "low"}]
)
def test_an_image_run_with_text_settings_is_refused(config: dict[str, Any]) -> None:
    # 이미지 호출은 이 설정을 보내지 않는다. 받으면 기록과 실제 호출이 달라진다
    with pytest.raises(ValidationError):
        SimulationCreateRequest(**image_body(execution_config=config))


def test_an_image_run_with_text_settings_on_one_model_is_refused() -> None:
    models = [
        {
            "model_id": 1,
            "execution_provider": "A",
            "execution_config": {"max_tokens": 9},
        },
        {"model_id": 2, "execution_provider": "B"},
    ]
    with pytest.raises(ValidationError):
        SimulationCreateRequest(**image_body(models=models))
