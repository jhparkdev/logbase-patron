"""이미지 테스트들이 함께 쓰는 표본. 실제로 열리는 그림이 아니라 형식을 구분하는 머리 바이트만 맞춘다."""

PNG_HEAD = b"\x89PNG\r\n\x1a\n"
JPEG_HEAD = b"\xff\xd8\xff\xe0"
WEBP_HEAD = b"RIFF\x00\x00\x00\x00WEBP"
GIF_HEAD = b"GIF89a"


def png(size: int = 64) -> bytes:
    return PNG_HEAD + b"\x00" * (size - len(PNG_HEAD))


def jpeg(size: int = 64) -> bytes:
    return JPEG_HEAD + b"\x00" * (size - len(JPEG_HEAD))


def webp(size: int = 64) -> bytes:
    return WEBP_HEAD + b"\x00" * (size - len(WEBP_HEAD))
