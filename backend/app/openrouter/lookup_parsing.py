"""비용이 없는 조회 응답을 결과 모양으로 바꾼다.

외부에서 온 값이라 모양을 믿지 않는다. 구조가 틀리면 None을 돌려준다.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.openrouter.json_access import (
    get_bool,
    get_dict,
    get_int,
    get_list,
    get_number,
    get_str,
    to_number,
)
from app.openrouter.lookup_result import GenerationInfo, KeyInfo, KeyUsage, ModelInfo

ISO_DATE_LENGTH = len("2026-12-31")


def _parse_price(raw: Any) -> Decimal | None:
    """가격 하나를 Decimal로 바꾼다. OpenRouter는 가격을 문자열로 준다."""
    if isinstance(raw, str):
        try:
            price = Decimal(raw)
        except InvalidOperation:
            return None
        return price if price.is_finite() else None
    return to_number(raw)


def _parse_pricing(pricing: dict[str, Any]) -> dict[str, Decimal]:
    parsed: dict[str, Decimal] = {}
    for name, raw in pricing.items():
        price = _parse_price(raw)
        if price is None or price < 0:
            continue
        parsed[name] = price
    return parsed


def _parse_date(raw: Any) -> date | None:
    # 예고일의 실제 형식은 아직 확인하지 못했다. 날짜로 읽을 수 없으면 None으로 둔다.
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw[:ISO_DATE_LENGTH])
    except ValueError:
        return None


def _parse_datetime(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _str_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]


def parse_models(body: dict[str, Any]) -> list[ModelInfo] | None:
    items = body.get("data")
    if not isinstance(items, list):
        return None

    models: list[ModelInfo] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        model_id = get_str(item, "id")
        if not model_id:
            continue
        architecture = get_dict(item, "architecture")
        models.append(
            ModelInfo(
                model_id=model_id,
                name=get_str(item, "name"),
                pricing=_parse_pricing(get_dict(item, "pricing")),
                input_modalities=_str_list(architecture.get("input_modalities")),
                output_modalities=_str_list(architecture.get("output_modalities")),
                supported_parameters=_str_list(item.get("supported_parameters")),
                context_length=get_int(item, "context_length"),
                expiration_date=_parse_date(item.get("expiration_date")),
            )
        )
    return models


def parse_generation(body: dict[str, Any]) -> GenerationInfo | None:
    data = body.get("data")
    if not isinstance(data, dict):
        return None

    provider_statuses: list[int] = []
    for response in get_list(data, "provider_responses"):
        if not isinstance(response, dict):
            continue
        status = get_int(response, "status")
        if status is not None:
            provider_statuses.append(status)

    return GenerationInfo(
        found=True,
        total_cost=get_number(data, "total_cost"),
        native_tokens_prompt=get_int(data, "native_tokens_prompt"),
        native_tokens_completion=get_int(data, "native_tokens_completion"),
        provider=get_str(data, "provider_name"),
        cancelled=get_bool(data, "cancelled"),
        provider_statuses=provider_statuses,
    )


def parse_key_usage(body: dict[str, Any]) -> KeyUsage | None:
    data = body.get("data")
    if not isinstance(data, dict):
        return None

    return KeyUsage(
        usage=get_number(data, "usage"),
        usage_daily=get_number(data, "usage_daily"),
        usage_weekly=get_number(data, "usage_weekly"),
        usage_monthly=get_number(data, "usage_monthly"),
        limit=get_number(data, "limit"),
        limit_remaining=get_number(data, "limit_remaining"),
    )


def parse_keys(body: dict[str, Any]) -> list[KeyInfo] | None:
    items = body.get("data")
    if not isinstance(items, list):
        return None

    # label은 Key 일부가 담겨 있어 읽지 않는다.
    return [
        KeyInfo(
            name=get_str(item, "name"),
            disabled=get_bool(item, "disabled"),
            limit=get_number(item, "limit"),
            usage=get_number(item, "usage"),
            workspace_id=get_str(item, "workspace_id"),
            created_at=_parse_datetime(item.get("created_at")),
            last_used_at=_parse_datetime(item.get("last_used_at")),
            key_hash=get_str(item, "hash"),
        )
        for item in items
        if isinstance(item, dict)
    ]
