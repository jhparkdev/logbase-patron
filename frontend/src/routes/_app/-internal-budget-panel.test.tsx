// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";
import {
  PROJECT_DETAIL,
  stubInternalBudgetApi,
} from "../../test/internalBudgetApi";
import { renderAt, routeMatch } from "../../test/renderAt";

const ROUTE_ID = "/_app/internal-budget";
const OCTOBER = "/internal-budget?from=2026-10-01&to=2026-10-31";
const PANEL = `${OCTOBER}&detail=1`;
const NAME = "사내 챗봇 구축";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
});

beforeEach(() => {
  stubInternalBudgetApi();
});

afterEach(() => vi.restoreAllMocks());

function panel() {
  return screen.findByRole("dialog", { name: NAME });
}

test("패널은 조회 종료일이 속한 달의 사용 요약과 지금 월 예산을 보여 준다", async () => {
  const { requests } = stubInternalBudgetApi();
  renderAt(PANEL);

  const dialog = await panel();
  expect(within(dialog).getByText("2026-10 사용 요약")).toBeTruthy();
  expect(within(dialog).getByText("3,100.20")).toBeTruthy();
  expect(within(dialog).getByText(/≈\s320\.30/)).toBeTruthy();
  expect(within(dialog).getByText("2건")).toBeTruthy();
  expect(within(dialog).getByText("정상")).toBeTruthy();
  expect(
    within(dialog).getByText("사용액 3,420.50 USD (추정 포함) · 예산의 68%"),
  ).toBeTruthy();
  expect(
    within(dialog).getByLabelText<HTMLInputElement>("월 예산 (USD)").value,
  ).toBe("5000");
  expect(
    within(dialog).getByLabelText<HTMLInputElement>("적용 시작 월").value,
  ).toBe("2026-10");
  const detail = requests.find(({ url }) =>
    url.pathname.endsWith("/projects/1"),
  );
  expect(detail?.url.searchParams.get("month")).toBe("2026-10");
});

test("예산이 없으면 0%가 아니라 미설정이고 월 예산 칸은 비어 있다", async () => {
  stubInternalBudgetApi({
    detail: {
      status: 200,
      body: {
        ...PROJECT_DETAIL,
        budget: {
          ...PROJECT_DETAIL.budget,
          monthly_amount_usd: null,
          effective_from_month: null,
          usage_pct: null,
          confirmed_usage_pct: null,
          remaining_usd: null,
          status: "UNSET",
        },
      },
    },
  });
  renderAt(PANEL);

  const dialog = await panel();
  expect(
    within(dialog).getByText("사용액 3,420.50 USD (추정 포함) · 예산 미설정"),
  ).toBeTruthy();
  expect(within(dialog).queryByText(/예산의 0%/)).toBeNull();
  expect(
    within(dialog).getByLabelText<HTMLInputElement>("월 예산 (USD)").value,
  ).toBe("");
});

test("예산을 저장하면 입력값을 문자열로 보내고 패널과 프로젝트 표를 다시 불러온다", async () => {
  const { requests } = stubInternalBudgetApi();
  renderAt(PANEL);

  const dialog = await panel();
  await screen.findByRole("table", { name: "프로젝트별 예산 현황" });
  fireEvent.change(within(dialog).getByLabelText("월 예산 (USD)"), {
    target: { value: "6000.5" },
  });
  const count = (suffix: string) =>
    requests.filter(
      ({ url, method }) => method === "GET" && url.pathname.endsWith(suffix),
    ).length;
  const before = { detail: count("/projects/1"), rows: count("/projects") };
  fireEvent.click(within(dialog).getByRole("button", { name: "예산 저장" }));

  await waitFor(() =>
    expect(requests.find(({ method }) => method === "PUT")?.body).toEqual({
      monthly_amount_usd: "6000.5",
      effective_from_month: "2026-10",
    }),
  );
  await waitFor(() => {
    expect(count("/projects/1")).toBeGreaterThan(before.detail);
    expect(count("/projects")).toBeGreaterThan(before.rows);
  });
});

test("서버가 예산을 거절하면 그 이유를 폼 위에 보여 준다", async () => {
  stubInternalBudgetApi({
    budget: {
      status: 409,
      body: {
        code: "BUDGET_PERIOD_CONFLICT",
        message: "이미 적용 중이거나 예정된 예산과 기간이 겹쳐요.",
      },
    },
  });
  renderAt(PANEL);

  const dialog = await panel();
  fireEvent.click(within(dialog).getByRole("button", { name: "예산 저장" }));

  expect((await within(dialog).findByRole("alert")).textContent).toBe(
    "이미 적용 중이거나 예정된 예산과 기간이 겹쳐요.",
  );
});

test("없는 프로젝트 번호면 찾을 수 없다고 알리고 다시 시도를 두지 않는다", async () => {
  stubInternalBudgetApi({
    detail: {
      status: 404,
      body: { code: "NOT_FOUND", message: "프로젝트를 찾을 수 없어요." },
    },
  });
  renderAt(`${OCTOBER}&detail=99`);

  const dialog = await screen.findByRole("dialog", { name: "프로젝트 상세" });
  expect(
    await within(dialog).findByText("프로젝트를 찾을 수 없어요"),
  ).toBeTruthy();
  expect(
    within(dialog).queryByRole("button", { name: "다시 시도" }),
  ).toBeNull();
});

test("상세를 불러오지 못하면 패널 안에서 다시 시도할 수 있다", async () => {
  const { replies } = stubInternalBudgetApi({
    detail: { status: 500, body: {} },
  });
  renderAt(PANEL);

  const dialog = await screen.findByRole("dialog", { name: "프로젝트 상세" });
  expect(
    await within(dialog).findByText("프로젝트 상세를 불러오지 못했어요"),
  ).toBeTruthy();

  delete replies.detail;
  fireEvent.click(within(dialog).getByRole("button", { name: "다시 시도" }));

  expect(await panel()).toBeTruthy();
});

test("이 프로젝트 사용 내역 보기를 누르면 패널을 닫고 화면 전체에 프로젝트 조건을 건다", async () => {
  const router = renderAt(`${PANEL}&view=requests&page=2`);

  const dialog = await panel();
  fireEvent.click(
    within(dialog).getByRole("link", { name: /이 프로젝트 사용 내역 보기/ }),
  );

  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
    from: "2026-10-01",
    to: "2026-10-31",
    view: "requests",
    project: 1,
  });
});
