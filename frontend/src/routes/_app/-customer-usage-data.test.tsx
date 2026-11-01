// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";
import { stubCustomerUsageApi } from "../../test/customerUsageApi";
import { renderAt, routeMatch } from "../../test/renderAt";

const ROUTE_ID = "/_app/customer-usage";
const OCTOBER = "/customer-usage?from=2026-10-01&to=2026-10-31";
const NO_RESULT = "이 조건에는 API 호출 내역이 없어요";
const EMPTY_PAGE = { items: [], total: 0, page: 1, page_size: 10 };

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  // jsdom에는 크기 감시가 없어서 그래프 컨테이너가 쓸 빈 구현을 넣는다.
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});

beforeEach(() => {
  stubCustomerUsageApi();
});

afterEach(() => vi.restoreAllMocks());

function tableNamed(name: string) {
  return screen.findByRole("table", { name });
}

test("요약 카드는 서버 값을 보여 주고 미확인은 금액에 넣지 않았다고 알린다", async () => {
  renderAt(OCTOBER);

  expect(await screen.findByText("27,901")).toBeTruthy();
  expect(screen.getByText("147.00")).toBeTruthy();
  expect(screen.getByText(/≈\s47\.00/)).toBeTruthy();
  expect(screen.getByText("위 금액에 넣지 않았어요")).toBeTruthy();
  expect(screen.getAllByText(/이전 기간 대비/)).toHaveLength(2);
  expect(screen.queryByText(/전월 대비/)).toBeNull();
});

test("추이는 날짜별 값을 표로도 제공한다", async () => {
  renderAt(OCTOBER);

  const table = await tableNamed("사용량·비용 추이");
  expect(within(table).getByText("2026-10-01")).toBeTruthy();
  expect(within(table).getByText("1.50")).toBeTruthy();
});

test("고객 표는 예산 상태와 미분류, 미반영 건수를 구분해 보여 준다", async () => {
  renderAt(OCTOBER);

  const table = await tableNamed("고객별 사용 현황");
  expect(within(table).getByRole("link", { name: "A기업" })).toBeTruthy();
  expect(within(table).getByText("초과")).toBeTruthy();
  expect(within(table).getByText("121%")).toBeTruthy();
  expect(within(table).getByText("미확인 2건 미반영")).toBeTruthy();
  expect(within(table).getByText("미분류")).toBeTruthy();
  expect(within(table).getAllByText("미설정")).toHaveLength(2);
  expect(within(table).getByText("예산을 정하면 사용률이 보여요")).toBeTruthy();
  expect(within(table).queryByText("0%")).toBeNull();
});

test("호출 표는 비용 상태 칸 없이 미확인을 0으로 보여 주지 않는다", async () => {
  renderAt(OCTOBER);

  const table = await tableNamed("상세 API 호출 내역");
  expect(within(table).getAllByText("2026-10-31 14:32:21")).toHaveLength(2);
  expect(within(table).getByText("0.0200")).toBeTruthy();
  expect(within(table).getByText("상품 설명 생성")).toBeTruthy();
  expect(within(table).queryByText("PRODUCT_DESCRIPTION")).toBeNull();
  expect(within(table).getByText("미확인")).toBeTruthy();
  expect(within(table).getByText("Timeout")).toBeTruthy();
  expect(within(table).queryByText("0.0000")).toBeNull();
  expect(
    within(table).queryByRole("columnheader", { name: /비용 상태/ }),
  ).toBeNull();
});

test("요약 화면은 미리보기로 요청하고 기본 정렬은 주소에 남기지 않는다", async () => {
  const { requests } = stubCustomerUsageApi();
  const router = renderAt(OCTOBER);

  await tableNamed("고객별 사용 현황");

  const rows = requests.find((r) => r.url.pathname.endsWith("/rows"));
  expect(rows?.url.searchParams.get("preview")).toBe("true");
  expect(rows?.url.searchParams.get("sort")).toBe("confirmed");
  expect(rows?.url.searchParams.get("start_date")).toBe("2026-10-01");
  expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
    from: "2026-10-01",
    to: "2026-10-31",
  });
});

test("머리글을 누르면 그 표의 정렬만 주소에 남기고 1페이지로 돌아가 서버에 요청한다", async () => {
  const { requests } = stubCustomerUsageApi();
  const router = renderAt(`${OCTOBER}&view=customers&page=2`);

  const table = await tableNamed("고객별 사용 현황");
  fireEvent.click(
    within(table).getByRole("button", { name: "사용률 (추정 포함)" }),
  );

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      from: "2026-10-01",
      to: "2026-10-31",
      view: "customers",
      customersSort: "usage",
      customersOrder: "asc",
    }),
  );
  await waitFor(() =>
    expect(
      requests.some(
        (r) =>
          r.url.pathname.endsWith("/rows") &&
          r.url.searchParams.get("sort") === "usage" &&
          r.url.searchParams.get("order") === "asc",
      ),
    ).toBe(true),
  );
});

test("전체보기는 페이지를 주소에 남기고 그 페이지를 요청한다", async () => {
  const { requests } = stubCustomerUsageApi();
  const router = renderAt(`${OCTOBER}&view=customers`);

  fireEvent.click(await screen.findByRole("button", { name: "2" }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search?.page).toBe(2),
  );
  await waitFor(() =>
    expect(requests.some((r) => r.url.searchParams.get("page") === "2")).toBe(
      true,
    ),
  );
});

test("한 블록이 실패해도 다른 블록은 보이고 그 블록만 다시 시도한다", async () => {
  const api = stubCustomerUsageApi({
    summary: { status: 500, body: { code: "INTERNAL_ERROR", message: "오류" } },
  });
  // 오류 경계가 받는 오류를 React가 출력한다. 예상한 동작이라 테스트 출력에 남기지 않는다.
  vi.spyOn(console, "error").mockImplementation(() => {});
  renderAt(OCTOBER);

  expect(await screen.findByText("요약을 불러오지 못했어요")).toBeTruthy();
  expect(await tableNamed("고객별 사용 현황")).toBeTruthy();
  expect(screen.getAllByRole("button", { name: "다시 시도" })).toHaveLength(1);

  delete api.replies.summary;
  fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));

  expect(await screen.findByText("27,901")).toBeTruthy();
  expect(screen.queryByText("요약을 불러오지 못했어요")).toBeNull();
});

test("호출이 없으면 실패가 아니라 결과 없음으로 알린다", async () => {
  stubCustomerUsageApi({
    trend: {
      status: 200,
      body: {
        items: [
          {
            date: "2026-10-01",
            task_count: 0,
            call_count: 0,
            confirmed_cost_usd: "0",
            estimated_cost_usd: "0",
            unknown_cost_count: 0,
          },
        ],
      },
    },
    rows: { status: 200, body: EMPTY_PAGE },
    requests: { status: 200, body: EMPTY_PAGE },
  });
  renderAt(OCTOBER);

  expect(await screen.findAllByText(NO_RESULT)).toHaveLength(3);
  expect(screen.queryByRole("button", { name: "다시 시도" })).toBeNull();
});

test("조회 조건을 고르고 조회하면 1페이지로 돌아가 그 조건으로 요청한다", async () => {
  const { requests } = stubCustomerUsageApi();
  const router = renderAt(`${OCTOBER}&view=requests&page=3`);
  const customer = await screen.findByLabelText<HTMLSelectElement>("고객");
  await waitFor(() => expect(customer.disabled).toBe(false));

  fireEvent.change(customer, { target: { value: "2" } });
  expect(routeMatch(router, ROUTE_ID)?.search?.customer).toBeUndefined();
  fireEvent.click(screen.getByRole("button", { name: "조회" }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      from: "2026-10-01",
      to: "2026-10-31",
      view: "requests",
      customer: 2,
    }),
  );
  await waitFor(() =>
    expect(
      requests.some(
        (r) =>
          r.url.pathname.endsWith("/requests") &&
          r.url.searchParams.get("customer_id") === "2",
      ),
    ).toBe(true),
  );
});

test("고객명을 누르면 상세 패널에 서비스별 사용액을 보여 준다", async () => {
  const router = renderAt(OCTOBER);

  const table = await tableNamed("고객별 사용 현황");
  fireEvent.click(within(table).getByRole("link", { name: "A기업" }));

  const panel = await screen.findByRole("dialog", { name: "A기업" });
  expect(routeMatch(router, ROUTE_ID)?.search?.detail).toBe(1);
  expect(within(panel).getByText("서비스별 사용액")).toBeTruthy();
  expect(within(panel).getByRole("cell", { name: "AI PDP" })).toBeTruthy();
});

test("이 고객 사용 내역 보기는 패널을 닫고 고객 조건을 적용한다", async () => {
  const router = renderAt(`${OCTOBER}&detail=1`);

  const panel = await screen.findByRole("dialog", { name: "A기업" });
  fireEvent.click(
    within(panel).getByRole("link", { name: /이 고객 사용 내역 보기/ }),
  );

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      from: "2026-10-01",
      to: "2026-10-31",
      customer: 1,
    }),
  );
});

test("예산 저장은 입력값을 문자열로 보내고 예산 블록을 다시 불러온다", async () => {
  const { requests } = stubCustomerUsageApi();
  renderAt(`${OCTOBER}&detail=1`);

  const panel = await screen.findByRole("dialog", { name: "A기업" });
  const amount =
    within(panel).getByLabelText<HTMLInputElement>("월 예산 (USD)");
  expect(amount.value).toBe("10");
  fireEvent.change(amount, { target: { value: "20.5" } });
  const detailRequests = () =>
    requests.filter((r) => r.url.pathname.endsWith("/customers/1")).length;
  const before = detailRequests();
  fireEvent.click(within(panel).getByRole("button", { name: "예산 저장" }));

  await waitFor(() =>
    expect(requests.find((r) => r.method === "PUT")?.body).toEqual({
      monthly_amount_usd: "20.5",
      effective_from_month: "2026-10",
    }),
  );
  await waitFor(() => expect(detailRequests()).toBeGreaterThan(before));
});

test("서버가 예산을 거절하면 그 이유를 폼 위에 보여 준다", async () => {
  stubCustomerUsageApi({
    budget: {
      status: 409,
      body: {
        code: "BUDGET_PERIOD_CONFLICT",
        message: "이미 적용 중이거나 예정된 예산과 기간이 겹쳐요.",
      },
    },
  });
  renderAt(`${OCTOBER}&detail=1`);

  const panel = await screen.findByRole("dialog", { name: "A기업" });
  fireEvent.click(within(panel).getByRole("button", { name: "예산 저장" }));

  const alert = await within(panel).findByRole("alert");
  expect(alert.textContent).toBe(
    "이미 적용 중이거나 예정된 예산과 기간이 겹쳐요.",
  );
});
