import { z } from "zod";
import type { components } from "../../../shared/api/schema";
import { formatKstDateTime } from "../../../shared/lib/format";
import { PAGE_SIZE } from "../../../shared/lib/pagination";

export type AssistantSource = components["schemas"]["AssistantSource"];

export function assistantSourceLink(source: AssistantSource, now = new Date()) {
  if (source.kind === "models")
    return { to: "/models" as const, label: source.title, title: source.title };
  if (source.kind === "customer_usage" || source.kind === "internal_usage") {
    const internal = source.kind === "internal_usage";
    const context =
      source.page_context?.page ===
      (internal ? "internal_budget" : "customer_usage")
        ? source.page_context
        : undefined;
    const today = formatKstDateTime(now.toISOString()).slice(0, 10);
    const from =
      context?.start_date ??
      new Date(Date.parse(today) - 29 * 86400000).toISOString().slice(0, 10);
    const to = context?.end_date ?? today;
    const common = {
      from,
      to,
      model: context?.model_id ?? undefined,
      page:
        Math.floor(
          (((source.page_number ?? 1) - 1) * (source.page_size ?? PAGE_SIZE)) /
            PAGE_SIZE,
        ) + 1,
      budgetStatus: context?.budget_status ?? undefined,
    };
    const requestSort =
      source.sort_key === "requestedAt" ||
      source.sort_key === "cost" ||
      source.sort_key === "tokens"
        ? source.sort_key
        : undefined;
    const customerSort =
      source.sort_key === "confirmed" ||
      source.sort_key === "usage" ||
      source.sort_key === "status"
        ? source.sort_key
        : undefined;
    const projectSort =
      source.sort_key === "used" ||
      source.sort_key === "usage" ||
      source.sort_key === "status"
        ? source.sort_key
        : undefined;
    const label = `${source.title} · ${from} ~ ${to}`;
    const title = "답변에 사용한 조회 조건으로 이동";
    return internal
      ? {
          to: "/internal-budget" as const,
          label,
          title,
          search: {
            ...common,
            project: context?.project_id ?? undefined,
            view:
              context?.section === "requests"
                ? ("requests" as const)
                : context?.section === "budgets"
                  ? ("projects" as const)
                  : undefined,
            requestsSort: requestSort,
            requestsOrder: requestSort
              ? (source.sort_order ?? undefined)
              : undefined,
            projectsSort: projectSort,
            projectsOrder: projectSort
              ? (source.sort_order ?? undefined)
              : undefined,
          },
        }
      : {
          to: "/customer-usage" as const,
          label,
          title,
          search: {
            ...common,
            customer: context?.customer_id ?? undefined,
            service: context?.service_id ?? undefined,
            view:
              context?.section === "requests"
                ? ("requests" as const)
                : context?.section === "budgets"
                  ? ("customers" as const)
                  : undefined,
            requestsSort: requestSort,
            requestsOrder: requestSort
              ? (source.sort_order ?? undefined)
              : undefined,
            customersSort: customerSort,
            customersOrder: customerSort
              ? (source.sort_order ?? undefined)
              : undefined,
          },
        };
  }
  const parsed = z.guid().safeParse(source.simulation_id);
  const runId = parsed.success ? parsed.data : undefined;
  let requestedAt: string | undefined;
  if (runId && source.requested_at) {
    try {
      requestedAt = formatKstDateTime(source.requested_at);
    } catch {
      // 표시용 시각이 잘못되어도 확인된 실행의 상세 링크는 유지한다.
    }
  }
  const today = formatKstDateTime(now.toISOString()).slice(0, 10);
  const from = new Date(Date.parse(today) - 29 * 86400000)
    .toISOString()
    .slice(0, 10);
  return {
    to: "/simulation-history" as const,
    label: runId
      ? requestedAt
        ? `실행 상세 · ${requestedAt}`
        : source.title
      : "시뮬레이션 이력",
    title: runId
      ? `${requestedAt ? `${requestedAt} (한국시간) · ` : ""}${runId} 실행 상세`
      : source.title,
    search: {
      from: requestedAt?.slice(0, 10) ?? from,
      to: requestedAt?.slice(0, 10) ?? today,
      scenario: "",
      model: "",
      simulationId: runId ?? "",
      status: "all" as const,
      sort: "requestedAt" as const,
      direction: "desc" as const,
      page: 1,
      selected: runId,
      detail: !!runId,
    },
  };
}
