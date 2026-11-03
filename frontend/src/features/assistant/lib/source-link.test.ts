import { expect, test } from "vitest";
import { assistantSourceLink } from "./source-link";

const runId = "00000000-0000-4000-8000-000000000001";

test.each([
  [2, 1],
  [3, 2],
  [4, 2],
])(
  "tool page %i opens the screen page containing its five rows",
  (page_number, expected) => {
    const link = assistantSourceLink({
      title: "고객 호출",
      kind: "customer_usage",
      page_number,
      page_size: 5,
      sort_key: "cost",
      sort_order: "desc",
      page_context: { page: "customer_usage", section: "requests" },
    });
    expect(link.search).toMatchObject({
      page: expected,
      requestsSort: "cost",
      requestsOrder: "desc",
    });
  },
);

test("customer and internal evidence links retain the actual queried scope", () => {
  const customer = assistantSourceLink({
    title: "고객 사용 현황",
    kind: "customer_usage",
    page_context: {
      page: "customer_usage",
      start_date: "2026-10-01",
      end_date: "2026-10-31",
      customer_id: 2,
      service_id: 3,
      section: "requests",
    },
  });
  expect(customer.to).toBe("/customer-usage");
  expect(customer.search).toMatchObject({
    from: "2026-10-01",
    to: "2026-10-31",
    customer: 2,
    service: 3,
    view: "requests",
  });
  const internal = assistantSourceLink({
    title: "내부 예산",
    kind: "internal_usage",
    page_context: {
      page: "internal_budget",
      start_date: "2026-10-01",
      end_date: "2026-10-31",
      project_id: 4,
      section: "budgets",
      budget_status: "OVER",
    },
  });
  expect(internal.to).toBe("/internal-budget");
  expect(internal.search).toMatchObject({
    project: 4,
    view: "projects",
    budgetStatus: "OVER",
  });
});

test("a verified run links to the P05 modal and the run's Korean calendar date", () => {
  const link = assistantSourceLink({
    title: "실행 상세",
    kind: "simulation",
    simulation_id: runId,
    requested_at: "2025-12-31T15:30:00Z",
  });
  expect(link.to).toBe("/simulation-history");
  expect(link.label).toBe("실행 상세 · 2026-01-01 00:30:00");
  expect(link.search).toMatchObject({
    selected: runId,
    detail: true,
    simulationId: runId,
    from: "2026-01-01",
    to: "2026-01-01",
  });
});

test("legacy run links still open details without requiring a list row", () => {
  expect(
    assistantSourceLink({
      title: "시뮬레이션 결과",
      kind: "simulation",
      simulation_id: runId,
    }).search,
  ).toMatchObject({ selected: runId, detail: true });
});

test("general history or malformed IDs cannot open an arbitrary detail", () => {
  for (const simulation_id of [null, "invalid", "javascript:alert(1)"]) {
    const link = assistantSourceLink({
      title: "시뮬레이션 이력",
      kind: "history",
      simulation_id,
    });
    expect(link.search).toMatchObject({
      selected: undefined,
      detail: false,
      simulationId: "",
    });
  }
  expect(assistantSourceLink({ title: "등록 모델", kind: "models" }).to).toBe(
    "/models",
  );
});
