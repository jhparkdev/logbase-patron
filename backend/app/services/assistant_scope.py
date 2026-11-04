"""질문의 명시적 대상과 화면을 기준으로 허용할 조회 도구를 제한한다."""

import re
from dataclasses import dataclass
from uuid import UUID

from app.schemas.assistant import AssistantChatRequest
from app.services.assistant_models import model_lookup_kind

READ_TOOLS = frozenset({"find_models", "list_simulations", "get_simulation"})
SETTINGS_TOOL = "prepare_simulator_settings"
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
RUN_ID = re.compile(
    r"(?<![0-9a-f-])[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}(?![0-9a-f-])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RequestScope:
    allowed_tools: frozenset[str]
    requires_lookup: bool = False
    clarification: str | None = None
    required_tool: str | None = None
    comparison_id: UUID | None = None


def _base_tools(changing: bool) -> frozenset[str]:
    # 결과 원문·모델명 같은 도구 데이터 속 지시로 P04 폼이 바뀌지 않도록, 설정 도구는 변경 요청에만 연다.
    return READ_TOOLS | {SETTINGS_TOOL} if changing else READ_TOOLS


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
    comparison = _comparison_scope(request)
    if comparison is not None:
        return comparison
    changing = bool(
        re.search(r"바꿔|변경|설정|세팅|해제|선택해|지정해|입력해", text)
    ) and not HELP.search(text)
    model_lookup = (
        bool(re.search(r"모델|업체", text))
        and (
            bool(re.search(r"알려|보여|조회|목록|추천|지원", text))
            or model_lookup_kind(text) == "count"
        )
        and not re.search(r"사용량|예산|지출|호출", text)
    )
    if (
        SETUP.search(text) or changing and request.simulator is not None
    ) and not re.search(r"사용량|예산|지출", text):
        return RequestScope(
            _base_tools(changing),
            requires_lookup=bool(changing or model_lookup),
            required_tool="prepare_simulator_settings"
            if changing
            else "find_models"
            if model_lookup
            else None,
        )
    if model_lookup:
        return RequestScope(
            _base_tools(changing), requires_lookup=True, required_tool="find_models"
        )
    domain = _explicit(text)
    if domain is None and re.search(r"실제\s*(?:API|호출)", text, re.IGNORECASE):
        domain = "customer"
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
            required_tool=name,
        )
    if (
        domain == "simulation"
        and not HELP.search(text)
        and re.search(r"이력|결과|요약|정리|시각|최근|비용|상태|실행\s*ID", text)
    ):
        detail = bool(
            re.search(
                r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", text, re.IGNORECASE
            )
        )
        return RequestScope(
            _base_tools(changing),
            requires_lookup=True,
            required_tool="get_simulation" if detail else "list_simulations",
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
    return RequestScope(_base_tools(changing))


def _comparison_scope(request: AssistantChatRequest) -> RequestScope | None:
    text = request.messages[-1].content
    context = request.page_context
    ids = set(RUN_ID.findall(text.lower()))
    simulation_page = context and context.page in {"simulator", "simulation_history"}
    if (
        CUSTOMER.search(text)
        or INTERNAL.search(text)
        or HELP.search(text)
        # “가장 저렴한 업체로 선택해줘”처럼 순위 표현이 든 설정 요청은 실행 비교가 아니다.
        or re.search(
            r"바꿔|변경해|설정해|세팅|선택해|지정해|입력해|입력할|실행해|돌려|추천|등록된|선택할|사용할|지원하는",
            text,
        )
        or not (
            simulation_page
            or SIMULATION.search(text)
            or ids
            or re.search(r"실행.*결과", text)
        )
        or not re.search(
            r"비교|차이|최저\s*비용|더\s*(?:빠|빨|저렴|싼|느)|가장.*(?:빠|저렴|짧)|어느.*(?:빠|저렴)|어떤.*(?:빠|저렴)|모델별.*(?:비용|시간|토큰|검증|결과)",
            text,
        )
    ):
        return None
    if len(ids) > 1 or re.search(r"(?:서로\s*다른|여러|두)\s*실행", text):
        return RequestScope(
            frozenset(),
            clarification="현재는 한 실행 안의 전체 모델을 정량 비교해요. 비교할 실행 ID 한 개를 지정해 주세요.",
        )
    selected = (
        UUID(next(iter(ids)))
        if ids
        else context.simulation_id
        if simulation_page
        else None
    )
    if selected is None or (not ids and re.search(r"최근|최신|마지막|이전|다른", text)):
        return RequestScope(
            frozenset(),
            clarification="비교할 실행을 확인해 주세요. 시뮬레이션 이력에서 실행 상세를 열거나 실행 ID 한 개를 질문에 넣어 주세요.",
        )
    return RequestScope(
        frozenset({"get_simulation"}),
        requires_lookup=True,
        required_tool="get_simulation",
        comparison_id=selected,
    )
