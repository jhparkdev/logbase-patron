"""생성 종류와 이미지 옵션을 execution_config 에 담고 다시 읽는 순수 함수."""

import pytest

from app.schemas.simulation_output import ImageConfig, ImageQuality, OutputType
from app.services.simulation_output_config import (
    build_image_execution_config,
    image_call_options,
    split_stored_config,
    stored_output_type,
)

FULL = ImageConfig(n=2, aspect_ratio="16:9", resolution="2K", quality=ImageQuality.LOW)


def test_an_image_config_is_stored_with_the_output_type_and_only_the_given_options() -> (
    None
):
    assert build_image_execution_config(ImageConfig(n=2)) == {
        "output_type": "IMAGE",
        "n": 2,
    }


def test_an_image_run_without_options_stores_only_the_output_type() -> None:
    assert build_image_execution_config(None) == {"output_type": "IMAGE"}


def test_a_config_without_output_type_is_a_text_run() -> None:
    # 이미지 생성이 생기기 전의 기록은 모두 텍스트 실행이다
    assert stored_output_type({"max_tokens": 1024}) == OutputType.TEXT


def test_a_stored_image_config_is_an_image_run() -> None:
    assert stored_output_type(build_image_execution_config(FULL)) == OutputType.IMAGE


def test_call_options_are_the_stored_image_options_without_the_output_type() -> None:
    assert image_call_options(build_image_execution_config(FULL)) == {
        "n": 2,
        "aspect_ratio": "16:9",
        "resolution": "2K",
        "quality": "low",
    }


def test_splitting_an_image_config_gives_back_the_options_and_no_text_settings() -> (
    None
):
    output_type, text_config, image_config = split_stored_config(
        build_image_execution_config(FULL)
    )

    assert output_type == OutputType.IMAGE
    assert text_config == {}
    assert image_config == FULL


def test_splitting_an_image_config_without_options_gives_no_image_config() -> None:
    assert split_stored_config({"output_type": "IMAGE"}) == (
        OutputType.IMAGE,
        {},
        None,
    )


def test_splitting_a_text_config_keeps_it_as_is() -> None:
    config = {"max_tokens": 1024, "temperature": 0.7}

    assert split_stored_config(config) == (OutputType.TEXT, config, None)


@pytest.mark.parametrize("value", ["VIDEO", 1])
def test_an_unknown_output_type_is_not_read_as_text(value: object) -> None:
    # 모르는 값을 텍스트로 읽으면 다른 종류의 실행을 텍스트로 다시 돌리게 된다
    with pytest.raises(ValueError):
        stored_output_type({"output_type": value})
