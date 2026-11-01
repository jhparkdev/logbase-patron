from app.schemas.simulation_image import (
    MAX_IMAGE_BYTES,
    MAX_IMAGE_COUNT,
    ImageLimits,
    ImageMimeType,
)


def test_limits_follow_the_screen_policy() -> None:
    # 화면(frontend/src/features/simulator/lib/limits.ts)이 먼저 정한 값이다. 바꾸면 화면과 같이 바꾼다
    assert MAX_IMAGE_COUNT == 4
    assert MAX_IMAGE_BYTES == 5 * 1024 * 1024
    assert {mime.value for mime in ImageMimeType} == {
        "image/jpeg",
        "image/png",
        "image/webp",
    }


def test_limits_response_carries_every_policy_value() -> None:
    limits = ImageLimits.current().model_dump(mode="json")

    assert limits["max_count"] == MAX_IMAGE_COUNT
    assert limits["max_bytes"] == MAX_IMAGE_BYTES
    assert sorted(limits["mime_types"]) == ["image/jpeg", "image/png", "image/webp"]
