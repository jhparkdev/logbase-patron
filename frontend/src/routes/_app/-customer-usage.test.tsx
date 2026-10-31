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
