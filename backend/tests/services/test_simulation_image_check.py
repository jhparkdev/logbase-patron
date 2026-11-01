import pytest

from app.schemas.simulation_image import MAX_IMAGE_BYTES, ImageMimeType
from app.services.simulation_image_check import (
    EmptyImageError,
    ImageTooLargeError,
    UnsupportedImageTypeError,
    check_image,
    detect_image_mime,
)
from tests.image_samples import GIF_HEAD, jpeg, png, webp


@pytest.mark.parametrize(
    "data, expected",
    [
        (png(), ImageMimeType.PNG),
        (jpeg(), ImageMimeType.JPEG),
        (webp(), ImageMimeType.WEBP),
    ],
)
def test_the_type_comes_from_the_file_content(
    data: bytes, expected: ImageMimeType
) -> None:
    assert detect_image_mime(data) == expected


@pytest.mark.parametrize(
    "data",
    [
        GIF_HEAD + b"\x00" * 32,  # OpenRouter 는 받지만 화면 정책(JPG·PNG·WebP)에 없다
        b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        b"%PDF-1.7 not an image",
        b"RIFF\x00\x00\x00\x00WAVE",  # RIFF 이지만 WebP 가 아니다
        b"\x89PNG",  # 머리가 잘린 PNG
    ],
)
def test_other_content_is_not_an_accepted_image(data: bytes) -> None:
    assert detect_image_mime(data) is None


def test_a_checked_image_returns_its_type() -> None:
    assert check_image(png()) == ImageMimeType.PNG


def test_an_empty_file_is_rejected() -> None:
    with pytest.raises(EmptyImageError):
        check_image(b"")


# 크기 경계: 바로 전, 정확히 그 값, 바로 후
def test_a_file_just_under_the_limit_is_accepted() -> None:
    assert check_image(png(MAX_IMAGE_BYTES - 1)) == ImageMimeType.PNG


def test_a_file_exactly_at_the_limit_is_accepted() -> None:
    assert check_image(png(MAX_IMAGE_BYTES)) == ImageMimeType.PNG


def test_a_file_just_over_the_limit_is_rejected() -> None:
    with pytest.raises(ImageTooLargeError):
        check_image(png(MAX_IMAGE_BYTES + 1))


def test_an_unsupported_type_is_rejected_even_when_named_like_an_image() -> None:
    # 이름·Content-Type 이 아니라 내용으로 판단한다. 이미지로 위장한 파일이 저장소에 들어가지 않게 한다
    with pytest.raises(UnsupportedImageTypeError):
        check_image(b"MZ\x90\x00 not really a png")


def test_size_is_checked_before_the_type() -> None:
    with pytest.raises(ImageTooLargeError):
        check_image(b"x" * (MAX_IMAGE_BYTES + 1))
