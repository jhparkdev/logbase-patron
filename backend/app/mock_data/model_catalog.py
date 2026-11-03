"""등록 모델과 대표 가격. 메타데이터와 단가는 OpenRouter 스냅샷 값을 그대로 쓴다.

OpenRouter가 과거 단가를 주지 않으므로 가격 변경 이력은 지어내지 않고 모델마다 한 행씩만 둔다.
"""

from decimal import Decimal

from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.rows import Row
from app.mock_data.snapshot import Snapshot
from app.models import ConnectionTestStatus, PriceSource, PriceStatus

# model_prices 단가 컬럼 NUMERIC(30,18)의 소수 자릿수에 맞춘다.
PRICE_QUANTUM = Decimal(1).scaleb(-18)
CURRENCY = "USD"


def display_name(openrouter_name: str) -> str:
    """제작사 접두어를 뗀 이름. 예: "Anthropic: Claude Opus 5.5" -> "Claude Opus 5.5"."""
    return openrouter_name.split(": ", 1)[-1]


def quantize_price(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(PRICE_QUANTUM)


def model_rows(snapshot: Snapshot) -> list[Row]:
    by_id = {model.id: model for model in snapshot.models}
    rows: list[Row] = []
    for plan in MODEL_PLANS:
        model = by_id[plan.openrouter_model_id]
        rows.append(
            {
                "model_id": plan.model_id,
                "openrouter_model_id": model.id,
                "provider": model.id.split("/")[0],
                "display_name": display_name(model.name),
                "purpose": plan.purpose,
                "status": plan.status,
                "input_modalities": model.architecture.input_modalities,
                "output_modalities": model.architecture.output_modalities,
                "supported_parameters": model.supported_parameters,
                "context_length": model.context_length,
                "openrouter_metadata": snapshot.raw_model(model.id),
                "metadata_fetched_at": plan.registered_at,
                "last_test_status": ConnectionTestStatus.SUCCESS,
                "last_test_at": plan.tested_at,
                # 연결 테스트 호출(ai_requests)은 models보다 뒤에 들어가 외래키를 걸 수 없으므로 비워 둔다.
                "last_test_request_id": None,
                "last_success_test_at": plan.tested_at,
                "activated_at": plan.activated_at,
                "deactivated_at": plan.deactivated_at,
                "created_by": plan.created_by,
            }
        )
    return rows


def model_price_rows(snapshot: Snapshot) -> list[Row]:
    by_id = {model.id: model for model in snapshot.models}
    rows: list[Row] = []
    for plan in MODEL_PLANS:
        pricing = by_id[plan.openrouter_model_id].pricing
        rows.append(
            {
                "price_id": plan.model_id,
                "model_id": plan.model_id,
                "execution_provider": None,
                "currency": CURRENCY,
                "price_status": PriceStatus.KNOWN,
                "input_price_per_token": quantize_price(pricing.prompt),
                "output_price_per_token": quantize_price(pricing.completion),
                "cache_read_price_per_token": quantize_price(pricing.input_cache_read),
                "cache_write_price_per_token": quantize_price(
                    pricing.input_cache_write
                ),
                "raw_pricing": snapshot.raw_model(plan.openrouter_model_id)["pricing"],
                "source": PriceSource.OPENROUTER_MODELS,
                "effective_from": plan.registered_at,
                "effective_to": None,
                "checked_at": plan.registered_at,
            }
        )
    return rows
