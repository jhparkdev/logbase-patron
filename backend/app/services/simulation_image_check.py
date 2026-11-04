"""올린 이미지 검사. 파일 내용만 보는 순수 함수라 DB 와 저장소 없이 검증한다."""

from app.schemas.simulation_image import MAX_IMAGE_BYTES, ImageMimeType

_PNG_HEAD = b"\x89PNG\r\n\x1a\n"
_JPEG_HEAD = b"\xff\xd8\xff"
_RIFF_HEAD = b"RIFF"
_WEBP_TAG = b"WEBP"
_WEBP_TAG_OFFSET = 8


class EmptyImageError(ValueError):
    """빈 파일이다."""


class ImageTooLargeError(ValueError):
    """파일이 한도(MAX_IMAGE_BYTES)보다 크다."""


class UnsupportedImageTypeError(ValueError):
    """JPG·PNG·WebP 가 아니다. 이름이나 Content-Type 은 믿지 않고 내용으로 판단한다."""


def detect_image_mime(data: bytes) -> ImageMimeType | None:
    """머리 바이트로 형식을 알아낸다. 받는 형식이 아니면 None."""
    if data.startswith(_PNG_HEAD):
        return ImageMimeType.PNG
    if data.startswith(_JPEG_HEAD):
        return ImageMimeType.JPEG
    if (
        data.startswith(_RIFF_HEAD)
        and data[_WEBP_TAG_OFFSET : _WEBP_TAG_OFFSET + len(_WEBP_TAG)] == _WEBP_TAG
    ):
        return ImageMimeType.WEBP
    return None


def check_image(data: bytes) -> ImageMimeType:
    """저장해도 되는 이미지인지 검사하고 형식을 돌려준다. 크기를 먼저 본다(싼 검사부터)."""
    if not data:
        raise EmptyImageError
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageTooLargeError
    mime = detect_image_mime(data)
    if mime is None:
        raise UnsupportedImageTypeError
    return mime
