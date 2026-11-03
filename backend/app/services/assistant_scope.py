"""질문의 명시적 대상과 화면을 기준으로 허용할 조회 도구를 제한한다."""

import re
from dataclasses import dataclass

from app.schemas.assistant import AssistantChatRequest

BASE_TOOLS = frozenset(
    {"find_models", "list_simulations", "get_simulation", "prepare_simulator_settings"}
)
CUSTOMER = re.compile(r"고객|customer", re.IGNORECASE)
INTERNAL = re.compile(r"내부|프로젝트|구독료?|internal", re.IGNORECASE)
SIMULATION = re.compile(
    r"시뮬|비교\s*실행|실행\s*ID|최근\s*실행|simulation", re.IGNORECASE
)
SETUP = re.compile(
    r"프롬프트|prompt|temperature|reasoning|JSON\s*(?:Schema|스키마)|(?:토큰|모델|업체).*(?:바꿔|변경|설정|선택)|모델.*(?:지원|목록|추천)",
    re.IGNORECASE,
)
DATA = re.compile(
    r"호출|사용량|예산|비용|지출|구독|최근|마지막|최신|이번\s*달|지난\s*달"
)
HELP = re.compile(r"방법|어떻게|할\s*수|가능|기능")


@dataclass(frozen=True)
class RequestScope:
    allowed_tools: frozenset[str]
    requires_lookup: bool = False
    clarification: str | None = None


def _explicit(text: str) -> str | None:
    domains = [
        name
        for name, pattern in (
            ("customer", CUSTOMER),
            ("internal", INTERNAL),
            ("simulation", SIMULATION),
        )
        if pattern.search(text)
    ]
    return domains[0] if len(domains) == 1 else "mixed" if domains else None


def request_scope(request: AssistantChatRequest) -> RequestScope:
    text = request.messages[-1].content
    if re.search(
        r"(?:예산|구독료).*(?:변경해|바꿔|설정해|등록해|저장해|수정해|늘려|줄여|올려|내려)",
        text,
    ):
        return RequestScope(
            frozenset(),
            clarification="현재 도우미는 사용량·비용·예산 조회를 지원해요. 예산이나 구독료를 바꾸려면 해당 화면에서 값을 확인하고 직접 저장해 주세요.",
        )
    if SETUP.search(text) and not re.search(r"사용량|예산|지출", text):
        return RequestScope(BASE_TOOLS)
    domain = _explicit(text)
    if domain == "mixed":
        return RequestScope(
            frozenset(),
            clarification="고객의 실제 API 사용량, 내부 비용, 시뮬레이션 결과 중 어느 범위를 먼저 조회할까요? 서로 다른 출처는 구분해서 조회해 주세요.",
        )
    if domain is None and request.page_context:
        domain = {
            "customer_usage": "customer",
            "internal_budget": "internal",
            "simulation_history": "simulation",
            "simulator": "simulation",
        }.get(request.page_context.page)
    if domain is None:
        for previous in reversed(request.messages[:-1]):
            if previous.role == "user" and (
                candidate := _explicit(previous.content)
            ) in {"customer", "internal", "simulation"}:
                domain = candidate
                break
    if domain in {"customer", "internal"}:
        name = "get_customer_usage" if domain == "customer" else "get_internal_usage"
        return RequestScope(
            frozenset({name}),
            requires_lookup=not bool(HELP.search(text))
            and bool(
                DATA.search(text)
                or CUSTOMER.search(text)
                or INTERNAL.search(text)
                or re.search(r"요약|정리|현황|금액|총액|건수", text)
            ),
        )
    if (
        domain is None
        and DATA.search(text)
        and not re.search(r"모델.*(?:가격|단가|비용)", text)
    ):
        return RequestScope(
            frozenset(),
            clarification="어느 데이터를 조회할까요? 고객의 실제 API 사용량, 내부 프로젝트 비용, 시뮬레이션 이력 중에서 선택해 주세요.",
        )
    return RequestScope(BASE_TOOLS)
