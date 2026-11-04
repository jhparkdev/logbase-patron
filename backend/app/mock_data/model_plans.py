"""등록 모델의 일정(등록·활성화·비활성화)과 용도.

일정은 실제 출시일 뒤로 잡는다. 이전 세대 4개는 후속 모델이 활성화된 뒤 비활성화되어,
9~10월에 호출이 새 모델로 옮겨 가는 모습을 만든다.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.mock_data.period import kst
from app.models import ModelStatus

# 연결 테스트는 활성화 직전에 한다. 아직 활성화 전이면 등록 직후에 한다.
TEST_BEFORE_ACTIVATION = timedelta(minutes=15)
TEST_AFTER_REGISTRATION = timedelta(minutes=10)


@dataclass(frozen=True)
class ModelPlan:
    model_id: int
    openrouter_model_id: str
    purpose: str
    created_by: int
    registered_at: datetime
    activated_at: datetime | None = None
    deactivated_at: datetime | None = None
    replaced_by: str | None = None  # 이 모델 대신 쓰게 된 후속 모델

    @property
    def status(self) -> ModelStatus:
        if self.deactivated_at is not None:
            return ModelStatus.INACTIVE
        if self.activated_at is not None:
            return ModelStatus.ACTIVE
        return ModelStatus.TESTING

    @property
    def tested_at(self) -> datetime:
        if self.activated_at is not None:
            return self.activated_at - TEST_BEFORE_ACTIVATION
        return self.registered_at + TEST_AFTER_REGISTRATION


SONNET_55 = "anthropic/claude-sonnet-5.5"
GPT_6_LUNA = "openai/gpt-6-luna"
GEMINI_38_FLASH = "google/gemini-3.8-flash"
DEEPSEEK_41_FLASH = "deepseek/deepseek-v4.1-flash"

# 등록 순서. model_id와 price_id가 이 순서를 따른다.
MODEL_PLANS = (
    ModelPlan(
        1,
        "anthropic/claude-sonnet-5",
        "상세페이지 문구 생성 (이전 주력)",
        1,
        kst(7, 2, 10),
        kst(7, 2, 10, 30),
        kst(10, 20, 18),
        SONNET_55,
    ),
    ModelPlan(
        2,
        "openai/gpt-5.6-luna",
        "저비용 요약·분류 (이전 세대)",
        2,
        kst(7, 13, 14),
        kst(7, 13, 14, 20),
        kst(10, 10, 17),
        GPT_6_LUNA,
    ),
    ModelPlan(
        3,
        "google/gemini-3.6-flash",
        "이미지 속성 분석 (이전 세대)",
        1,
        kst(7, 23, 11),
        kst(7, 23, 11, 30),
        kst(9, 25, 16),
        GEMINI_38_FLASH,
    ),
    ModelPlan(
        4,
        "deepseek/deepseek-v4-flash-0731",
        "대량 태그·키워드 생성 (이전 세대)",
        6,
        kst(8, 4, 10),
        kst(8, 4, 10, 20),
        kst(10, 1, 11),
        DEEPSEEK_41_FLASH,
    ),
    ModelPlan(
        5,
        "z-ai/glm-5.3-flash",
        "대량 태그·키워드 생성",
        3,
        kst(8, 28, 15),
        kst(8, 29, 10),
    ),
    ModelPlan(
        6, GEMINI_38_FLASH, "이미지 속성 분석", 1, kst(9, 4, 10), kst(9, 5, 9, 30)
    ),
    ModelPlan(
        7, DEEPSEEK_41_FLASH, "저비용 초안 생성", 3, kst(9, 12, 14), kst(9, 15, 10)
    ),
    ModelPlan(
        8,
        "anthropic/claude-opus-5.5",
        "고품질 생성·평가 기준 모델",
        2,
        kst(9, 24, 10),
        kst(9, 25, 14),
    ),
    ModelPlan(9, GPT_6_LUNA, "저비용 요약·분류", 2, kst(9, 24, 10, 30), kst(9, 26, 11)),
    ModelPlan(10, SONNET_55, "상세페이지 문구 생성", 1, kst(9, 30, 10), kst(10, 2, 10)),
    ModelPlan(
        11,
        "openai/gpt-6.1-sol",
        "상세페이지 문구 생성 비교 대상",
        4,
        kst(10, 1, 15),
        kst(10, 6, 10),
    ),
    ModelPlan(
        12,
        "google/gemini-nano-banana-2.1",
        "상품 이미지 생성",
        4,
        kst(10, 8, 10),
        kst(10, 10, 10),
    ),
    ModelPlan(
        13,
        "anthropic/claude-haiku-5.5",
        "짧은 문구·분류",
        5,
        kst(10, 9, 11),
        kst(10, 13, 10),
    ),
    ModelPlan(
        14,
        "google/gemini-4-argon",
        "긴 문서 요약·비교 대상",
        5,
        kst(10, 15, 10),
        kst(10, 20, 10),
    ),
    ModelPlan(15, "moonshotai/kimi-k3.1-pro", "추론 모델 검증 중", 4, kst(10, 27, 14)),
)
