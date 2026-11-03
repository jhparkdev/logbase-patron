// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";
import { stubInternalBudgetApi } from "../../test/internalBudgetApi";
import { renderAt, routeMatch } from "../../test/renderAt";

const ROUTE_ID = "/_app/internal-budget";
const OCTOBER = "/internal-budget?from=2026-10-01&to=2026-10-31";
const TITLE = "프로젝트별 예산 현황";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
});

beforeEach(() => {
  stubInternalBudgetApi();
});

afterEach(() => vi.restoreAllMocks());

function projectRequests(requests: { url: URL }[]) {
  return requests
    .map(({ url }) => url)
    .filter((url) => url.pathname.endsWith("/projects"));
}

test("프로젝트 표는 예산 상태와 미반영 건수를 보여 주고 예산이 없으면 0%가 아니라 미설정이다", async () => {
  renderAt(OCTOBER);

  const table = await screen.findByRole("table", { name: TITLE });
  expect(
    within(table).getByRole("link", { name: "사내 챗봇 구축" }),
  ).toBeTruthy();
  expect(within(table).getByText("10.00")).toBeTruthy();
  expect(within(table).getByText("12.10")).toBeTruthy();
  expect(within(table).getByText("121%")).toBeTruthy();
  expect(within(table).getByText("초과")).toBeTruthy();
  expect(within(table).getByText("미확인 2건 미반영")).toBeTruthy();
  expect(within(table).getAllByText("미설정")).toHaveLength(2);
  expect(within(table).getByText("예산을 정하면 사용률이 보여요")).toBeTruthy();
  expect(within(table).queryByText("0%")).toBeNull();
});

test("요약 화면은 조회 기간 종료일의 달로 미리보기를 요청하고, 정렬을 고르지 않으면 서버 기본 정렬을 따른다", async () => {
  const { requests } = stubInternalBudgetApi();
  renderAt("/internal-budget?from=2026-09-01&to=2026-10-15");

  await screen.findByRole("table", { name: TITLE });
  const [url] = projectRequests(requests);
  expect(url.searchParams.get("month")).toBe("2026-10");
  expect(url.searchParams.get("preview")).toBe("true");
  expect(url.searchParams.has("sort")).toBe(false);
  expect(url.searchParams.has("page")).toBe(false);
});

test("머리글을 누르면 그 정렬로 다시 요청한다", async () => {
  const { requests } = stubInternalBudgetApi();
  renderAt(OCTOBER);

  const table = await screen.findByRole("table", { name: TITLE });
  fireEvent.click(within(table).getByRole("button", { name: /월 예산/ }));

  await waitFor(() =>
    expect(
      projectRequests(requests).some(
        (url) =>
          url.searchParams.get("sort") === "budget" &&
          url.searchParams.get("order") === "asc",
      ),
    ).toBe(true),
  );
});

test("전체보기는 페이지를 나눠 요청하고, 페이지를 누르면 주소에 남긴다", async () => {
  const { requests } = stubInternalBudgetApi();
  const router = renderAt(`${OCTOBER}&view=projects`);

  fireEvent.click(await screen.findByRole("button", { name: "2" }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search.page).toBe(2),
  );
  await waitFor(() =>
    expect(
      projectRequests(requests).some(
        (url) =>
          url.searchParams.get("preview") === "false" &&
          url.searchParams.get("page") === "2" &&
          url.searchParams.get("page_size") === "10",
      ),
    ).toBe(true),
  );
});

test("프로젝트명을 누르면 그 프로젝트의 상세 패널을 연다", async () => {
  const router = renderAt(OCTOBER);

  const table = await screen.findByRole("table", { name: TITLE });
  fireEvent.click(within(table).getByRole("link", { name: "사내 챗봇 구축" }));

  await screen.findByRole("dialog", { name: "사내 챗봇 구축" });
  expect(routeMatch(router, ROUTE_ID)?.search.detail).toBe(1);
});

test("프로젝트가 없으면 등록된 프로젝트가 없다고 알린다", async () => {
  stubInternalBudgetApi({
    projects: {
      status: 200,
      body: { items: [], total: 0, page: 1, page_size: 10 },
    },
  });
  renderAt(OCTOBER);

  expect(await screen.findByText("등록된 프로젝트가 없어요")).toBeTruthy();
});

test("프로젝트 표를 불러오지 못하면 그 블록에만 알리고 다시 시도할 수 있다", async () => {
  const { replies } = stubInternalBudgetApi({
    projects: { status: 500, body: {} },
  });
  // 오류 경계가 받는 오류를 React가 출력한다. 예상한 동작이라 테스트 출력에 남기지 않는다.
  vi.spyOn(console, "error").mockImplementation(() => {});
  renderAt(OCTOBER);

  expect(
    await screen.findByText("프로젝트별 예산 현황을 불러오지 못했어요"),
  ).toBeTruthy();
  expect(await screen.findByText("1,240.50")).toBeTruthy();

  delete replies.projects;
  fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));

  expect(await screen.findByRole("table", { name: TITLE })).toBeTruthy();
});
