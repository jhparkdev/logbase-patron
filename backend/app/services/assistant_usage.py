"""P01·P02의 읽기 서비스를 에이전트에 연결한다. 집계·예산 계산이나 저장은 하지 않는다."""

import re
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.assistant import AssistantPageContext, AssistantSource
from app.schemas.assistant_usage import (
    TOOL_PAGE_SIZE,
    CustomerUsageToolQuery,
    InternalUsageToolQuery,
    UsageToolOptions,
)
from app.schemas.internal_requests import InternalRequestsQuery
from app.schemas.project_budget import ProjectRowSort, ProjectRowsQuery
from app.schemas.usage import (
    CustomerRowSort,
    CustomerRowsQuery,
    RequestRowSort,
    RequestRowsQuery,
    UsageOption,
)
from app.services import aggregation, internal_requests, internal_usage, project_budgets
from app.services.aggregation import UsageFilter
from app.services.budget_policy import BudgetStatus
from app.services.simulation_period import (
    DateRange,
    InvalidPeriodError,
    kst_today,
    resolve_period,
)


class UsageQueryError(ValueError):
    """조회 대상이나 조건을 사용자가 명확히 지정해야 한다."""


def _normalize(value: str) -> str:
    return "".join(value.casefold().split())


def _mentioned(options: list[UsageOption], text: str) -> list[UsageOption]:
    normalized = _normalize(text)
    return [
        item
        for item in options
        if any(
            len(alias) >= 2 and alias in normalized
            for alias in (
                _normalize(item.name),
                _normalize(re.split(r"[（(\[]", item.name, maxsplit=1)[0]),
            )
        )
    ]


def entity_id(
    options: list[UsageOption],
    explicit_id: int | None,
    name: str | None,
    inherited: int | None,
    label: str,
    text: str,
    previous: tuple[str, ...] = (),
) -> int | None:
    all_request = rf"(?:전체|모든)\s*{label}|{label}.*조건.*해제"
    if re.search(all_request, text):
        # 사용자가 명시적으로 해제한 조건은 모델이 이전 화면의 ID를 반복해도 되살리지 않는다.
        return None
    for index in range(len(previous) - 1, -1, -1):
        if re.search(all_request, previous[index]):
            previous = previous[index + 1 :]
            break
    mentioned = _mentioned(options, text)
    if len(mentioned) > 1:
        raise UsageQueryError(
            f"{label}을 여러 개 지정했어요. 전체 조회 또는 한 대상씩 이름을 지정해 주세요."
        )
    expected = mentioned[0].id if mentioned else inherited
    if expected is None and name not in {"전체", "all"}:
        for earlier in reversed(previous):
            found = _mentioned(options, earlier)
            if len(found) == 1:
                expected = found[0].id
                break
    if name is not None:
        normalized = _normalize(name)
        if normalized in {
            "전체",
            "all",
            "전체고객",
            "전체프로젝트",
            "전체서비스",
            "전체모델",
        }:
            if explicit_id is not None:
                raise UsageQueryError(
                    f"{label} 전체 조회와 특정 ID를 함께 지정할 수 없어요."
                )
            if inherited is not None and not re.search(
                r"전체|모든|\ball\b|조건.*해제", text, re.IGNORECASE
            ):
                raise UsageQueryError(
                    f"선택한 {label} 조건을 해제할지 확인해 주세요. 전체 조회를 원하면 명시해 주세요."
                )
            return None
        exact = [item for item in options if _normalize(item.name) == normalized]
        matches = exact or [
            item
            for item in options
            if normalized and normalized in _normalize(item.name)
        ]
        if len(matches) != 1:
            choices = ", ".join(item.name for item in matches[:TOOL_PAGE_SIZE])
            raise UsageQueryError(
                f"{label} 이름을 하나로 확인할 수 없어요. "
                + (
                    f"{choices} 중 정확한 이름을 지정해 주세요."
                    if choices
                    else "등록된 이름을 확인해 주세요."
                )
            )
        found = matches[0].id
        if explicit_id is not None and found != explicit_id:
            raise UsageQueryError(
                f"{label} 이름과 ID가 서로 달라요. 대상을 다시 확인해 주세요."
            )
        if expected is not None and found != expected:
            raise UsageQueryError(
                f"요청하거나 화면에서 선택한 {label}과 조회 대상이 달라요. 대상을 명확히 지정해 주세요."
            )
        if (
            expected is None
            and normalized not in _normalize(text)
            and not any(normalized in _normalize(earlier) for earlier in previous)
        ):
            raise UsageQueryError(
                f"요청에서 {label} 이름을 확인하지 못했어요. 원하는 이름을 직접 지정해 주세요."
            )
        return found
    if explicit_id is not None and expected is not None and explicit_id != expected:
        raise UsageQueryError(f"요청하거나 화면에서 선택한 {label}과 조회 ID가 달라요.")
    if (
        explicit_id is not None
        and expected is None
        and not re.search(rf"(?<!\d){explicit_id}(?:번|(?=\s|$))", text)
    ):
        raise UsageQueryError(
            f"조회할 {label} ID의 근거를 확인하지 못했어요. 이름을 직접 지정해 주세요."
        )
    candidate = explicit_id if explicit_id is not None else expected
    if candidate is not None and not any(item.id == candidate for item in options):
        raise UsageQueryError(
            f"조회할 {label}을 확인할 수 없어요. 등록된 대상을 다시 선택해 주세요."
        )
    return candidate


def usage_period(
    query: CustomerUsageToolQuery | InternalUsageToolQuery,
    context: AssistantPageContext | None,
    now: datetime,
    text: str,
    *,
    internal: bool,
) -> DateRange:
    today = kst_today(now)
    try:
        # 모델 인자는 먼저 검증하되, 사용자가 말하지 않은 기간으로 조건을 바꾸지 않는다.
        resolve_period(query.start_date, query.end_date, today)
        if re.search(r"이번\s*달|이달", text):
            return DateRange(today.replace(day=1), today)
        if re.search(r"지난\s*달|저번\s*달", text):
            end = today.replace(day=1) - timedelta(days=1)
            return DateRange(end.replace(day=1), end)
        if re.search(r"오늘", text):
            return DateRange(today, today)
        if recent := re.search(r"최근\s*(\d+)\s*일", text):
            days = int(recent[1])
            if not 1 <= days <= 366:
                raise ValueError
            return resolve_period(today - timedelta(days=days - 1), today, today)
        explicit_dates = re.findall(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", text)
        if not explicit_dates:
            explicit_dates = re.findall(
                r"(?:(\d{4})\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일", text
            )
        if explicit_dates:
            dates = [
                date(int(year or today.year), int(month), int(day))
                for year, month, day in explicit_dates
            ]
            if len(dates) > 2 or any(not 2000 <= day.year <= 2100 for day in dates):
                raise ValueError
            return resolve_period(dates[0], dates[-1], today)
        if month := re.search(r"(?:(\d{4})\s*년\s*)?(\d{1,2})\s*월", text):
            year, number = int(month[1] or today.year), int(month[2])
            if not 2000 <= year <= 2100:
                raise ValueError
            return DateRange(
                date(year, number, 1), date(year, number, monthrange(year, number)[1])
            )
        if context and context.start_date:
            return DateRange(context.start_date, context.end_date)
        return (
            DateRange(today.replace(day=1), today)
            if internal
            else resolve_period(None, None, today)
        )
    except (ValueError, InvalidPeriodError) as error:
        raise UsageQueryError(
            "조회 기간은 유효한 시작일과 종료일로, 최대 366일 이내로 지정해 주세요. 예: 2026-10-01부터 2026-10-31까지."
        ) from error


class AssistantUsage:
    def __init__(
        self,
        session: AsyncSession,
        now: datetime,
        context: AssistantPageContext | None,
        request_text: str,
        previous: tuple[str, ...] = (),
    ) -> None:
        self.session = session
        self.now = now
        self.context = context
        self.text = request_text
        self.previous = previous

    def section(
        self, query: UsageToolOptions, context: AssistantPageContext | None
    ) -> str:
        if re.search(
            r"(?:최근|마지막|최신).*(?:호출|요청)|(?:호출|요청).*(?:최근|마지막|최신)",
            self.text,
        ):
            return "requests"
        if re.search(
            r"예산.*(?:초과|현황|미설정|주의|목록|사용률)|(?:초과|주의).*예산",
            self.text,
        ):
            return "budgets"
        if query.section != "screen":
            return query.section
        if re.search(r"추이|추세|일별|날짜별", self.text):
            return "trend"
        if re.search(r"예산|고객별", self.text):
            return "budgets"
        if re.search(r"호출\s*(?:내역|이력|목록)|API\s*(?:내역|이력)", self.text):
            return "requests"
        return context.section if context and context.section else "summary"

    def budget_status(
        self,
        query: UsageToolOptions,
        context: AssistantPageContext | None,
        section: str,
    ) -> BudgetStatus | None:
        explicit = next(
            (
                status
                for pattern, status in (
                    (r"예산.*초과|초과.*(?:고객|프로젝트|항목)", "OVER"),
                    (r"예산.*주의|주의.*예산", "WARNING"),
                    (r"예산.*미설정|예산.*없는", "UNSET"),
                    (r"예산.*정상", "NORMAL"),
                )
                if re.search(pattern, self.text)
            ),
            None,
        )
        if explicit and section != "budgets":
            raise UsageQueryError(
                "예산 상태 조건은 예산 목록에서 확인할 수 있어요. 예산 현황 조회로 요청해 주세요."
            )
        if explicit and query.budget_status and query.budget_status != explicit:
            raise UsageQueryError(
                "요청한 예산 상태와 조회 조건이 달라요. 다시 요청해 주세요."
            )
        if re.search(r"(?:전체|모든)\s*예산|예산\s*상태\s*조건.*해제", self.text):
            if query.budget_status:
                raise UsageQueryError(
                    "전체 예산 조회와 특정 상태를 함께 지정할 수 없어요."
                )
            return None
        return (
            BudgetStatus(explicit)
            if explicit
            else query.budget_status or (context.budget_status if context else None)
        )

    async def customer(
        self, query: CustomerUsageToolQuery
    ) -> tuple[dict[str, Any], AssistantSource]:
        context = (
            self.context
            if self.context and self.context.page == "customer_usage"
            else None
        )
        period = usage_period(query, context, self.now, self.text, internal=False)
        section = self.section(query, context)
        options = await aggregation.list_options(self.session)
        if section == "options":
            return self.options(options), AssistantSource(
                title="고객·서비스 목록",
                kind="customer_usage",
                page_context=AssistantPageContext(
                    page="customer_usage", start_date=period.start, end_date=period.end
                ),
            )
        customer = entity_id(
            options.customers,
            query.customer_id,
            query.customer_name,
            context.customer_id if context else None,
            "고객",
            self.text,
            self.previous,
        )
        service = entity_id(
            options.services,
            query.service_id,
            query.service_name,
            context.service_id if context else None,
            "서비스",
            self.text,
            self.previous,
        )
        model = entity_id(
            options.models,
            query.model_id,
            query.model_name,
            context.model_id if context else None,
            "모델",
            self.text,
            self.previous,
        )
        if customer is None and re.search(r"(?:이|해당|선택한)\s*고객", self.text):
            raise UsageQueryError(
                "선택한 고객을 확인할 수 없어요. 고객을 선택하거나 이름을 지정해 주세요."
            )
        budget_status = self.budget_status(query, context, section)
        scope = AssistantPageContext(
            page="customer_usage",
            start_date=period.start,
            end_date=period.end,
            customer_id=customer,
            service_id=service,
            model_id=model,
            section=section,
            budget_status=budget_status if section == "budgets" else None,
        )
        usage_filter = UsageFilter(period, customer, service, model)
        sort = None
        if section == "requests":
            sort = {"cost": RequestRowSort.COST, "tokens": RequestRowSort.TOKENS}.get(
                query.sort, RequestRowSort.REQUESTED_AT
            )
            data = await aggregation.list_requests(
                self.session,
                usage_filter,
                RequestRowsQuery(
                    sort=sort,
                    order=query.order,
                    page=query.page,
                    page_size=TOOL_PAGE_SIZE,
                ),
            )
        elif section == "budgets":
            sort = {
                "cost": CustomerRowSort.CONFIRMED,
                "status": CustomerRowSort.STATUS,
            }.get(query.sort, CustomerRowSort.USAGE)
            data = await aggregation.list_customer_rows(
                self.session,
                usage_filter,
                CustomerRowsQuery(
                    sort=sort,
                    order=query.order,
                    page=query.page,
                    page_size=TOOL_PAGE_SIZE,
                    budget_status=budget_status,
                ),
            )
        elif section == "trend":
            data = await aggregation.daily_trend(self.session, usage_filter)
        else:
            data = await aggregation.summarize(self.session, usage_filter)
        entities = self.entity_names(
            (
                ("customer", options.customers, customer),
                ("service", options.services, service),
                ("model", options.models, model),
            )
        )
        title = {
            "requests": "고객 호출 내역",
            "budgets": "고객 예산 현황",
            "trend": "고객 사용량 추이",
        }.get(section, "고객 사용 현황")
        return self.result(data, scope, query, entities), AssistantSource(
            title=title,
            kind="customer_usage",
            page_context=scope,
            page_number=query.page
            if section in {"requests", "budgets", "trend"}
            else None,
            sort_key=sort,
            page_size=TOOL_PAGE_SIZE
            if section in {"requests", "budgets", "trend"}
            else None,
            sort_order=query.order if sort else None,
        )

    async def internal(
        self, query: InternalUsageToolQuery
    ) -> tuple[dict[str, Any], AssistantSource]:
        context = (
            self.context
            if self.context and self.context.page == "internal_budget"
            else None
        )
        period = usage_period(query, context, self.now, self.text, internal=True)
        section = self.section(query, context)
        options = await internal_requests.list_options(self.session)
        if section == "options":
            return self.options(options), AssistantSource(
                title="내부 프로젝트 목록",
                kind="internal_usage",
                page_context=AssistantPageContext(
                    page="internal_budget", start_date=period.start, end_date=period.end
                ),
            )
        project = entity_id(
            options.projects,
            query.project_id,
            query.project_name,
            context.project_id if context else None,
            "프로젝트",
            self.text,
            self.previous,
        )
        model = entity_id(
            options.models,
            query.model_id,
            query.model_name,
            context.model_id if context else None,
            "모델",
            self.text,
            self.previous,
        )
        if project is None and re.search(r"(?:이|해당|선택한)\s*프로젝트", self.text):
            raise UsageQueryError(
                "선택한 프로젝트를 확인할 수 없어요. 프로젝트를 선택하거나 이름을 지정해 주세요."
            )
        budget_status = self.budget_status(query, context, section)
        scope = AssistantPageContext(
            page="internal_budget",
            start_date=period.start,
            end_date=period.end,
            project_id=project,
            model_id=model,
            section=section,
            budget_status=budget_status if section == "budgets" else None,
        )
        sort = None
        if section == "requests":
            sort = {"cost": "cost", "tokens": "tokens"}.get(query.sort, "requestedAt")
            data = await internal_requests.list_requests(
                self.session,
                period,
                InternalRequestsQuery(
                    project_id=project,
                    model_id=model,
                    sort=sort,
                    order=query.order,
                    page=query.page,
                    page_size=TOOL_PAGE_SIZE,
                ),
            )
        elif section == "budgets":
            sort = {"cost": ProjectRowSort.USED, "status": ProjectRowSort.STATUS}.get(
                query.sort, ProjectRowSort.USAGE
            )
            data = await project_budgets.list_project_budgets(
                self.session,
                ProjectRowsQuery(
                    month=period.end.replace(day=1),
                    project_id=project,
                    model_id=model,
                    sort=sort,
                    order=query.order,
                    page=query.page,
                    page_size=TOOL_PAGE_SIZE,
                    budget_status=budget_status,
                ),
            )
        elif section == "trend":
            data = await internal_usage.daily_trend(
                self.session, period, project, model
            )
        else:
            data = await internal_usage.summarize(self.session, period, project, model)
        entities = self.entity_names(
            (("project", options.projects, project), ("model", options.models, model))
        )
        title = {
            "requests": "내부 호출 내역",
            "budgets": "내부 예산 현황",
            "trend": "내부 사용량 추이",
        }.get(section, "내부 사용량·예산")
        return self.result(data, scope, query, entities), AssistantSource(
            title=title,
            kind="internal_usage",
            page_context=scope,
            page_number=query.page
            if section in {"requests", "budgets", "trend"}
            else None,
            sort_key=sort,
            page_size=TOOL_PAGE_SIZE
            if section in {"requests", "budgets", "trend"}
            else None,
            sort_order=query.order if sort else None,
        )

    @staticmethod
    def entity_names(
        groups: tuple[tuple[str, list[UsageOption], int | None], ...],
    ) -> dict[str, str]:
        return {
            name: next((item.name for item in options if item.id == selected), "전체")
            for name, options, selected in groups
        }

    @staticmethod
    def options(options: BaseModel) -> dict[str, Any]:
        values = options.model_dump(mode="json")
        return {
            "section": "options",
            "data": {
                name: {"items": rows[:TOOL_PAGE_SIZE], "total": len(rows)}
                for name, rows in values.items()
            },
        }

    @staticmethod
    def result(
        data: BaseModel,
        scope: AssistantPageContext,
        query: UsageToolOptions,
        entities: dict[str, str],
    ) -> dict[str, Any]:
        values = data.model_dump(mode="json")
        if scope.section == "trend":
            rows = list(reversed(values["items"]))
            offset = (query.page - 1) * TOOL_PAGE_SIZE
            values = {
                "items": rows[offset : offset + TOOL_PAGE_SIZE],
                "total": len(rows),
                "page": query.page,
                "page_size": TOOL_PAGE_SIZE,
            }
        return {
            "scope": scope.page,
            "conditions": scope.model_dump(mode="json", exclude_none=True),
            "section": scope.section,
            "matched_entities": entities,
            "cost_caveat": (
                f"금액 미확인 {values['unknown_cost_count']}건은 합계에서 제외했다. 미확인 금액은 알 수 없으며 0달러가 아니다."
                if values.get("unknown_cost_count")
                else "미확인 호출은 금액이 없는 상태이며 0달러를 뜻하지 않는다."
            ),
            "data": values,
            "notes": [
                "금액은 USD 문자열이다. 미확인 비용은 금액 합계에서 제외되며 0이 아니다. 예산이 null이면 미설정이다.",
                "기간 안의 결과만 확인했다. 한 페이지는 최대 5개이며 페이지의 행을 전체 합계로 다시 계산하지 않는다.",
                "예산은 조회 종료일이 속한 달 전체 기준이다. 고객 예산은 서비스·모델 필터와 관계없이 고객 전체 사용액이며 고객×서비스 행에서 반복된다."
                if scope.page == "customer_usage"
                else "내부 비용은 고객 사용을 제외한다. 구독료는 기간에 걸친 각 달의 전체 청구액이며 모델 필터가 있으면 제외된다. 프로젝트 예산은 종료월 기준이다.",
            ],
        }
