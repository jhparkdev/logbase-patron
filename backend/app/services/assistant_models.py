"""모델 질문의 표시 범위와 조회로 확인된 답변을 정한다."""

import re
from typing import Any, Literal

ModelLookupKind = Literal["count", "list", "providers"]


def model_lookup_kind(
    text: str, previous_user_requests: tuple[str, ...] = ()
) -> ModelLookupKind:
    if re.fullmatch(
        r"\s*(?:다음(?:\s*페이지)?|이어서|계속|나머지)(?:\s*(?:보여줘|알려줘))?[.!?]?\s*",
        text,
    ):
        for previous in reversed(previous_user_requests):
            if re.search(r"모델|업체|provider", previous, re.IGNORECASE):
                return model_lookup_kind(previous)
    omit_providers = re.search(
        r"(?:업체|provider)(?:\s*(?:정보|목록|이름))?(?:는|은|를|도)?\s*(?:없이|빼고|제외|말고|생략|필요\s*없|알려주지|보여주지)",
        text,
        re.IGNORECASE,
    )
    explicit_providers = not omit_providers and re.search(
        r"업체|provider|어디.*실행|어느.*서버", text, re.IGNORECASE
    )
    if explicit_providers or re.search(r"선택해|바꿔|변경해|설정해|골라|지정해", text):
        return "providers"
    if re.search(r"목록|이름|리스트", text):
        return "list"
    if re.search(
        r"개수|몇\s*개|모델(?:의)?\s*(?:총\s*)?수(?:가|는|를|도|[?？]|$)|how many|count",
        text,
        re.IGNORECASE,
    ):
        return "count"
    return "list"


def model_answer(result: dict[str, Any]) -> str:
    total = result["total"]
    scope = (
        f"‘{result['q']}’ 검색 결과 기준" if result.get("q") else "전체 등록 모델 기준"
    )
    if result.get("view") == "count":
        return f"{scope}, 사용 중 상태는 {total:,}개예요."
    rows = result["items"]
    if not rows:
        return (
            f"{scope}, 사용 중 상태의 모델이 없어요."
            if not total
            else f"{scope}, 사용 중 모델은 {total:,}개이며 이 페이지에는 결과가 없어요. 이전 페이지를 확인해 주세요."
        )
    page = result.get("page", 1)
    size = result.get("page_size", 5)
    start = (page - 1) * size + 1
    end = start + len(rows) - 1
    heading = (
        f"‘{result['q']}’ 검색 결과에서 사용 가능한 모델은 {total:,}개입니다."
        if result.get("q")
        else f"지금 사용 가능한 모델은 {total:,}개입니다."
    )
    lines = [heading]
    show_providers = result.get("view") == "providers"
    for row in rows:
        lines.append(f"- {row['name']} — 모델 제공사: {row.get('creator') or '미확인'}")
        if show_providers:
            names = ", ".join(item["execution_provider"] for item in row["providers"])
            lines.append(f"실행 업체: {names or '확인하지 못했어요'}")
    if show_providers:
        lines.append(
            "업체 목록은 호출 경로 정보이며 실제 호출 성공을 검증한 결과는 아니에요."
        )
    footer = "등록 모델의 ‘사용 중’ 상태를 기준으로 조회했어요."
    if start > 1 or end < total:
        footer = f"{start:,}~{end:,}번째 모델을 표시했어요. {footer}"
    if end < total:
        footer += " 이어서 보려면 ‘다음 페이지 보여줘’라고 요청해 주세요."
    lines.append(footer)
    return "\n\n".join(lines)
