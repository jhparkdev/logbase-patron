// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { stubInternalBudgetApi } from "../../test/internalBudgetApi";
import { renderAt, routeMatch } from "../../test/renderAt";

const ROUTE_ID = "/_app/internal-budget";
const OCTOBER = "/internal-budget?from=2026-10-01&to=2026-10-31";
const TITLE = "구독료 관리";
const MEMBER_TITLE = "구성원별 Command Code 사용량";
const EMPTY_PAGE = { items: [], total: 0, page: 1, page_size: 10 };

beforeEach(() => {
  stubInternalBudgetApi();
});

afterEach(() => vi.restoreAllMocks());

function subscriptionUrls(requests: { url: URL }[]) {
  return requests
    .map(({ url }) => url)
    .filter((url) => url.pathname === "/api/subscriptions");
}

test("구독료 표는 도구명, 적용 월, 금액, 귀속 프로젝트, 상태를 보여 주고 프로젝트가 없으면 미배분이다", async () => {
  renderAt(OCTOBER);

  const table = await screen.findByRole("table", { name: TITLE });
  expect(within(table).getByText("Command Code")).toBeTruthy();
  expect(within(table).getByText("2026-10")).toBeTruthy();
  expect(within(table).getByText("100.00")).toBeTruthy();
  expect(within(table).getByText("사내 챗봇 구축")).toBeTruthy();
  expect(within(table).getByText("사용 중")).toBeTruthy();
  expect(within(table).getByText("Notion AI")).toBeTruthy();
  expect(within(table).getByText("미배분")).toBeTruthy();
  expect(within(table).getByText("해지")).toBeTruthy();
});

test("요약 화면은 조회 기간으로 미리보기를 요청하고, 정렬을 고르지 않으면 보내지 않는다", async () => {
  const { requests } = stubInternalBudgetApi();
  renderAt(OCTOBER);

  await screen.findByRole("table", { name: TITLE });
  const [url] = subscriptionUrls(requests);
  expect(url.searchParams.get("start_date")).toBe("2026-10-01");
  expect(url.searchParams.get("end_date")).toBe("2026-10-31");
  expect(url.searchParams.get("preview")).toBe("true");
  expect(url.searchParams.has("sort")).toBe(false);
  expect(url.searchParams.has("page")).toBe(false);
});

test("머리글을 누르면 그 정렬이 주소에 남고 다시 요청한다", async () => {
  const { requests } = stubInternalBudgetApi();
  const router = renderAt(OCTOBER);

  const table = await screen.findByRole("table", { name: TITLE });
  fireEvent.click(within(table).getByRole("button", { name: /금액/ }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toMatchObject({
      subscriptionsSort: "amount",
      subscriptionsOrder: "asc",
    }),
  );
  await waitFor(() =>
    expect(
      subscriptionUrls(requests).some(
        (url) =>
          url.searchParams.get("sort") === "amount" &&
          url.searchParams.get("order") === "asc",
      ),
    ).toBe(true),
  );
});

test("전체보기는 페이지를 나눠 요청하고, 구성원 사용량은 보여 주지 않는다", async () => {
  const { requests } = stubInternalBudgetApi();
  const router = renderAt(`${OCTOBER}&view=subscriptions`);

  await screen.findByRole("table", { name: TITLE });
  expect(screen.queryByRole("heading", { name: MEMBER_TITLE })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "2" }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search.page).toBe(2),
  );
  await waitFor(() =>
    expect(
      subscriptionUrls(requests).some(
        (url) =>
          url.searchParams.get("preview") === "false" &&
          url.searchParams.get("page") === "2" &&
          url.searchParams.get("page_size") === "10",
      ),
    ).toBe(true),
  );
});

test("요약 화면에서는 구독료 표 아래에 구성원 사용량을 함께 보여 준다", async () => {
  renderAt(OCTOBER);

  await screen.findByRole("table", { name: TITLE });
  expect(screen.getByRole("heading", { name: MEMBER_TITLE })).toBeTruthy();
});

test("구독료가 없으면 등록하라고 알린다", async () => {
  stubInternalBudgetApi({ subscriptions: { status: 200, body: EMPTY_PAGE } });
  renderAt(OCTOBER);

  expect(await screen.findByText("등록된 구독료가 없어요")).toBeTruthy();
});

test("구독료 표를 불러오지 못하면 그 블록에만 알리고 다시 시도할 수 있다", async () => {
  const { replies } = stubInternalBudgetApi({
    subscriptions: { status: 500, body: {} },
  });
  // 오류 경계가 받는 오류를 React가 출력한다. 예상한 동작이라 테스트 출력에 남기지 않는다.
  vi.spyOn(console, "error").mockImplementation(() => {});
  renderAt(OCTOBER);

  expect(
    await screen.findByText("구독료 관리를 불러오지 못했어요"),
  ).toBeTruthy();
  expect(await screen.findByText("1,240.50")).toBeTruthy();

  delete replies.subscriptions;
  fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));

  expect(await screen.findByRole("table", { name: TITLE })).toBeTruthy();
});
