"""상세 화면에서 보여 줄 고객 호출 원문. 고객마다 최근 성공 호출 몇 건에만 남긴다(전체에 넣으면 SQL이 커진다).

원문은 고객 업종에 맞는 가상의 상품으로 만들고, 평가 결과는 같은 작업에 재작성이 있었는지와 맞춘다.
"""

import json

from pydantic import JsonValue

from app.mock_data import sim_answers
from app.mock_data.ids import rng_for
from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.organizations import AI_PDP, FLIPPAGE, service_id
from app.mock_data.rows import Row
from app.mock_data.sim_content import (
    MODEL_TIERS,
    PRODUCTS,
    Product,
    Tier,
    copy_input,
    unstructured_text,
)
from app.mock_data.usage import CustomerUsage
from app.models import CallPurpose, RequestStatus

CALLS_PER_CUSTOMER = 8
PASSING_SCORE = 80
SYSTEM_PROMPTS = {
    AI_PDP: "당신은 온라인 쇼핑몰의 상품 상세페이지 작성 도우미입니다.",
    FLIPPAGE: "당신은 쇼핑몰 카탈로그를 목록용 문구로 정리하는 도우미입니다.",
}


def products_of(customer_id: int | None) -> list[Product]:
    return [p for p in PRODUCTS if p.customer_id == customer_id]


def _evaluation(rewritten: bool, score: int) -> str:
    issues = (
        ["과장 표현('최고', '완벽')이 있음", "소재 정보가 두 번 반복됨"]
        if rewritten
        else []
    )
    return json.dumps(
        {"score": score, "pass": not rewritten, "issues": issues}, ensure_ascii=False
    )


def _message_and_answer(
    call: Row, task_type: str, rewritten: bool, product: Product, tier: Tier
) -> tuple[str, str]:
    rng = rng_for(f"payload:{call['request_id']}")
    if task_type == "CATALOG_SUMMARY":
        message = f"다음 카탈로그 항목을 목록용 2줄 요약으로 정리하세요.\n{unstructured_text(product)}"
        answer = f"{product.name} | {product.price:,}원\n{', '.join(product.options)} · {product.praises[0]}"
        return message, answer
    if task_type == "IMAGE_ANALYSIS":
        message = f"상품 이미지를 보고 색상, 소재, 카테고리를 JSON으로 추출하세요.\n상품명: {product.name}"
        answer = {
            "color": product.options[0],
            "material": product.material,
            "category": product.category,
        }
        return message, json.dumps(answer, ensure_ascii=False)
    draft = sim_answers.product_copy(product, tier, rng)
    if call["call_purpose"] == CallPurpose.EVALUATION:
        score = (
            rng.randint(55, PASSING_SCORE - 1)
            if rewritten
            else rng.randint(PASSING_SCORE, 96)
        )
        message = f"다음 상세 설명을 정확성·과장 표현·가독성 기준으로 채점하고 JSON으로 답하세요.\n{draft}"
        return message, _evaluation(rewritten, score)
    message = f"다음 상품의 상세 설명 3문단과 마케팅 문구 1줄을 작성하세요.\n{copy_input(product)}"
    return message, draft


def customer_payload_rows(usage: CustomerUsage) -> list[Row]:
    tasks = {t["task_id"]: t for t in usage.tasks}
    rewritten = {
        r["task_id"]
        for r in usage.requests
        if r["call_purpose"] == CallPurpose.REGENERATION
    }
    tiers = {p.model_id: MODEL_TIERS[p.openrouter_model_id] for p in MODEL_PLANS}
    services = {service_id(code): code for code in SYSTEM_PROMPTS}
    rows: list[Row] = []
    for customer_id in sorted({p.customer_id for p in PRODUCTS}):
        candidates = [
            r
            for r in usage.requests
            if r["customer_id"] == customer_id
            and r["status"] == RequestStatus.SUCCESS
            and r["task_id"] in tasks
        ]
        products = products_of(customer_id)
        for call in sorted(candidates, key=lambda r: r["requested_at"])[
            -CALLS_PER_CUSTOMER:
        ]:
            task = tasks[call["task_id"]]
            product = products[call["request_id"].int % len(products)]
            message, answer = _message_and_answer(
                call,
                task["task_type"],
                call["task_id"] in rewritten,
                product,
                tiers[call["model_id"]],
            )
            messages: list[JsonValue] = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPTS[services[call["service_id"]]],
                },
                {"role": "user", "content": message},
            ]
            rows.append(
                {
                    "request_id": call["request_id"],
                    "request_messages": messages,
                    "response_text": answer,
                    "response_raw": None,
                }
            )
    return rows
