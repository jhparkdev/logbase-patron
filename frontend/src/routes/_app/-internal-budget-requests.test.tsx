// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { stubInternalBudgetApi } from "../../test/internalBudgetApi";
import { renderAt, routeMatch } from "../../test/renderAt";

const ROUTE_ID = "/_app/internal-budget";
const OCTOBER = "/internal-budget?from=2026-10-01&to=2026-10-31";
const TITLE = "상세 API 사용 이력";

beforeEach(() => {
  stubInternalBudgetApi();
});

afterEach(() => vi.restoreAllMocks());

function requestUrls(requests: { url: URL }[]) {
  return requests
    .map(({ url }) => url)
    .filter((url) => url.pathname.endsWith("/requests"));
}

test("이력은 KST 시각과 호출 출처를 보여 주고, 미확인 비용과 모르는 토큰 수를 0으로 보여 주지 않는다", async () => {
  renderAt(OCTOBER);

  const table = await screen.findByRole("table", { name: TITLE });
  expect(within(table).getByText("2026-10-31 14:32:21")).toBeTruthy();
  expect(within(table).getByText("2026-10-31 00:00:00")).toBeTruthy();
  expect(
    within(table).getByRole("link", { name: "사내 챗봇 구축" }),
  ).toBeTruthy();
  expect(within(table).getAllByText("미분류")).toHaveLength(2);
  expect(within(table).getByText("125,320")).toBeTruthy();
  expect(within(table).getByText("–")).toBeTruthy();
  expect(within(table).getByText("0.0200")).toBeTruthy();
  expect(within(table).getByText(/≈\s0\.0800/)).toBeTruthy();
  expect(within(table).getByText("미확인")).toBeTruthy();
  expect(within(table).queryByText("0.0000")).toBeNull();
  expect(within(table).getByText("내부 개발")).toBeTruthy();
  expect(within(table).getByText("시뮬레이션")).toBeTruthy();
  expect(within(table).getByText("연결 테스트")).toBeTruthy();
  expect(within(table).queryByText("SYSTEM_TEST")).toBeNull();
  expect(within(table).getByText("Timeout")).toBeTruthy();
});

test("요약 화면은 조회 기간으로 최근 이력 미리보기를 요청하고, 정렬을 고르지 않으면 보내지 않는다", async () => {
  const { requests } = stubInternalBudgetApi();
  renderAt(OCTOBER);

  await screen.findByRole("table", { name: TITLE });
  const [url] = requestUrls(requests);
  expect(url.searchParams.get("start_date")).toBe("2026-10-01");
  expect(url.searchParams.get("end_date")).toBe("2026-10-31");
  expect(url.searchParams.get("preview")).toBe("true");
  expect(url.searchParams.has("sort")).toBe(false);
  expect(url.searchParams.has("page")).toBe(false);
});

test("머리글을 누르면 그 칸으로 정렬해 다시 요청한다. 구분(호출 출처) 칸도 정렬한다", async () => {
  const { requests } = stubInternalBudgetApi();
  const router = renderAt(OCTOBER);

  const table = await screen.findByRole("table", { name: TITLE });
  fireEvent.click(within(table).getByRole("button", { name: /비용/ }));
  await waitFor(() =>
    expect(
      requestUrls(requests).some(
        (url) =>
          url.searchParams.get("sort") === "cost" &&
          url.searchParams.get("order") === "asc",
      ),
    ).toBe(true),
  );

  fireEvent.click(within(table).getByRole("button", { name: /구분/ }));
  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toMatchObject({
      requestsSort: "origin",
      requestsOrder: "asc",
    }),
  );
  await waitFor(() =>
    expect(
      requestUrls(requests).some(
        (url) => url.searchParams.get("sort") === "origin",
      ),
    ).toBe(true),
  );
});

test("전체보기는 페이지를 나눠 요청하고, 페이지를 누르면 주소에 남긴다", async () => {
  const { requests } = stubInternalBudgetApi();
  const router = renderAt(`${OCTOBER}&view=requests`);

  fireEvent.click(await screen.findByRole("button", { name: "2" }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search.page).toBe(2),
  );
  await waitFor(() =>
    expect(
      requestUrls(requests).some(
        (url) =>
          url.searchParams.get("preview") === "false" &&
          url.searchParams.get("page") === "2" &&
          url.searchParams.get("page_size") === "10",
      ),
    ).toBe(true),
  );
});

test("이력이 없으면 조건을 바꿔 보라고 알린다", async () => {
  stubInternalBudgetApi({
    requests: {
      status: 200,
      body: { items: [], total: 0, page: 1, page_size: 10 },
    },
  });
  renderAt(`${OCTOBER}&view=requests`);

  expect(
    await screen.findByText("이 조건에는 API 사용 내역이 없어요"),
  ).toBeTruthy();
});

test("이력을 불러오지 못하면 그 블록에만 알리고 다시 시도할 수 있다", async () => {
  const { replies } = stubInternalBudgetApi({
    requests: { status: 500, body: {} },
  });
  // 오류 경계가 받는 오류를 React가 출력한다. 예상한 동작이라 테스트 출력에 남기지 않는다.
  vi.spyOn(console, "error").mockImplementation(() => {});
  renderAt(OCTOBER);

  expect(
    await screen.findByText("상세 API 사용 이력을 불러오지 못했어요"),
  ).toBeTruthy();
  expect(
    await screen.findByRole("table", { name: "프로젝트별 예산 현황" }),
  ).toBeTruthy();

  delete replies.requests;
  fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));

  expect(await screen.findByRole("table", { name: TITLE })).toBeTruthy();
});
