"""시나리오별 실행 입력과, 모델 등급을 받아 답을 만드는 함수의 짝.

시나리오 프롬프트는 실행 당시 값이다. 데이터 요약은 조건이 바뀐 시각 전후로 프롬프트가 다르다.
"""

from collections.abc import Callable
from datetime import datetime
from random import Random

from app.mock_data import sim_answers, sim_content
from app.mock_data.scenarios import (
    CHANGED_AT,
    DATA_SUMMARY_PROMPT_BEFORE_CHANGE,
    by_code,
)
from app.mock_data.sim_content import Flaw, Product, Tier

CUSTOM = "CUSTOM"
FLAW_WEIGHTS = {
    Flaw.NONE: 80,
    Flaw.CODE_FENCE: 6,
    Flaw.WRONG_TYPE: 7,
    Flaw.MISSING_FIELD: 7,
}

type Answer = Callable[[Tier, Random], str]


def _flaw(rng: Random) -> Flaw:
    return rng.choices(list(FLAW_WEIGHTS), weights=list(FLAW_WEIGHTS.values()))[0]


def scenario_input(
    code: str, product: Product, at: datetime, rng: Random
) -> tuple[str, str, Answer]:
    """(프롬프트, 입력, 모델 등급별 답) — 시나리오 프롬프트는 실행 당시 값이다."""
    if code == "PRODUCT_COPY":
        return (
            by_code(code).prompt_template,
            sim_content.copy_input(product),
            (lambda tier, r: sim_answers.product_copy(product, tier, r)),
        )
    if code == "TEXT_TO_JSON":
        return (
            by_code(code).prompt_template,
            sim_content.unstructured_text(product),
            (lambda tier, r: sim_answers.text_to_json(product, tier, _flaw(r), r)),
        )
    if code == "DATA_SUMMARY":
        if at < CHANGED_AT:
            return (
                DATA_SUMMARY_PROMPT_BEFORE_CHANGE,
                sim_content.review_data(product),
                (lambda tier, r: sim_answers.summary_lines(product, tier, r)),
            )
        return (
            by_code(code).prompt_template,
            sim_content.review_data(product),
            (lambda tier, r: sim_answers.structured_summary(product, tier, _flaw(r))),
        )
    return (
        by_code(code).prompt_template,
        sim_content.sales_data(product, rng),
        (lambda tier, r: sim_answers.stock_strategy(product, tier, r)),
    )


def custom_input(product: Product, rng: Random) -> tuple[str, str, Answer]:
    if rng.random() < 0.5:
        return (
            sim_content.INQUIRY_PROMPT,
            sim_content.inquiry_input(product),
            (lambda tier, r: sim_answers.inquiry_reply(product, tier, r)),
        )
    return (
        sim_content.TITLE_PROMPT,
        sim_content.title_input(product),
        (lambda tier, r: sim_answers.search_title(product, tier, r)),
    )
