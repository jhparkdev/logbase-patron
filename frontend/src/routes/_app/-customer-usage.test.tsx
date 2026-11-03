// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";
import { stubCustomerUsageApi } from "../../test/customerUsageApi";
import { changePeriod, periodInputs } from "../../test/periodInputs";
import { renderAt, routeMatch } from "../../test/renderAt";

const ROUTE_ID = "/_app/customer-usage";

// jsdom에는 모달 dialog 열기가 없어서, 브라우저처럼 open 속성만 켠다.
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

afterEach(() => vi.useRealTimers());

test("상세 패널은 조회 종료일이 속한 달의 사용 요약과 월 예산 입력을 보여 준다", async () => {
  renderAt("/customer-usage?from=2026-09-20&to=2026-10-15&detail=3");

  const panel = await screen.findByRole("dialog", { name: "A기업" });
  expect(
    within(panel).getByRole("heading", { name: "2026-10 사용액 · 추정 포함" }),
  ).toBeTruthy();
  expect(
    within(panel).getByLabelText<HTMLInputElement>("적용 시작 월").value,
  ).toBe("2026-10");
});

test("상세 패널은 서버가 준 주의 기준을 막대 기준선과 글자로 보여 준다", async () => {
  renderAt("/customer-usage?from=2026-09-20&to=2026-10-15&detail=3");

  const panel = await screen.findByRole("dialog", { name: "A기업" });
  expect(within(panel).getByText("주의 기준 80%")).toBeTruthy();
  expect(panel.querySelector("[data-mark='warning']")).toBeTruthy();
});

test("서비스별 사용액은 서버가 준 합계를 추정 포함 표시와 함께 보여 주고 화면에서 더하지 않는다", async () => {
  renderAt("/customer-usage?from=2026-09-20&to=2026-10-15&detail=3");

  const panel = await screen.findByRole("dialog", { name: "A기업" });
  const list = within(
    within(panel).getByRole("list", { name: "서비스별 사용액" }),
  );
  expect(list.getByText("AI PDP")).toBeTruthy();
  expect(list.getByText("≈ 12.10 USD")).toBeTruthy();
  expect(list.getByText("추정 포함")).toBeTruthy();
  expect(
    list.getByText(/예산의 121% · 확정 2.10 · 추정 ≈ 10.00 · 미확인 2건/),
  ).toBeTruthy();
});

test("상세 패널을 닫으면 패널 값만 지우고 조회 조건과 전체보기는 그대로다", async () => {
  const router = renderAt(
    "/customer-usage?from=2026-10-01&to=2026-10-15&view=customers&detail=3",
  );

  const panel = await screen.findByRole("dialog", { name: "A기업" });
  fireEvent.click(within(panel).getAllByRole("button", { name: "닫기" })[0]);

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      from: "2026-10-01",
      to: "2026-10-15",
      view: "customers",
    }),
  );
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("주소에 기간이 없으면 KST 오늘을 포함한 최근 30일을 칸에 보여 준다", async () => {
  // 화면 동작은 그대로 두고 현재 날짜만 고정한다.
  vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-10-31T03:00:00Z") });
  renderAt("/customer-usage");

  const { from, to } = await periodInputs();
  expect(from.value).toBe("2026-10-02");
  expect(to.value).toBe("2026-10-31");
});

test("고객별 사용 현황은 조회 기간 종료일이 속한 달의 예산 기준임을 알린다", async () => {
  renderAt("/customer-usage?from=2026-09-20&to=2026-10-15");

  expect(await screen.findByText("2026-10 기준")).toBeTruthy();
});

test.each([
  {
    table: "고객별 사용 현황",
    view: "customers",
    hidden: "상세 API 호출 내역",
  },
  { table: "상세 API 호출 내역", view: "requests", hidden: "고객별 사용 현황" },
])(
  "$table 전체보기는 조회 기간을 그대로 두고 그 표만 펼친다",
  async ({ table, view, hidden }) => {
    const router = renderAt("/customer-usage?from=2026-10-01&to=2026-10-15");

    fireEvent.click(
      await screen.findByRole("link", { name: `${table} 전체보기` }),
    );

    await waitFor(() =>
      expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
        from: "2026-10-01",
        to: "2026-10-15",
        view,
      }),
    );
    expect(screen.getByRole("heading", { name: table })).toBeTruthy();
    for (const name of [hidden, "사용량·비용 추이"]) {
      expect(screen.queryByRole("heading", { name })).toBeNull();
    }
    expect(screen.queryByRole("link", { name: /전체보기/ })).toBeNull();
  },
);

test("호출 전체보기에서는 최근 20건 표시를 하지 않는다", async () => {
  renderAt("/customer-usage?from=2026-10-01&to=2026-10-15&view=requests");

  expect(
    await screen.findByRole("heading", { name: "상세 API 호출 내역" }),
  ).toBeTruthy();
  expect(screen.queryByText("최근 20건")).toBeNull();
});

test("요약으로 돌아가면 조회 기간은 그대로 두고 요약 화면을 보여 준다", async () => {
  const router = renderAt(
    "/customer-usage?from=2026-10-01&to=2026-10-15&view=customers",
  );

  fireEvent.click(
    await screen.findByRole("link", { name: "요약으로 돌아가기" }),
  );

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      from: "2026-10-01",
      to: "2026-10-15",
    }),
  );
  expect(
    screen.getByRole("heading", { name: "사용량·비용 추이" }),
  ).toBeTruthy();
  expect(screen.getByText("최근 20건")).toBeTruthy();
});

test("조회를 눌러야 바꾼 기간이 주소에 남는다", async () => {
  const router = renderAt("/customer-usage?from=2026-10-01&to=2026-10-15");

  await changePeriod({ from: "2026-09-01", to: "2026-09-30" });
  expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
    from: "2026-10-01",
    to: "2026-10-15",
  });

  fireEvent.click(screen.getByRole("button", { name: "조회" }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      from: "2026-09-01",
      to: "2026-09-30",
    }),
  );
});

test("전체보기에서 조회해도 전체보기가 그대로다", async () => {
  const router = renderAt(
    "/customer-usage?from=2026-10-01&to=2026-10-15&view=requests",
  );
  await changePeriod({ from: "2026-09-01", to: "2026-09-30" });

  fireEvent.click(screen.getByRole("button", { name: "조회" }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      from: "2026-09-01",
      to: "2026-09-30",
      view: "requests",
    }),
  );
});

test.each([
  {
    label: "366일을 넘는 기간",
    period: { from: "2025-01-01", to: "2026-01-02" },
    message: "기간은 최대 366일까지 조회할 수 있어요. 기간을 줄여 주세요.",
  },
  {
    label: "시작일이 종료일보다 늦은 기간",
    period: { from: "2026-10-20", to: "2026-10-10" },
    message: "시작일은 종료일보다 늦을 수 없어요.",
  },
])("$label은 조회하지 않고 이유를 알린다", async ({ period, message }) => {
  const router = renderAt("/customer-usage?from=2026-10-01&to=2026-10-15");
  await changePeriod(period);

  fireEvent.click(screen.getByRole("button", { name: "조회" }));

  expect((await screen.findByRole("alert")).textContent).toBe(message);
  expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
    from: "2026-10-01",
    to: "2026-10-15",
  });
});

test("뒤로 가기로 주소가 바뀌면 칸도 그 기간으로 돌아간다", async () => {
  const router = renderAt("/customer-usage?from=2026-10-01&to=2026-10-15");
  await changePeriod({ from: "2026-09-01", to: "2026-09-30" });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search?.from).toBe("2026-09-01"),
  );

  router.history.back();

  await waitFor(async () => {
    const { from, to } = await periodInputs();
    expect(from.value).toBe("2026-10-01");
    expect(to.value).toBe("2026-10-15");
  });
});
