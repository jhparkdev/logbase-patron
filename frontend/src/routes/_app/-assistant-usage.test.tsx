// @vitest-environment jsdom
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { components } from "../../shared/api/schema";
import { stubCustomerUsageApi } from "../../test/customerUsageApi";
import { stubInternalBudgetApi } from "../../test/internalBudgetApi";
import { renderAt } from "../../test/renderAt";

beforeEach(() => {
  window.scrollTo = vi.fn();
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});
afterEach(() => vi.unstubAllGlobals());
const reply = (body: unknown) =>
  new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });

function setup(sources: components["schemas"]["AssistantSource"][] = []) {
  const customer = stubCustomerUsageApi();
  const customerFetch = fetch;
  const internal = stubInternalBudgetApi();
  const internalFetch = fetch;
  const bodies: components["schemas"]["AssistantChatRequest"][] = [];
  vi.stubGlobal("fetch", async (request: Request) => {
    const path = new URL(request.url).pathname;
    if (path.startsWith("/api/usage/customers")) return customerFetch(request);
    if (
      path.startsWith("/api/usage/internal") ||
      path.startsWith("/api/subscriptions")
    )
      return internalFetch(request);
    if (path === "/api/auth/me")
      return reply({
        user_id: 1,
        user_code: "U-1",
        name: "테스터",
        email: "test@example.test",
      });
    if (path === "/api/assistant/status")
      return reply({ enabled: true, model: "qwen3.5:4b" });
    if (path === "/api/assistant/chat") {
      bodies.push(await request.json());
      return reply({ message: "조회 결과를 확인했어요.", sources });
    }
    return reply({ items: [], total: 0, page: 1, page_size: 10 });
  });
  return { customer, internal, bodies };
}

async function open() {
  fireEvent.click(
    await screen.findByRole("button", { name: "AI 도우미 열기" }),
  );
  await waitFor(() =>
    expect(
      (screen.getByRole("button", { name: "보내기" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false),
  );
}
async function send(bodies: unknown[], count: number) {
  fireEvent.change(screen.getByLabelText("질문 또는 설정 요청"), {
    target: { value: "현재 조건의 비용을 정리해줘" },
  });
  fireEvent.click(screen.getByRole("button", { name: "보내기" }));
  await waitFor(() => expect(bodies).toHaveLength(count));
  await waitFor(() =>
    expect(
      (screen.getByRole("button", { name: "보내기" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false),
  );
}

test("only applied filters are sent and applying new dates updates the next request", async () => {
  const { bodies } = setup();
  const router = renderAt(
    '/customer-usage?from=2026-10-01&to=2026-10-31&customer=1&service=10&model=20&view="requests"',
  );
  await open();
  fireEvent.change(screen.getByLabelText("시작일"), {
    target: { value: "2026-10-10" },
  });
  await send(bodies, 1);
  expect(bodies[0].page_context).toMatchObject({
    page: "customer_usage",
    start_date: "2026-10-01",
    end_date: "2026-10-31",
    customer_id: 1,
    service_id: 10,
    model_id: 20,
  });
  fireEvent.click(screen.getByRole("button", { name: /^조회$/ }));
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({ from: "2026-10-10" }),
  );
  await send(bodies, 2);
  expect(bodies[1].page_context?.start_date).toBe("2026-10-10");
});

test("navigation changes scope without carrying customer IDs into internal queries", async () => {
  const { bodies } = setup();
  const router = renderAt(
    '/customer-usage?from=2026-10-01&to=2026-10-31&customer=1&view="requests"',
  );
  await open();
  await send(bodies, 1);
  await act(async () => {
    await router.navigate({
      to: "/internal-budget",
      search: {
        from: "2026-09-01",
        to: "2026-09-30",
        project: 2,
        view: "requests",
      },
    });
  });
  await send(bodies, 2);
  expect(bodies[1].page_context).toMatchObject({
    page: "internal_budget",
    start_date: "2026-09-01",
    project_id: 2,
  });
  expect(bodies[1].page_context?.customer_id).toBeUndefined();
});

test("an internal budget source opens matching filters and the budget condition can be cleared", async () => {
  const { internal, bodies } = setup([
    {
      title: "내부 예산 현황",
      kind: "internal_usage",
      page_context: {
        page: "internal_budget",
        start_date: "2026-10-01",
        end_date: "2026-10-31",
        project_id: 1,
        section: "budgets",
        budget_status: "OVER",
      },
    },
  ]);
  const router = renderAt(
    '/customer-usage?from=2026-10-01&to=2026-10-31&view="requests"',
  );
  await open();
  await send(bodies, 1);
  fireEvent.click(
    await screen.findByRole("link", {
      name: "내부 예산 현황 · 2026-10-01 ~ 2026-10-31",
    }),
  );
  await screen.findByText("예산 목록 조건");
  expect(router.state.location.pathname).toBe("/internal-budget");
  expect(router.state.location.search).toMatchObject({
    project: 1,
    view: "projects",
    budgetStatus: "OVER",
  });
  await waitFor(() =>
    expect(
      internal.requests.some(
        ({ url }) =>
          url.pathname.endsWith("/projects") &&
          url.searchParams.get("budget_status") === "OVER",
      ),
    ).toBe(true),
  );
  fireEvent.click(screen.getByRole("button", { name: "예산 상태 조건 해제" }));
  await waitFor(() =>
    expect(router.state.location.search.budgetStatus).toBeUndefined(),
  );
});
