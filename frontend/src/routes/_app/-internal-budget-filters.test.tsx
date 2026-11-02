// @vitest-environment jsdom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { SUMMARY, stubInternalBudgetApi } from "../../test/internalBudgetApi";
import { renderAt, routeMatch } from "../../test/renderAt";

const ROUTE_ID = "/_app/internal-budget";
const OCTOBER = "/internal-budget?from=2026-10-01&to=2026-10-31";

beforeEach(() => {
  stubInternalBudgetApi();
});

afterEach(() => vi.restoreAllMocks());

async function loadedSelect(label: string) {
  const select = await screen.findByLabelText<HTMLSelectElement>(label);
  await waitFor(() => expect(select.disabled).toBe(false));
  return select;
}

function urlOf(requests: { url: URL }[], pathname: string) {
  return requests
    .map(({ url }) => url)
    .filter((url) => url.pathname === pathname);
}

test("프로젝트·모델 선택 상자는 선택지 API로 채우고, 주소의 조건을 보여 준다", async () => {
  renderAt(`${OCTOBER}&project=1`);

  const project = await loadedSelect("프로젝트");
  expect(project.value).toBe("1");
  expect(screen.getByRole("option", { name: "사내 챗봇 구축" })).toBeTruthy();
  const model = await loadedSelect("모델");
  expect(model.value).toBe("");
  expect(screen.getByRole("option", { name: "openai/gpt-4o" })).toBeTruthy();
});

test("조건을 고르고 조회하면 주소에 남고 1페이지로 돌아가며, 모든 블록이 그 조건으로 요청한다", async () => {
  const { requests } = stubInternalBudgetApi();
  const router = renderAt(`${OCTOBER}&view=projects&page=3`);

  fireEvent.change(await loadedSelect("프로젝트"), { target: { value: "1" } });
  fireEvent.change(await loadedSelect("모델"), { target: { value: "20" } });
  expect(routeMatch(router, ROUTE_ID)?.search.project).toBeUndefined();
  fireEvent.click(screen.getByRole("button", { name: "조회" }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      from: "2026-10-01",
      to: "2026-10-31",
      view: "projects",
      project: 1,
      model: 20,
    }),
  );
  await waitFor(() => {
    const filtered = urlOf(requests, "/api/usage/internal/projects").at(-1);
    expect(filtered?.searchParams.get("project_id")).toBe("1");
    expect(filtered?.searchParams.get("model_id")).toBe("20");
  });
});

test("요약 화면의 요약·이력은 프로젝트와 모델을, 구독료 표는 프로젝트만 조건으로 보낸다", async () => {
  const { requests } = stubInternalBudgetApi();
  renderAt(`${OCTOBER}&project=1&model=20`);

  await screen.findByRole("table", { name: "구독료 관리" });
  await screen.findByText("1,240.50");
  for (const pathname of [
    "/api/usage/internal/summary",
    "/api/usage/internal/requests",
  ]) {
    const [url] = urlOf(requests, pathname);
    expect(url.searchParams.get("project_id")).toBe("1");
    expect(url.searchParams.get("model_id")).toBe("20");
  }
  const [subscriptions] = urlOf(requests, "/api/subscriptions");
  expect(subscriptions.searchParams.get("project_id")).toBe("1");
  expect(subscriptions.searchParams.has("model_id")).toBe(false);
});

test("모델 조건으로 구독료를 뺀 요약은 카드에 그 사실을 알린다", async () => {
  stubInternalBudgetApi({
    summary: {
      status: 200,
      body: {
        ...SUMMARY,
        subscription_usd: "0",
        unknown_cost_count: 0,
        has_unknown: false,
        subscription_excluded: true,
      },
    },
  });
  renderAt(`${OCTOBER}&model=20`);

  expect(
    await screen.findByText("모델 조건에서는 구독료를 빼고 보여요"),
  ).toBeTruthy();
  expect(screen.getByText("API 비용만 (구독료 제외)")).toBeTruthy();
});

test("선택지를 불러오지 못해도 기간 조회는 할 수 있다", async () => {
  stubInternalBudgetApi({ options: { status: 500, body: {} } });
  const router = renderAt(OCTOBER);

  const project = await screen.findByLabelText<HTMLSelectElement>("프로젝트");
  expect(project.disabled).toBe(true);
  fireEvent.change(await screen.findByLabelText("종료일"), {
    target: { value: "2026-10-20" },
  });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search.to).toBe("2026-10-20"),
  );
});
