from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.openrouter.lookup_parsing import (
    parse_endpoints,
    parse_generation,
    parse_key_usage,
    parse_keys,
    parse_models,
)


# ---------------------------------------------------------------
# 모델 목록
# ---------------------------------------------------------------
def test_모델_목록에서_ID_가격_입력_형식을_꺼낸다() -> None:
    body = {
        "data": [
            {
                "id": "a/b",
                "pricing": {
                    "prompt": "0.000002",
                    "completion": "0.00001",
                    "input_cache_read": "0.0000002",
                },
                "name": "Example: Model A",
                "architecture": {
                    "input_modalities": ["text", "image"],
                    "output_modalities": ["text"],
                },
                "supported_parameters": ["response_format", "reasoning"],
                "context_length": 1000,
                "expiration_date": "2026-12-31",
            }
        ]
    }

    models = parse_models(body)

    assert models is not None
    assert len(models) == 1
    model = models[0]
    assert model.model_id == "a/b"
    assert model.pricing == {
        "prompt": Decimal("0.000002"),
        "completion": Decimal("0.00001"),
        "input_cache_read": Decimal("0.0000002"),
    }
    assert model.name == "Example: Model A"
    assert model.input_modalities == ["text", "image"]
    assert model.output_modalities == ["text"]
    assert model.supported_parameters == ["response_format", "reasoning"]
    assert model.context_length == 1000
    assert model.expiration_date == date(2026, 12, 31)


def test_예고일_필드가_없는_모델은_expiration_date가_None이다() -> None:
    models = parse_models({"data": [{"id": "a/b"}]})

    assert models is not None
    assert models[0].expiration_date is None


def test_이름과_출력_형식이_없으면_None과_빈_목록이다() -> None:
    models = parse_models({"data": [{"id": "a/b"}]})

    assert models is not None
    assert models[0].name is None
    assert models[0].output_modalities == []


def test_이름이_문자열이_아니면_None이다() -> None:
    models = parse_models({"data": [{"id": "a/b", "name": 5}]})

    assert models is not None
    assert models[0].name is None


def test_가격_단위는_문자열도_정확한_Decimal로_읽는다() -> None:
    body = {"data": [{"id": "a/b", "pricing": {"prompt": "0.000000029"}}]}

    models = parse_models(body)

    assert models is not None
    assert models[0].pricing["prompt"] == Decimal("0.000000029")


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
    body = {
        "data": {
            "total_cost": Decimal("0.5"),
            "provider_name": "ExampleProvider",
            "cancelled": False,
            "provider_responses": [{"status": 200}],
        }
    }

    info = parse_generation(body)

    assert info is not None
    assert info.found is True
    assert info.total_cost == Decimal("0.5")
    assert info.provider == "ExampleProvider"
    assert info.cancelled is False
    assert info.provider_statuses == [200]


def test_토큰은_비용과_맞는_native_값을_쓴다() -> None:
    body = {
        "data": {
            "native_tokens_prompt": 20,
            "native_tokens_completion": 5,
            "tokens_prompt": 11,
            "tokens_completion": 3,
        }
    }

    info = parse_generation(body)

    assert info is not None
    # tokens_prompt(11)는 비용과 맞지 않는다 (검증 보고서 API-03)
    assert info.native_tokens_prompt == 20
    assert info.native_tokens_completion == 5


def test_취소된_호출은_cancelled와_499로_알_수_있다() -> None:
    body = {"data": {"cancelled": True, "provider_responses": [{"status": 499}]}}

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
    body = {
        "data": {
            "limit": 10,
            "limit_remaining": Decimal("9.5"),
            "usage": Decimal("0.5"),
            "usage_daily": Decimal("0.1"),
            "usage_weekly": Decimal("0.2"),
            "usage_monthly": Decimal("0.4"),
        }
    }

    usage = parse_key_usage(body)

    assert usage is not None
    assert usage.usage == Decimal("0.5")
    assert usage.usage_daily == Decimal("0.1")
    assert usage.usage_weekly == Decimal("0.2")
    assert usage.usage_monthly == Decimal("0.4")
    assert usage.limit == Decimal(10)
    assert usage.limit_remaining == Decimal("9.5")


def test_한도가_없으면_limit이_None이다() -> None:
    body = {"data": {"usage": 1, "limit": None, "limit_remaining": None}}

    usage = parse_key_usage(body)

    assert usage is not None
    assert usage.limit is None
    assert usage.limit_remaining is None


def test_Key_사용량_결과에는_label이_없다() -> None:
    usage = parse_key_usage({"data": {"label": "example-label", "usage": 1}})

    assert usage is not None
    assert not hasattr(usage, "label")


@pytest.mark.parametrize("body", [{}, {"data": "문자열"}])
def test_Key_사용량의_data가_객체가_아니면_None이다(body: dict[str, Any]) -> None:
    assert parse_key_usage(body) is None


# ---------------------------------------------------------------
# Key 목록 (Management Key)
# ---------------------------------------------------------------
def test_Key_목록에서_이름_사용량_workspace_시각을_꺼낸다() -> None:
    body = {
        "data": [
            {
                "hash": "h",
                "name": "test-key",
                "disabled": False,
                "limit": 10,
                "usage": Decimal("0.25"),
                "workspace_id": "ws-1",
                "created_at": "2026-01-01T00:00:00.123Z",
                "last_used_at": "2026-01-02T00:00:00.456789Z",
            }
        ]
    }

    keys = parse_keys(body)

    assert keys is not None
    assert len(keys) == 1
    key = keys[0]
    assert key.name == "test-key"
    assert key.disabled is False
    assert key.limit == Decimal(10)
    assert key.usage == Decimal("0.25")
    assert key.workspace_id == "ws-1"
    assert key.created_at == datetime(2026, 1, 1, 0, 0, 0, 123000, tzinfo=UTC)
    assert key.last_used_at == datetime(2026, 1, 2, 0, 0, 0, 456789, tzinfo=UTC)


def test_hash는_내부용으로만_들고_있고_label은_버린다() -> None:
    body = {"data": [{"hash": "hash-of-key-1", "label": "example-label"}]}

    keys = parse_keys(body)

    assert keys is not None
    key = keys[0]
    assert key.key_hash == "hash-of-key-1"
    assert not hasattr(key, "label")


def test_hash와_label은_출력이나_직렬화에_나오지_않는다() -> None:
    body = {"data": [{"hash": "hash-of-key-1", "label": "example-label"}]}

    keys = parse_keys(body)

    assert keys is not None
    key = keys[0]
    assert "hash-of-key-1" not in repr(key)
    assert "hash-of-key-1" not in key.model_dump_json()
    assert "example-label" not in repr(key)
    assert "example-label" not in key.model_dump_json()


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


# ---------------------------------------------------------------
# 모델 하나의 서버 업체 목록
# ---------------------------------------------------------------
def endpoint(name: str | None, **fields: Any) -> dict[str, Any]:
    return {"provider_name": name, "status": 0, "uptime_last_1d": 99.5, **fields}


def test_업체_목록에서_이름_상태_가동률을_꺼낸다() -> None:
    body = {
        "data": {
            "id": "a/b",
            "endpoints": [
                endpoint("Io Net", uptime_last_1d=99.51388888888889),
                endpoint("DekaLLM", status=-1, uptime_last_1d=None),
            ],
        }
    }

    endpoints = parse_endpoints(body)

    assert endpoints is not None
    assert [item.provider_name for item in endpoints] == ["Io Net", "DekaLLM"]
    assert [item.status for item in endpoints] == [0, -1]
    assert endpoints[0].uptime_last_1d == Decimal("99.51388888888889")
    assert endpoints[1].uptime_last_1d is None


def test_같은_이름의_업체는_처음_것_하나만_남긴다() -> None:
    body = {
        "data": {
            "endpoints": [
                endpoint("DeepInfra", status=0),
                endpoint("DeepInfra", status=-1),
                endpoint("Parasail"),
            ]
        }
    }

    endpoints = parse_endpoints(body)

    assert endpoints is not None
    assert [(item.provider_name, item.status) for item in endpoints] == [
        ("DeepInfra", 0),
        ("Parasail", 0),
    ]


def test_업체_목록에서_이름이_없거나_모양이_다른_항목은_건너뛴다() -> None:
    body = {
        "data": {
            "endpoints": [
                "문자열",
                endpoint(None),
                endpoint(""),
                endpoint(5),
                {"status": 0},
                endpoint("DekaLLM"),
            ]
        }
    }

    endpoints = parse_endpoints(body)

    assert endpoints is not None
    assert [item.provider_name for item in endpoints] == ["DekaLLM"]


def test_상태와_가동률의_모양이_다르면_None으로_둔다() -> None:
    item = endpoint("DekaLLM", status="정상", uptime_last_1d="높음")

    endpoints = parse_endpoints({"data": {"endpoints": [item]}})

    assert endpoints is not None
    assert endpoints[0].status is None
    assert endpoints[0].uptime_last_1d is None


def test_업체가_하나도_없어도_정상_응답이면_빈_목록이다() -> None:
    endpoints = parse_endpoints({"data": {"endpoints": []}})

    assert endpoints == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"data": "문자열"},
        {"data": []},
        {"data": {}},
        {"data": {"endpoints": "문자열"}},
        {"data": {"endpoints": {"provider_name": "DekaLLM"}}},
    ],
)
def test_업체_목록의_모양이_틀리면_None이다(body: dict[str, Any]) -> None:
    assert parse_endpoints(body) is None
