"""역할별로 어떤 모델이 호출을 받는지 시기에 따라 정한 경로.

단계가 바뀌면 MIGRATION 동안 새 모델 비중이 0에서 1로 늘어난다. 각 단계의 시작은 새 모델 활성화
뒤로, 전환이 끝나는 시각은 이전 모델 비활성화 앞으로 잡는다(테스트가 확인한다).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from random import Random

from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.period import PERIOD_START, kst

MIGRATION = timedelta(days=8)


def model_id(openrouter_model_id: str) -> int:
    return next(
        p.model_id for p in MODEL_PLANS if p.openrouter_model_id == openrouter_model_id
    )


SONNET_5 = model_id("anthropic/claude-sonnet-5")
LUNA_56 = model_id("openai/gpt-5.6-luna")
GEMINI_36 = model_id("google/gemini-3.6-flash")
DEEPSEEK_0731 = model_id("deepseek/deepseek-v4-flash-0731")
GLM = model_id("z-ai/glm-5.3-flash")
GEMINI_38 = model_id("google/gemini-3.8-flash")
DEEPSEEK_41 = model_id("deepseek/deepseek-v4.1-flash")
OPUS = model_id("anthropic/claude-opus-5.5")
LUNA_6 = model_id("openai/gpt-6-luna")
SONNET_55 = model_id("anthropic/claude-sonnet-5.5")
SOL = model_id("openai/gpt-6.1-sol")
HAIKU = model_id("anthropic/claude-haiku-5.5")
ARGON = model_id("google/gemini-4-argon")


@dataclass(frozen=True)
class Stage:
    model_id: int
    starts_at: datetime


@dataclass(frozen=True)
class Route:
    name: str
    stages: tuple[Stage, ...]


def pick_model(route: Route, at: datetime, rng: Random) -> int:
    current = route.stages[0].model_id
    for stage in route.stages[1:]:
        if at < stage.starts_at:
            break
        share_of_new = min(1.0, (at - stage.starts_at) / MIGRATION)
        if rng.random() < share_of_new:
            current = stage.model_id
    return current


def _route(name: str, *stages: tuple[int, datetime]) -> Route:
    return Route(name, tuple(Stage(model, starts) for model, starts in stages))


PDP_WRITER = _route(
    "상세 문구 작성", (SONNET_5, PERIOD_START), (SONNET_55, kst(10, 6, 9))
)
PDP_WRITER_BUDGET = _route(
    "상세 문구 작성(저비용)", (LUNA_56, PERIOD_START), (LUNA_6, kst(9, 28, 9))
)
PDP_WRITER_BEAUTY = _route(
    "상세 문구 작성(뷰티)", (SONNET_5, PERIOD_START), (SOL, kst(10, 8, 9))
)
PDP_WRITER_LIVING = _route("상세 문구 작성(리빙)", (HAIKU, kst(10, 13, 10)))
PDP_EVALUATOR = _route("문구 평가", (LUNA_56, PERIOD_START), (LUNA_6, kst(9, 28, 9)))
PDP_PREMIUM_REWRITER = _route(
    "프리미엄 재작성", (SONNET_5, PERIOD_START), (OPUS, kst(9, 29, 9))
)
IMAGE_ANALYZER = _route(
    "이미지 속성 분석", (GEMINI_36, PERIOD_START), (GEMINI_38, kst(9, 8, 9))
)
CATALOG_SUMMARIZER = _route(
    "카탈로그 요약",
    (LUNA_56, PERIOD_START),
    (DEEPSEEK_0731, kst(8, 5, 9)),
    (DEEPSEEK_41, kst(9, 17, 9)),
)
CATALOG_SUMMARIZER_LIGHT = _route(
    "카탈로그 요약(경량)", (LUNA_56, PERIOD_START), (GLM, kst(8, 31, 9))
)
INTERNAL_WRITER = _route(
    "내부 개발 기본", (SONNET_5, PERIOD_START), (SONNET_55, kst(10, 3, 9))
)
INTERNAL_TOOL_ASSISTANT = _route(
    "내부 도구",
    (LUNA_56, PERIOD_START),
    (LUNA_6, kst(9, 29, 9)),
    (HAIKU, kst(10, 14, 9)),
)
INTERNAL_LONG_DOCS = _route(
    "내부 긴 문서",
    (GEMINI_36, PERIOD_START),
    (GEMINI_38, kst(9, 6, 9)),
    (ARGON, kst(10, 21, 9)),
)

ALL_ROUTES = (
    PDP_WRITER,
    PDP_WRITER_BUDGET,
    PDP_WRITER_BEAUTY,
    PDP_WRITER_LIVING,
    PDP_EVALUATOR,
    PDP_PREMIUM_REWRITER,
    IMAGE_ANALYZER,
    CATALOG_SUMMARIZER,
    CATALOG_SUMMARIZER_LIGHT,
    INTERNAL_WRITER,
    INTERNAL_TOOL_ASSISTANT,
    INTERNAL_LONG_DOCS,
)
