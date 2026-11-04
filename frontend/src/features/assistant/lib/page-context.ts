import { z } from "zod";
import type { components } from "../../../shared/api/schema";
import {
  budgetStatusBadge,
  budgetStatusSchema,
} from "../../../shared/lib/budget";
import {
  currentMonthPeriod,
  periodSchema,
  recentPeriod,
  wholeMonthPeriod,
} from "../../../shared/lib/period";

export type AssistantPageContext =
  components["schemas"]["AssistantPageContext"];

function id(value: unknown): number | undefined {
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string" && /^\d+$/.test(value)
        ? Number(value)
        : undefined;
  return parsed !== undefined && Number.isSafeInteger(parsed) && parsed > 0
    ? parsed
    : undefined;
}

function period(values: Record<string, unknown>, internal: boolean, now: Date) {
  try {
    const parsed = periodSchema.safeParse({ from: values.from, to: values.to });
    if (parsed.success) return parsed.data;
  } catch {
    /* 잘못된 외부 날짜는 화면의 기본 기간으로 복구한다. */
  }
  return internal ? currentMonthPeriod(now) : recentPeriod(now, 30);
}

export function assistantPageContext(
  path: string,
  search: unknown,
  now = new Date(),
): AssistantPageContext | undefined {
  const values =
    typeof search === "object" && search !== null
      ? (search as Record<string, unknown>)
      : {};
  if (path === "/customer-usage" || path === "/internal-budget") {
    const internal = path === "/internal-budget";
    const selected = id(values.detail);
    const range = selected
      ? wholeMonthPeriod(period(values, internal, now).to)
      : period(values, internal, now);
    if (selected)
      return internal
        ? {
            page: "internal_budget",
            start_date: range.from,
            end_date: range.to,
            project_id: selected,
            section: "budgets",
            detail: true,
          }
        : {
            page: "customer_usage",
            start_date: range.from,
            end_date: range.to,
            customer_id: selected,
            section: "budgets",
            detail: true,
          };
    const status = budgetStatusSchema.safeParse(values.budgetStatus);
    const common = {
      start_date: range.from,
      end_date: range.to,
      ...(id(values.model) ? { model_id: id(values.model) } : {}),
      ...(status.success ? { budget_status: status.data } : {}),
    };
    const section =
      values.view === "requests"
        ? "requests"
        : values.view === "customers" || values.view === "projects"
          ? "budgets"
          : "summary";
    return internal
      ? {
          page: "internal_budget",
          ...common,
          ...(id(values.project) ? { project_id: id(values.project) } : {}),
          section,
        }
      : {
          page: "customer_usage",
          ...common,
          ...(id(values.customer) ? { customer_id: id(values.customer) } : {}),
          ...(id(values.service) ? { service_id: id(values.service) } : {}),
          section,
        };
  }
  if (path === "/models")
    return {
      page: "models",
      ...(id(values.model) ? { model_id: id(values.model) } : {}),
    };
  if (path === "/simulator") {
    const run = z.guid().safeParse(values.run);
    return {
      page: "simulator",
      ...(run.success ? { simulation_id: run.data } : {}),
    };
  }
  if (path === "/simulation-history") {
    const range = period(values, false, now);
    const run = z.guid().safeParse(values.selected ?? values.simulationId);
    return {
      page: "simulation_history",
      start_date: range.from,
      end_date: range.to,
      ...(id(values.model) ? { model_id: id(values.model) } : {}),
      ...(run.success ? { simulation_id: run.data } : {}),
    };
  }
  return undefined;
}

export function pageContextLabel(context: AssistantPageContext): string {
  const page = {
    customer_usage: "고객 사용 현황",
    internal_budget: "내부 사용량·예산",
    models: "등록 모델",
    simulator: "시뮬레이터",
    simulation_history: "시뮬레이션 이력",
  }[context.page];
  const selected = context.detail
    ? "선택한 상세 대상"
    : context.customer_id
      ? "선택한 고객"
      : context.project_id
        ? "선택한 프로젝트"
        : context.simulation_id
          ? "선택한 실행"
          : undefined;
  const range =
    context.start_date && context.end_date
      ? `${context.start_date} ~ ${context.end_date}`
      : undefined;
  const status = context.budget_status
    ? `예산 ${budgetStatusBadge(context.budget_status).label}`
    : undefined;
  return [
    page,
    range,
    selected,
    context.service_id ? "서비스 조건 적용" : undefined,
    context.model_id ? "모델 조건 적용" : undefined,
    status,
  ]
    .filter(Boolean)
    .join(" · ");
}
