from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.openrouter.lookup_parsing import (
    parse_generation,
    parse_key_usage,
    parse_keys,
    parse_models,
)
from app.openrouter.parsing import loads_decimal

# 검증 보고서 API-01의 실제 응답 모양을 줄인 것
MODELS_BODY_TEXT = """
{
  "data": [
    {
      "id": "moonshotai/kimi-k3.1-pro",
      "pricing": {
        "prompt": "0.000002",
        "completion": "0.00001",
        "input_cache_read": "0.0000002"
      },
      "architecture": {"input_modalities": ["text", "image"]},
      "supported_parameters": ["response_format", "reasoning"],
      "context_length": 262144,
      "expiration_date": "2026-12-31"
    },
    {
      "id": "mistralai/mistral-nemo",
      "pricing": {"prompt": "0.000000029", "completion": "0.00000003"},
      "architecture": {"input_modalities": ["text"]},
      "supported_parameters": [],
      "context_length": 128000
    }
  ],
  "total_count": 2
}
"""

# 검증 보고서 API-03의 실제 응답 모양을 줄인 것
GENERATION_BODY_TEXT = """
{
  "data": {
    "id": "gen-abc",
    "total_cost": 3.48e-07,
    "native_tokens_prompt": 16,
    "native_tokens_completion": 2,
    "tokens_prompt": 11,
    "tokens_completion": 1,
    "provider_name": "DekaLLM",
    "cancelled": false,
    "provider_responses": [{"status": 200, "provider_name": "DekaLLM"}]
  }
}
"""

# 검증 보고서 API-05-a의 실제 응답 모양을 줄인 것
KEY_USAGE_BODY_TEXT = """
{
  "data": {
    "label": "sk-or-v1-0e6...1c96",
    "is_management_key": false,
    "limit": 50,
    "limit_remaining": 49.999865881,
    "usage": 0.000134119,
    "usage_daily": 0.000134119,
    "usage_weekly": 0.000134119,
    "usage_monthly": 0.000134119
  }
}
"""

# 검증 보고서 API-05-b의 실제 응답 모양을 줄인 것
KEYS_BODY_TEXT = """
{
  "data": [
    {
      "hash": "hash-of-key-1",
      "label": "sk-or-v1-0e6...1c96",
      "name": "PoC key",
      "disabled": false,
      "limit": 50,
      "usage": 0.00010486,
      "created_at": "2026-10-23T07:34:55.562Z",
      "last_used_at": "2026-10-24T04:21:46.568012Z",
      "workspace_id": "ws-1"
    }
  ]
}
"""


# ---------------------------------------------------------------
# 모델 목록
# ---------------------------------------------------------------
def test_모델_목록에서_ID_가격_입력_형식을_꺼낸다() -> None:
    models = parse_models(loads_decimal(MODELS_BODY_TEXT))

    assert models is not None
    assert len(models) == 2
    kimi = models[0]
    assert kimi.model_id == "moonshotai/kimi-k3.1-pro"
    assert kimi.pricing == {
        "prompt": Decimal("0.000002"),
        "completion": Decimal("0.00001"),
        "input_cache_read": Decimal("0.0000002"),
    }
    assert kimi.input_modalities == ["text", "image"]
    assert kimi.supported_parameters == ["response_format", "reasoning"]
    assert kimi.context_length == 262144
    assert kimi.expiration_date == date(2026, 12, 31)


def test_예고일이_없는_모델은_expiration_date가_None이다() -> None:
    models = parse_models(loads_decimal(MODELS_BODY_TEXT))

    assert models is not None
    assert models[1].model_id == "mistralai/mistral-nemo"
    assert models[1].expiration_date is None


def test_가격_단위는_문자열도_정확한_Decimal로_읽는다() -> None:
    models = parse_models(loads_decimal(MODELS_BODY_TEXT))

    assert models is not None
    assert models[1].pricing["prompt"] == Decimal("0.000000029")


def test_ID가_없거나_모양이_다른_항목은_건너뛴다() -> None:
    body = {"data": [{"pricing": {}}, "문자열", 5, {"id": ""}, {"id": "a/b"}]}

    models = parse_models(body)

    assert models is not None
    assert [model.model_id for model in models] == ["a/b"]


def test_가격이_이상한_항목은_빼고_나머지만_남긴다() -> None:
    pricing = {
        "prompt": "abc",
        "completion": "-1",
        "image": "NaN",
        "request": "0",
        "audio": 5,
        "web_search": True,
    }

    models = parse_models({"data": [{"id": "a/b", "pricing": pricing}]})

    assert models is not None
    assert models[0].pricing == {"request": Decimal(0), "audio": Decimal(5)}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-12-31", date(2026, 12, 31)),
        ("2026-12-31T00:00:00Z", date(2026, 12, 31)),
        (None, None),
        ("아무 말", None),
        (20261231, None),
    ],
)
def test_예고일을_날짜로_읽고_못_읽으면_None이다(
    raw: object, expected: date | None
) -> None:
    models = parse_models({"data": [{"id": "a/b", "expiration_date": raw}]})

    assert models is not None
    assert models[0].expiration_date == expected


@pytest.mark.parametrize("body", [{}, {"data": "문자열"}, {"data": {"id": "a/b"}}])
def test_모델_목록의_data가_목록이_아니면_None이다(body: dict[str, Any]) -> None:
    assert parse_models(body) is None


# ---------------------------------------------------------------
# 호출 하나의 비용 조회 (대조용)
# ---------------------------------------------------------------
def test_호출_조회에서_비용_토큰_업체를_꺼낸다() -> None:
    info = parse_generation(loads_decimal(GENERATION_BODY_TEXT))

    assert info is not None
    assert info.found is True
    assert info.total_cost == Decimal("3.48e-07")
    assert info.provider == "DekaLLM"
    assert info.cancelled is False
    assert info.provider_statuses == [200]


def test_토큰은_비용과_맞는_native_값을_쓴다() -> None:
    info = parse_generation(loads_decimal(GENERATION_BODY_TEXT))

    assert info is not None
    # tokens_prompt(11)는 비용과 맞지 않는다 (검증 보고서 API-03)
    assert info.native_tokens_prompt == 16
    assert info.native_tokens_completion == 2


def test_취소된_호출은_cancelled와_499로_알_수_있다() -> None:
    body = loads_decimal(GENERATION_BODY_TEXT)
    body["data"]["cancelled"] = True
    body["data"]["provider_responses"] = [{"status": 499}]

    info = parse_generation(body)

    assert info is not None
    assert info.cancelled is True
    assert info.provider_statuses == [499]


def test_업체_응답_상태가_정수가_아니면_무시한다() -> None:
    body = {"data": {"provider_responses": [{"status": "200"}, 5, {"status": True}]}}

    info = parse_generation(body)

    assert info is not None
    assert info.provider_statuses == []


@pytest.mark.parametrize("body", [{}, {"data": "문자열"}, {"data": [1]}])
def test_호출_조회의_data가_객체가_아니면_None이다(body: dict[str, Any]) -> None:
    assert parse_generation(body) is None


# ---------------------------------------------------------------
# 현재 Key 사용량
# ---------------------------------------------------------------
def test_Key_사용량을_Decimal로_꺼낸다() -> None:
    usage = parse_key_usage(loads_decimal(KEY_USAGE_BODY_TEXT))

    assert usage is not None
    assert usage.usage == Decimal("0.000134119")
    assert usage.usage_daily == Decimal("0.000134119")
    assert usage.usage_weekly == Decimal("0.000134119")
    assert usage.usage_monthly == Decimal("0.000134119")
    assert usage.limit == Decimal(50)
    assert usage.limit_remaining == Decimal("49.999865881")


def test_한도가_없으면_limit이_None이다() -> None:
    body = {"data": {"usage": 1, "limit": None, "limit_remaining": None}}

    usage = parse_key_usage(body)

    assert usage is not None
    assert usage.limit is None
    assert usage.limit_remaining is None


def test_Key_사용량_결과에는_label이_없다() -> None:
    usage = parse_key_usage(loads_decimal(KEY_USAGE_BODY_TEXT))

    assert usage is not None
    assert not hasattr(usage, "label")


@pytest.mark.parametrize("body", [{}, {"data": "문자열"}])
def test_Key_사용량의_data가_객체가_아니면_None이다(body: dict[str, Any]) -> None:
    assert parse_key_usage(body) is None


# ---------------------------------------------------------------
# Key 목록 (Management Key)
# ---------------------------------------------------------------
def test_Key_목록에서_이름_사용량_workspace_시각을_꺼낸다() -> None:
    keys = parse_keys(loads_decimal(KEYS_BODY_TEXT))

    assert keys is not None
    assert len(keys) == 1
    key = keys[0]
    assert key.name == "PoC key"
    assert key.disabled is False
    assert key.limit == Decimal(50)
    assert key.usage == Decimal("0.00010486")
    assert key.workspace_id == "ws-1"
    assert key.created_at == datetime(2026, 10, 23, 7, 34, 55, 562000, tzinfo=UTC)
    assert key.last_used_at == datetime(2026, 10, 24, 4, 21, 46, 568012, tzinfo=UTC)


def test_hash는_내부용으로만_들고_있고_label은_버린다() -> None:
    keys = parse_keys(loads_decimal(KEYS_BODY_TEXT))

    assert keys is not None
    key = keys[0]
    assert key.key_hash == "hash-of-key-1"
    assert not hasattr(key, "label")


def test_hash는_출력이나_직렬화에_나오지_않는다() -> None:
    keys = parse_keys(loads_decimal(KEYS_BODY_TEXT))

    assert keys is not None
    key = keys[0]
    assert "hash-of-key-1" not in repr(key)
    assert "hash-of-key-1" not in key.model_dump_json()
    assert "sk-or-v1" not in key.model_dump_json()


def test_시각을_읽을_수_없으면_None이다() -> None:
    body = {"data": [{"hash": "h", "created_at": "아무 말", "last_used_at": None}]}

    keys = parse_keys(body)

    assert keys is not None
    assert keys[0].created_at is None
    assert keys[0].last_used_at is None


def test_Key_목록에서_모양이_다른_항목은_건너뛴다() -> None:
    keys = parse_keys({"data": ["문자열", 5, {"hash": "h"}]})

    assert keys is not None
    assert [key.key_hash for key in keys] == ["h"]


@pytest.mark.parametrize("body", [{}, {"data": "문자열"}, {"data": {"hash": "h"}}])
def test_Key_목록의_data가_목록이_아니면_None이다(body: dict[str, Any]) -> None:
    assert parse_keys(body) is None
