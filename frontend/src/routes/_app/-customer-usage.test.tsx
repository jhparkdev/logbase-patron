// @vitest-environment jsdom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { changePeriod, periodInputs } from "../../test/periodInputs";
import { renderAt, routeMatch } from "../../test/renderAt";

const ROUTE_ID = "/_app/customer-usage";

afterEach(() => vi.useRealTimers());

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
