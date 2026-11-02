import base64
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.openrouter.errors import USER_MESSAGES, ErrorType
from app.openrouter.image_parsing import (
    build_image_cancelled_result,
    build_image_failure_result,
    build_image_result,
)
from app.openrouter.result import CallStatus, CostSource, CostStatus

MODEL_ID = "bytedance-seed/seedream-4.5"
STARTED_AT = datetime(2026, 11, 2, 1, 0, 0, tzinfo=UTC)
FINISHED_AT = datetime(2026, 11, 2, 1, 0, 12, 250000, tzinfo=UTC)
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x01" * 64
WEBP_BYTES = b"RIFF\x00\x00\x00\x00WEBP" + b"\x02" * 64


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def success_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "created": 1793581200,
        "data": [{"b64_json": b64(PNG_BYTES), "media_type": "image/png"}],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 4096,
            "total_tokens": 4108,
            "cost": Decimal("0.04"),
            "completion_tokens_details": {"image_tokens": 4096},
        },
    }
    body.update(overrides)
    return body


def parse(status_code: int, body: Any, **overrides: Any):
    arguments: dict[str, Any] = {
        "status_code": status_code,
        "body": body,
        "requested_model": MODEL_ID,
        "started_at": STARTED_AT,
        "finished_at": FINISHED_AT,
    }
    arguments.update(overrides)
    return build_image_result(**arguments)


# ---------------------------------------------------------------
# 정상 응답
# ---------------------------------------------------------------
def test_정상_응답은_이미지를_풀어_SUCCESS와_CONFIRMED로_돌려준다() -> None:
    result = parse(200, success_body())

    assert result.status == CallStatus.SUCCESS
    assert result.error_type is None
    assert result.http_status == 200
    assert result.requested_model == MODEL_ID
    assert [image.data for image in result.images] == [PNG_BYTES]
    assert [image.media_type for image in result.images] == ["image/png"]
    assert result.cost_status == CostStatus.CONFIRMED
    assert result.cost_usd == Decimal("0.04")
    assert result.cost_source == CostSource.API_RESPONSE
    assert result.latency_ms == 12250


def test_토큰_수를_읽는다() -> None:
    result = parse(200, success_body())

    assert result.prompt_tokens == 12
    assert result.completion_tokens == 4096
    assert result.total_tokens == 4108
    assert result.image_tokens == 4096


def test_여러_장이면_받은_순서대로_돌려준다() -> None:
    data = [
        {"b64_json": b64(PNG_BYTES), "media_type": "image/png"},
        {"b64_json": b64(WEBP_BYTES), "media_type": "image/webp"},
    ]

    result = parse(200, success_body(data=data))

    assert [image.data for image in result.images] == [PNG_BYTES, WEBP_BYTES]


def test_형식을_알_수_없으면_media_type은_None이다() -> None:
    result = parse(200, success_body(data=[{"b64_json": b64(PNG_BYTES)}]))

    assert result.status == CallStatus.SUCCESS
    assert result.images[0].media_type is None


def test_usage가_없으면_성공이지만_비용은_미확인이다() -> None:
    body = success_body()
    del body["usage"]

    result = parse(200, body)

    assert result.status == CallStatus.SUCCESS
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None
    assert result.prompt_tokens is None


def test_비용이_null이면_0이_아니라_미확인이다() -> None:
    body = success_body()
    body["usage"]["cost"] = None

    result = parse(200, body)

    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None


def test_비용이_음수면_믿지_않고_미확인이다() -> None:
    body = success_body()
    body["usage"]["cost"] = Decimal("-0.01")

    result = parse(200, body)

    assert result.cost_status == CostStatus.UNKNOWN


def test_비용이_0이면_무료로_확정한다() -> None:
    body = success_body()
    body["usage"]["cost"] = 0

    result = parse(200, body)

    assert result.cost_status == CostStatus.CONFIRMED
    assert result.cost_usd == Decimal(0)


def test_원본_응답에는_이미지_내용을_남기지_않는다() -> None:
    result = parse(200, success_body())

    assert result.raw_response is not None
    assert result.raw_response["data"] == [{"media_type": "image/png"}]
    assert result.raw_response["usage"]["total_tokens"] == 4108
    assert b64(PNG_BYTES) not in str(result.raw_response)


def test_헤더의_호출_ID를_담는다() -> None:
    result = parse(200, success_body(), generation_id="gen-img123")

    assert result.generation_id == "gen-img123"


# ---------------------------------------------------------------
# 200인데 믿을 수 없는 응답
# ---------------------------------------------------------------
def test_이미지가_하나도_없으면_INVALID_RESPONSE다() -> None:
    result = parse(200, success_body(data=[]))

    assert result.status == CallStatus.FAILED
    assert result.error_type == ErrorType.INVALID_RESPONSE
    assert result.error_message == USER_MESSAGES[ErrorType.INVALID_RESPONSE]
    assert result.images == ()


def test_data가_목록이_아니면_INVALID_RESPONSE다() -> None:
    result = parse(200, success_body(data={"b64_json": b64(PNG_BYTES)}))

    assert result.error_type == ErrorType.INVALID_RESPONSE


def test_base64가_아니면_INVALID_RESPONSE다() -> None:
    result = parse(200, success_body(data=[{"b64_json": "이건-base64가-아님!"}]))

    assert result.error_type == ErrorType.INVALID_RESPONSE
    assert result.images == ()


def test_이미지_내용이_비어_있으면_INVALID_RESPONSE다() -> None:
    result = parse(200, success_body(data=[{"b64_json": ""}]))

    assert result.error_type == ErrorType.INVALID_RESPONSE


def test_한_장이라도_깨져_있으면_전체를_INVALID_RESPONSE로_본다() -> None:
    data = [{"b64_json": b64(PNG_BYTES)}, {"media_type": "image/png"}]

    result = parse(200, success_body(data=data))

    assert result.error_type == ErrorType.INVALID_RESPONSE
    assert result.images == ()


def test_응답이_깨져도_받은_비용은_남긴다() -> None:
    # 이미지 응답에는 호출 ID가 없어 나중에 대조할 수 없다. 받은 비용을 버리면 영영 모른다.
    result = parse(200, success_body(data=[]))

    assert result.status == CallStatus.FAILED
    assert result.cost_status == CostStatus.CONFIRMED
    assert result.cost_usd == Decimal("0.04")


def test_200인데_JSON_객체가_아니면_INVALID_RESPONSE다() -> None:
    result = parse(200, None)

    assert result.status == CallStatus.FAILED
    assert result.error_type == ErrorType.INVALID_RESPONSE
    assert result.cost_status == CostStatus.UNKNOWN


# ---------------------------------------------------------------
# HTTP 오류
# ---------------------------------------------------------------
def test_502는_업체_오류이고_비용은_미확인이다() -> None:
    body = {"error": {"code": 502, "message": "upstream failed"}}

    result = parse(502, body)

    assert result.status == CallStatus.FAILED
    assert result.error_type == ErrorType.PROVIDER_ERROR
    assert result.http_status == 502
    assert result.raw_response == body
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None


def test_404이면_라우팅_실패_단계를_함께_돌려준다() -> None:
    body = {
        "error": {
            "code": 404,
            "message": "No endpoints found",
            "metadata": {"failed_routing_step": "Filter by Parameters"},
        }
    }

    result = parse(404, body)

    assert result.error_type == ErrorType.UNSUPPORTED_INPUT
    assert result.failed_routing_step == "Filter by Parameters"


def test_오류_본문이_JSON이_아니어도_실패_결과로_돌려준다() -> None:
    result = parse(500, None)

    assert result.status == CallStatus.FAILED
    assert result.error_type == ErrorType.PROVIDER_ERROR
    assert result.raw_response is None


# ---------------------------------------------------------------
# 보내지 못한 호출
# ---------------------------------------------------------------
def test_실패_결과는_비용_미확인이고_사용자_문구를_담는다() -> None:
    result = build_image_failure_result(
        status=CallStatus.TIMEOUT,
        error_type=ErrorType.TIMEOUT_ERROR,
        requested_model=MODEL_ID,
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
    )

    assert result.status == CallStatus.TIMEOUT
    assert result.error_message == USER_MESSAGES[ErrorType.TIMEOUT_ERROR]
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.latency_ms == 12250


def test_취소_결과는_오류가_아니고_비용은_0이_아니라_미확인이다() -> None:
    result = build_image_cancelled_result(
        requested_model=MODEL_ID, started_at=STARTED_AT, finished_at=FINISHED_AT
    )

    assert result.status == CallStatus.CANCELLED
    assert result.error_type is None
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None
