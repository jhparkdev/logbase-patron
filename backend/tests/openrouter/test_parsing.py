from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.openrouter.errors import ErrorType
from app.openrouter.parsing import build_result_from_chat_body, loads_decimal
from app.openrouter.result import CallResult, CallStatus, CostSource, CostStatus

STARTED_AT = datetime(2026, 10, 27, 1, 0, 0, tzinfo=UTC)
FINISHED_AT = datetime(2026, 10, 27, 1, 0, 1, 500000, tzinfo=UTC)

# 검증 보고서 API-02의 실제 응답 모양을 줄인 것
SUCCESS_BODY_TEXT = """
{
  "id": "gen-abc123",
  "model": "mistralai/mistral-nemo",
  "provider": "DekaLLM",
  "choices": [
    {"message": {"role": "assistant", "content": "2"}, "finish_reason": "stop"}
  ],
  "usage": {
    "prompt_tokens": 16,
    "completion_tokens": 2,
    "total_tokens": 18,
    "cost": 3.48e-07,
    "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
    "completion_tokens_details": {"reasoning_tokens": 0}
  }
}
"""


def make_body() -> dict[str, Any]:
    return loads_decimal(SUCCESS_BODY_TEXT)


def build(body: dict[str, Any]) -> CallResult:
    return build_result_from_chat_body(
        body,
        requested_model="mistralai/mistral-nemo",
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
        http_status=200,
    )


# ---------------------------------------------------------------
# JSON을 읽을 때 소수는 float이 아니라 Decimal로 읽는다
# ---------------------------------------------------------------
def test_소수는_Decimal로_읽는다() -> None:
    body = loads_decimal('{"cost": 3.48e-07, "tokens": 16}')
    assert isinstance(body["cost"], Decimal)
    assert body["cost"] == Decimal("3.48e-07")


def test_정수는_그대로_정수다() -> None:
    body = loads_decimal('{"tokens": 16}')
    assert body["tokens"] == 16
    assert isinstance(body["tokens"], int)


# ---------------------------------------------------------------
# 정상 응답: 비용이 있으면 확정(CONFIRMED)
# ---------------------------------------------------------------
def test_비용이_있는_정상_응답은_SUCCESS와_CONFIRMED다() -> None:
    result = build(make_body())

    assert result.status == CallStatus.SUCCESS
    assert result.error_type is None
    assert result.cost_status == CostStatus.CONFIRMED
    assert result.cost_usd == Decimal("3.48e-07")
    assert result.cost_source == CostSource.API_RESPONSE


def test_정상_응답에서_본문_모델_업체_ID를_꺼낸다() -> None:
    result = build(make_body())

    assert result.content == "2"
    assert result.requested_model == "mistralai/mistral-nemo"
    assert result.actual_model == "mistralai/mistral-nemo"
    assert result.provider == "DekaLLM"
    assert result.generation_id == "gen-abc123"
    assert result.finish_reason == "stop"
    assert result.http_status == 200


def test_정상_응답에서_토큰_수를_꺼낸다() -> None:
    result = build(make_body())

    assert result.prompt_tokens == 16
    assert result.completion_tokens == 2
    assert result.total_tokens == 18


def test_응답_시간을_밀리초로_계산한다() -> None:
    result = build(make_body())

    assert result.started_at == STARTED_AT
    assert result.finished_at == FINISHED_AT
    assert result.latency_ms == 1500


def test_비용이_0이면_실제_0원이라서_CONFIRMED다() -> None:
    body = make_body()
    body["usage"]["cost"] = 0

    result = build(body)

    assert result.cost_status == CostStatus.CONFIRMED
    assert result.cost_usd == Decimal("0")


def test_float으로_온_비용도_Decimal로_바꿔_받는다() -> None:
    body = make_body()
    body["usage"]["cost"] = 3.48e-07

    result = build(body)

    assert result.cost_status == CostStatus.CONFIRMED
    assert result.cost_usd == Decimal("3.48e-07")


# ---------------------------------------------------------------
# 정상 응답인데 비용이 없으면 미확인(UNKNOWN). 0으로 바꾸지 않는다
# ---------------------------------------------------------------
def test_비용이_없는_정상_응답은_SUCCESS와_UNKNOWN이다() -> None:
    body = make_body()
    del body["usage"]["cost"]

    result = build(body)

    assert result.status == CallStatus.SUCCESS
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None
    assert result.cost_source is None


@pytest.mark.parametrize("bad_cost", [None, "abc", "0.1", True, Decimal("-1"), -1])
def test_비용이_숫자가_아니거나_음수면_UNKNOWN이다(bad_cost: object) -> None:
    body = make_body()
    body["usage"]["cost"] = bad_cost

    result = build(body)

    assert result.status == CallStatus.SUCCESS
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None


# ---------------------------------------------------------------
# 캐시·reasoning 토큰은 이미 입력·출력 토큰에 포함된 값이다
# (검증 보고서 API-04: 합쳐서 계산하면 중복이다)
# ---------------------------------------------------------------
def test_캐시와_reasoning_토큰은_기존_토큰_수에_더하지_않는다() -> None:
    body = make_body()
    body["usage"].update(
        {
            "prompt_tokens": 3622,
            "completion_tokens": 100,
            "total_tokens": 3722,
            "cost": Decimal("2.21508e-05"),
            "prompt_tokens_details": {"cached_tokens": 3584, "cache_write_tokens": 0},
            "completion_tokens_details": {"reasoning_tokens": 82},
        }
    )

    result = build(body)

    assert result.prompt_tokens == 3622
    assert result.completion_tokens == 100
    assert result.total_tokens == 3722
    assert result.cached_tokens == 3584
    assert result.cache_write_tokens == 0
    assert result.reasoning_tokens == 82


def test_세부_토큰_정보가_없으면_None이다() -> None:
    body = make_body()
    del body["usage"]["prompt_tokens_details"]
    del body["usage"]["completion_tokens_details"]

    result = build(body)

    assert result.status == CallStatus.SUCCESS
    assert result.cached_tokens is None
    assert result.cache_write_tokens is None
    assert result.reasoning_tokens is None


# ---------------------------------------------------------------
# 답이 중간에 잘려도(length) 호출은 성공이다
# ---------------------------------------------------------------
def test_답이_잘려도_SUCCESS이고_truncated로_알린다() -> None:
    body = make_body()
    body["choices"][0]["finish_reason"] = "length"

    result = build(body)

    assert result.status == CallStatus.SUCCESS
    assert result.finish_reason == "length"
    assert result.truncated is True


# ---------------------------------------------------------------
# 200인데 내용이 비정상이면 실패(INVALID_RESPONSE). 빈 응답을 성공으로 보지 않는다
# ---------------------------------------------------------------
def set_empty_content(body: dict[str, Any]) -> None:
    body["choices"][0]["message"]["content"] = ""


def set_blank_content(body: dict[str, Any]) -> None:
    body["choices"][0]["message"]["content"] = "   "


def set_null_content(body: dict[str, Any]) -> None:
    body["choices"][0]["message"]["content"] = None


def remove_choices(body: dict[str, Any]) -> None:
    del body["choices"]


def set_empty_choices(body: dict[str, Any]) -> None:
    body["choices"] = []


def remove_model(body: dict[str, Any]) -> None:
    del body["model"]


def remove_usage(body: dict[str, Any]) -> None:
    del body["usage"]


def remove_prompt_tokens(body: dict[str, Any]) -> None:
    del body["usage"]["prompt_tokens"]


def remove_completion_tokens(body: dict[str, Any]) -> None:
    del body["usage"]["completion_tokens"]


def set_text_prompt_tokens(body: dict[str, Any]) -> None:
    body["usage"]["prompt_tokens"] = "16"


@pytest.mark.parametrize(
    "break_body",
    [
        set_empty_content,
        set_blank_content,
        set_null_content,
        remove_choices,
        set_empty_choices,
        remove_model,
        remove_usage,
        remove_prompt_tokens,
        remove_completion_tokens,
        set_text_prompt_tokens,
    ],
)
def test_내용이_비정상인_200_응답은_INVALID_RESPONSE다(
    break_body: Callable[[dict[str, Any]], None],
) -> None:
    body = make_body()
    break_body(body)

    result = build(body)

    assert result.status == CallStatus.FAILED
    assert result.error_type == ErrorType.INVALID_RESPONSE
    assert result.error_message
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None


def test_비정상_응답이어도_대조에_쓸_generation_id와_원문은_남긴다() -> None:
    body = make_body()
    set_empty_content(body)

    result = build(body)

    assert result.generation_id == "gen-abc123"
    assert result.raw_response == body
    assert result.http_status == 200
