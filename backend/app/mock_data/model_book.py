"""호출을 만들 때 쓰는 모델별 정보 묶음: OpenRouter ID, 가격 행, 단가, 응답 속도."""

from dataclasses import dataclass
from decimal import Decimal

from app.mock_data.model_catalog import PRICE_QUANTUM, display_name, quantize_price
from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.model_profiles import PROFILES, ModelProfile
from app.mock_data.snapshot import Snapshot


@dataclass(frozen=True)
class ModelEntry:
    model_id: int
    openrouter_id: str
    display_name: str
    price_id: int
    input_price: Decimal
    output_price: Decimal
    cache_read_price: Decimal | None
    profile: ModelProfile


type ModelBook = dict[int, ModelEntry]


def build_model_book(snapshot: Snapshot) -> ModelBook:
    models = {model.id: model for model in snapshot.models}
    book: ModelBook = {}
    for plan in MODEL_PLANS:
        model = models[plan.openrouter_model_id]
        prices = model.pricing
        book[plan.model_id] = ModelEntry(
            model_id=plan.model_id,
            openrouter_id=plan.openrouter_model_id,
            display_name=display_name(model.name),
            # model_catalog가 모델마다 가격 행을 하나씩 같은 번호로 만든다.
            price_id=plan.model_id,
            input_price=prices.prompt.quantize(PRICE_QUANTUM),
            output_price=prices.completion.quantize(PRICE_QUANTUM),
            cache_read_price=quantize_price(prices.input_cache_read),
            profile=PROFILES[plan.openrouter_model_id],
        )
    return book
