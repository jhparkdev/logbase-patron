"""시뮬레이터 시나리오 템플릿 5개. v0.6 seed와 같은 코드·문구를 유지한다.

데이터 요약 시나리오는 2026-11-02에 'JSON Schema 구조화' 조건이 더해졌다. 실행은 당시 값을
simulation_runs에 복사해 두므로, 그 전 실행에는 바뀌기 전 프롬프트가 남아 있다.
"""

from dataclasses import dataclass

from pydantic import JsonValue

from app.mock_data.period import kst
from app.mock_data.rows import Row
from app.models import InputType

CHANGED_AT = kst(11, 2, 17)
DATA_SUMMARY_PROMPT_BEFORE_CHANGE = "다음 데이터를 5줄 이내로 요약하세요.\n{{data}}"


@dataclass(frozen=True)
class MockScenario:
    scenario_id: int
    scenario_code: str
    name: str
    description: str
    input_type: InputType
    prompt_template: str
    default_json_schema: dict[str, JsonValue] | None
    default_execution_config: dict[str, JsonValue]


def _string_fields(*names: str) -> dict[str, JsonValue]:
    return {name: {"type": "string"} for name in names}


SCENARIOS = (
    MockScenario(
        1,
        "PRODUCT_IMAGE_ANALYSIS",
        "상품 이미지·속성 분석",
        "상품 이미지에서 색상·소재·카테고리 등 속성을 추출",
        InputType.TEXT_IMAGE,
        "다음 상품 이미지를 보고 색상, 소재, 카테고리를 JSON으로 추출하세요.\n상품명: {{product_name}}",
        {
            "type": "object",
            "required": ["color", "material", "category"],
            "properties": _string_fields("color", "material", "category"),
        },
        {"temperature": 0.2, "max_tokens": 512},
    ),
    MockScenario(
        2,
        "PRODUCT_COPY",
        "상품 설명 및 마케팅 문구 생성",
        "상품 정보로 상세 설명과 마케팅 문구 작성",
        InputType.TEXT,
        "다음 상품 정보로 상세 설명 3문단과 마케팅 문구 1줄을 작성하세요.\n{{product_info}}",
        None,
        {"temperature": 0.7, "max_tokens": 1024},
    ),
    MockScenario(
        3,
        "DATA_SUMMARY",
        "데이터 요약 및 구조화",
        "긴 상품 리뷰·스펙 데이터를 요약하고 구조화",
        InputType.TEXT,
        "다음 데이터를 5줄 이내로 요약하고, 지정한 JSON Schema에 맞춰 구조화하세요.\n{{data}}",
        {
            "type": "object",
            "required": ["summary", "key_points"],
            "properties": {
                "summary": {"type": "string"},
                "key_points": {"type": "array", "items": {"type": "string"}},
            },
        },
        {"temperature": 0.3, "max_tokens": 512},
    ),
    MockScenario(
        4,
        "TEXT_TO_JSON",
        "비정형 텍스트 → JSON 변환",
        "비정형 상품 설명을 지정 JSON 구조로 변환",
        InputType.TEXT,
        "다음 텍스트를 지정한 JSON Schema에 맞춰 변환하세요.\n{{text}}",
        {
            "type": "object",
            "required": ["name", "price", "options"],
            "properties": {
                "name": {"type": "string"},
                "price": {"type": "integer"},
                "options": {"type": "array", "items": {"type": "string"}},
            },
        },
        {"temperature": 0, "max_tokens": 512},
    ),
    MockScenario(
        5,
        "GENERAL_REASONING",
        "일반 분석 및 추론",
        "판매 데이터 기반 간단한 분석·추론",
        InputType.TEXT,
        "다음 판매 데이터를 보고 다음 달 재고 전략을 제안하세요.\n{{data}}",
        None,
        {"temperature": 0.5, "max_tokens": 1024},
    ),
)


def by_code(scenario_code: str) -> MockScenario:
    return next(s for s in SCENARIOS if s.scenario_code == scenario_code)


def scenario_rows() -> list[Row]:
    return [
        {
            "scenario_id": s.scenario_id,
            "scenario_code": s.scenario_code,
            "name": s.name,
            "description": s.description,
            "input_type": s.input_type,
            "prompt_template": s.prompt_template,
            "default_json_schema": s.default_json_schema,
            "default_execution_config": s.default_execution_config,
            "is_active": True,
        }
        for s in SCENARIOS
    ]
