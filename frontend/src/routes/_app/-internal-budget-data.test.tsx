// @vitest-environment jsdom
import { fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { SUMMARY, stubInternalBudgetApi } from "../../test/internalBudgetApi";
import { renderAt } from "../../test/renderAt";

const OCTOBER = "/internal-budget?from=2026-10-01&to=2026-10-31";
const SUMMARY_ERROR = "요약을 불러오지 못했어요";
const EMPTY_PAGE = { items: [], total: 0, page: 1, page_size: 10 };

beforeEach(() => {
  stubInternalBudgetApi();
});

afterEach(() => vi.restoreAllMocks());

test("요약 카드는 서버 금액을 보여 주고 미확인 건수는 총 관리 비용에 넣지 않았다고 알린다", async () => {
  renderAt(OCTOBER);

  expect(await screen.findByText("1,240.50")).toBeTruthy();
  expect(screen.getByText(/≈\s320\.15/)).toBeTruthy();
  expect(screen.getByText("980.00")).toBeTruthy();
  expect(screen.getByText("2,540.65")).toBeTruthy();
  expect(screen.getByText("미확인 3건 미반영")).toBeTruthy();
});

test("추정 비용이 0이면 ≈ 없이 보여 주고, 미확인이 없으면 미반영 안내를 하지 않는다", async () => {
  stubInternalBudgetApi({
    summary: {
      status: 200,
      body: {
        ...SUMMARY,
        api_estimated_usd: "0",
        unknown_cost_count: 0,
        has_unknown: false,
      },
    },
    // 요약 카드만 보도록 금액이 나오는 다른 표는 비운다.
    projects: { status: 200, body: EMPTY_PAGE },
    requests: { status: 200, body: EMPTY_PAGE },
  });
  renderAt(OCTOBER);

  expect(await screen.findByText("0.00")).toBeTruthy();
  expect(screen.queryByText(/≈/)).toBeNull();
  expect(screen.queryByText(/미반영/)).toBeNull();
});

test("요약은 주소의 조회 기간으로 요청한다", async () => {
  const { requests } = stubInternalBudgetApi();
  renderAt(OCTOBER);

  await screen.findByText("1,240.50");
  const summary = requests.find(({ url }) => url.pathname.endsWith("/summary"));
  expect(summary?.url.searchParams.get("start_date")).toBe("2026-10-01");
  expect(summary?.url.searchParams.get("end_date")).toBe("2026-10-31");
});

test("요약을 불러오지 못하면 그 블록에만 알리고 다시 시도할 수 있다", async () => {
  const { replies } = stubInternalBudgetApi({
    summary: { status: 500, body: {} },
  });
  renderAt(OCTOBER);

  expect(await screen.findByText(SUMMARY_ERROR)).toBeTruthy();
  expect(
    await screen.findByRole("table", { name: "프로젝트별 예산 현황" }),
  ).toBeTruthy();

  delete replies.summary;
  fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));

  expect(await screen.findByText("1,240.50")).toBeTruthy();
  expect(screen.queryByText(SUMMARY_ERROR)).toBeNull();
});

test("전체보기에서는 요약을 요청하지 않는다", async () => {
  const { requests } = stubInternalBudgetApi();
  renderAt(`${OCTOBER}&view=projects`);

  await screen.findByRole("table", { name: "프로젝트별 예산 현황" });
  expect(requests.some(({ url }) => url.pathname.endsWith("/summary"))).toBe(
    false,
  );
});
