// @vitest-environment jsdom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";
import { stubInternalBudgetApi } from "../../test/internalBudgetApi";
import { changePeriod, periodInputs } from "../../test/periodInputs";
import { renderAt, routeMatch } from "../../test/renderAt";

// jsdom에는 모달 dialog 열기가 없어서, 브라우저처럼 open 속성만 켠다.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
});

beforeEach(() => {
  stubInternalBudgetApi();
});

afterEach(() => vi.restoreAllMocks());

const ROUTE_ID = "/_app/internal-budget";

test("주소의 기간을 칸에 보여 준다", async () => {
  renderAt("/internal-budget?from=2026-10-01&to=2026-10-15");

  const { from, to } = await periodInputs();
  expect(from.value).toBe("2026-10-01");
  expect(to.value).toBe("2026-10-15");
});

test("조회를 눌러야 바꾼 기간이 주소에 남는다", async () => {
  const router = renderAt("/internal-budget?from=2026-10-01&to=2026-10-15");

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

test("366일을 넘는 기간은 조회하지 않고 줄여 달라고 안내한다", async () => {
  const router = renderAt("/internal-budget?from=2026-10-01&to=2026-10-15");

  await changePeriod({ from: "2025-01-01", to: "2026-01-02" });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "기간은 최대 366일까지 조회할 수 있어요. 기간을 줄여 주세요.",
  );
  expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
    from: "2026-10-01",
    to: "2026-10-15",
  });
});

test("예산 현황은 조회 기간 종료일이 속한 달 기준임을 알린다", async () => {
  renderAt("/internal-budget?from=2026-09-01&to=2026-10-15");

  expect(await screen.findByText(/2026-10 기준/)).toBeTruthy();
});

const PERIOD = "from=2026-10-01&to=2026-10-15";

test("전체보기를 누르면 그 목록만 펼치고 조회 기간은 그대로 둔다", async () => {
  const router = renderAt(`/internal-budget?${PERIOD}`);

  fireEvent.click(
    await screen.findByRole("link", { name: "프로젝트별 예산 현황 전체보기" }),
  );

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      from: "2026-10-01",
      to: "2026-10-15",
      view: "projects",
    }),
  );
  expect(screen.queryByRole("table", { name: "구독료 관리" })).toBeNull();
});

test("전체 목록에서 머리글을 누르면 정렬이 주소에 남고 1페이지로 돌아간다", async () => {
  const router = renderAt(`/internal-budget?${PERIOD}&view=requests&page=3`);

  fireEvent.click(await screen.findByRole("button", { name: /비용 \(USD\)/ }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      from: "2026-10-01",
      to: "2026-10-15",
      view: "requests",
      requestsSort: "cost",
      requestsOrder: "asc",
    }),
  );
});

test("전체 목록에서 조회하면 목록은 유지하고 1페이지로 돌아간다", async () => {
  const router = renderAt(`/internal-budget?${PERIOD}&view=projects&page=3`);
  const { to } = await periodInputs();

  fireEvent.change(to, { target: { value: "2026-10-20" } });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      from: "2026-10-01",
      to: "2026-10-20",
      view: "projects",
    }),
  );
});

test("요약으로 돌아가면 목록·페이지 값은 지우고 정렬은 이어 간다", async () => {
  const router = renderAt(
    `/internal-budget?${PERIOD}&view=requests&requestsSort=cost&requestsOrder=desc&page=2`,
  );

  fireEvent.click(
    await screen.findByRole("link", { name: "요약으로 돌아가기" }),
  );

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      from: "2026-10-01",
      to: "2026-10-15",
      requestsSort: "cost",
      requestsOrder: "desc",
    }),
  );
});

test("요약 화면에서 머리글을 누르면 그 표의 정렬만 주소에 남는다", async () => {
  const router = renderAt(`/internal-budget?${PERIOD}`);

  fireEvent.click(await screen.findByRole("button", { name: /비용 \(USD\)/ }));
  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      from: "2026-10-01",
      to: "2026-10-15",
      requestsSort: "cost",
      requestsOrder: "asc",
    }),
  );

  fireEvent.click(screen.getByRole("button", { name: /월 예산 \(USD\)/ }));
  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      from: "2026-10-01",
      to: "2026-10-15",
      requestsSort: "cost",
      requestsOrder: "asc",
      projectsSort: "budget",
      projectsOrder: "asc",
    }),
  );
});

test("주소에 프로젝트 번호가 있으면 프로젝트 상세 패널을 열고, 닫으면 그 값만 지운다", async () => {
  const router = renderAt(`/internal-budget?${PERIOD}&project=3`);

  await screen.findByRole("dialog", { name: "프로젝트 상세" });
  // 패널 머리의 X. 폼 아래에도 같은 동작의 "닫기"가 있다.
  fireEvent.click(screen.getAllByRole("button", { name: "닫기" })[0]);

  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
    from: "2026-10-01",
    to: "2026-10-15",
  });
});

test("구독료 등록을 누르면 등록 패널이 열리고 주소에 남는다", async () => {
  const router = renderAt(`/internal-budget?${PERIOD}`);

  fireEvent.click(await screen.findByRole("button", { name: "구독료 등록" }));

  await screen.findByRole("dialog", { name: "구독료 등록" });
  expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
    from: "2026-10-01",
    to: "2026-10-15",
    subscription: "new",
  });
});
