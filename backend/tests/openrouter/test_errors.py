import pytest

from app.openrouter.errors import (
    ErrorType,
    classify_http_error,
    get_failed_routing_step,
)


def routing_error_body(step: str) -> dict:
    """업체 라우팅이 실패했을 때 OpenRouter가 보내는 404 본문 모양 (검증 보고서 API-08)."""
    return {
        "error": {
            "message": "No endpoints found",
            "code": 404,
            "metadata": {"failed_routing_step": step},
        }
    }


# ---------------------------------------------------------------
# 오류 유형 8종은 회사 문서가 정한 값이라 늘리거나 줄이면 안 된다
# ---------------------------------------------------------------
def test_오류_유형은_회사_문서의_8종이다() -> None:
    expected = {
        "AUTH_ERROR",
        "RATE_LIMIT",
        "TIMEOUT_ERROR",
        "PROVIDER_ERROR",
        "NETWORK_ERROR",
        "INVALID_RESPONSE",
        "UNSUPPORTED_INPUT",
        "UNKNOWN_ERROR",
    }
    assert {error_type.value for error_type in ErrorType} == expected


# ---------------------------------------------------------------
# 상태 코드로 오류 유형을 정한다
# ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, ErrorType.AUTH_ERROR),
        (429, ErrorType.RATE_LIMIT),
        (500, ErrorType.PROVIDER_ERROR),
        (502, ErrorType.PROVIDER_ERROR),
        (503, ErrorType.PROVIDER_ERROR),
    ],
)
def test_상태_코드로_오류_유형을_정한다(status_code: int, expected: ErrorType) -> None:
    assert classify_http_error(status_code, None) == expected


# 5xx 경계: 바로 전(499), 시작(500), 끝(599), 바로 후(600)
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (499, ErrorType.UNKNOWN_ERROR),
        (500, ErrorType.PROVIDER_ERROR),
        (599, ErrorType.PROVIDER_ERROR),
        (600, ErrorType.UNKNOWN_ERROR),
    ],
)
def test_5xx_경계에서_서버_오류만_PROVIDER_ERROR다(
    status_code: int, expected: ErrorType
) -> None:
    assert classify_http_error(status_code, None) == expected


# ---------------------------------------------------------------
# 404는 본문의 라우팅 실패 단계를 보고 정한다 (검증 보고서의 실제 응답)
# ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("step", "expected"),
    [
        ("Filter by Fallback", ErrorType.PROVIDER_ERROR),
        ("Filter by Image Support", ErrorType.UNSUPPORTED_INPUT),
        ("Filter by Parameters", ErrorType.UNSUPPORTED_INPUT),
    ],
)
def test_404는_라우팅_실패_단계로_오류_유형을_정한다(
    step: str, expected: ErrorType
) -> None:
    body = routing_error_body(step)
    assert classify_http_error(404, body) == expected


def test_모르는_라우팅_단계의_404는_UNKNOWN_ERROR다() -> None:
    body = routing_error_body("Filter by Something New")
    assert classify_http_error(404, body) == ErrorType.UNKNOWN_ERROR


def test_본문이_없는_404는_UNKNOWN_ERROR다() -> None:
    assert classify_http_error(404, None) == ErrorType.UNKNOWN_ERROR


# ---------------------------------------------------------------
# 아직 정해지지 않은 상태 코드는 UNKNOWN_ERROR로 둔다
# 400은 회사 확인 대기(U-03), 402·403은 실제 응답을 확인하기 전이다
# ---------------------------------------------------------------
@pytest.mark.parametrize("status_code", [400, 402, 403, 418])
def test_정해지지_않은_상태_코드는_UNKNOWN_ERROR다(status_code: int) -> None:
    assert classify_http_error(status_code, None) == ErrorType.UNKNOWN_ERROR


# ---------------------------------------------------------------
# 본문에서 라우팅 실패 단계를 꺼낸다
# ---------------------------------------------------------------
def test_본문에서_라우팅_실패_단계를_꺼낸다() -> None:
    body = routing_error_body("Filter by Fallback")
    assert get_failed_routing_step(body) == "Filter by Fallback"


@pytest.mark.parametrize(
    "body",
    [
        None,
        "문자열 본문",
        {},
        {"error": "문자열"},
        {"error": {}},
        {"error": {"metadata": "문자열"}},
        {"error": {"metadata": {}}},
        {"error": {"metadata": {"failed_routing_step": 123}}},
    ],
)
def test_모양이_다른_본문에서는_None을_돌려준다(body: object) -> None:
    assert get_failed_routing_step(body) is None  # type: ignore[arg-type]
