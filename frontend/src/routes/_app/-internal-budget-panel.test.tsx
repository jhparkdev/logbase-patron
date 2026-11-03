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

const RICH_DETAIL = {
  ...PROJECT_DETAIL,
  subscription_usd: "800.00",
  services: [
    {
      service_id: 1,
      service_name: "고객센터 챗봇",
      task_count: 10,
      call_count: 30,
      confirmed_cost_usd: "1320.00",
      estimated_cost_usd: "310.00",
      unknown_cost_count: 2,
      budget_share_pct: "33.00",
    },
    {
      service_id: 2,
      service_name: "코드 리뷰 봇",
      task_count: 2,
      call_count: 10,
      confirmed_cost_usd: "160.00",
      estimated_cost_usd: "0.00",
      unknown_cost_count: 0,
      budget_share_pct: "4.00",
    },
  ],
  subscriptions: [
    {
      subscription_id: 1,
      tool_name: "Cursor Business",
      amount_usd: "480.00",
      status: "ACTIVE",
    },
    {
      subscription_id: 2,
      tool_name: "ChatGPT Team",
      amount_usd: "320.00",
      status: "CANCELLED",
    },
  ],
};

test("패널은 조회 종료일이 속한 달의 사용액을 예산 대비 쌓은 막대와 구성 금액으로 보여 주고 지금 월 예산을 채운다", async () => {
  const { requests } = stubInternalBudgetApi();
  renderAt(PANEL);

  const dialog = within(await panel());
  expect(
    dialog.getByRole("heading", { name: "2026-10 사용액 · 추정·구독료 포함" }),
  ).toBeTruthy();
  expect(dialog.getByText("3,420.50")).toBeTruthy();
  expect(dialog.getByText("/ 5,000.00 USD")).toBeTruthy();
  expect(dialog.getByText("정상")).toBeTruthy();
  expect(
    dialog
      .getByRole("meter", { name: "사용률" })
      .getAttribute("aria-valuetext"),
  ).toBe("68%");
  expect(dialog.getByText("68% 사용")).toBeTruthy();
  expect(dialog.getByText("1,579.50")).toBeTruthy();
  expect(dialog.getByText("API 확정 비용").nextSibling?.textContent).toBe(
    "3,100.20",
  );
  expect(dialog.getByText("API 추정 비용").nextSibling?.textContent).toBe(
    "≈ 320.30",
  );
  expect(dialog.getByText("귀속 구독료").nextSibling?.textContent).toBe("0.00");
  expect(dialog.getByText("12건")).toBeTruthy();
  expect(dialog.getByText("40회")).toBeTruthy();
  expect(dialog.getByText("2건 미반영")).toBeTruthy();
  expect(dialog.getByLabelText<HTMLInputElement>("월 예산 (USD)").value).toBe(
    "5000",
  );
  expect(dialog.getByLabelText<HTMLInputElement>("적용 시작 월").value).toBe(
    "2026-10",
  );
  expect(dialog.getByText(/구독료도 예산에서 함께 빠져요/)).toBeTruthy();
  const detail = requests.find(({ url }) =>
    url.pathname.endsWith("/projects/1"),
  );
  expect(detail?.url.searchParams.get("month")).toBe("2026-10");
});

test("예산이 없으면 0%가 아니라 미설정이고 막대 대신 안내, 월 예산 칸은 비어 있다", async () => {
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

  const dialog = within(await panel());
  expect(dialog.getByText("예산 미설정")).toBeTruthy();
  expect(dialog.getByText("예산을 정하면 사용률이 보여요")).toBeTruthy();
  expect(dialog.queryByRole("meter")).toBeNull();
  expect(dialog.queryByText(/0% 사용/)).toBeNull();
  expect(dialog.getByLabelText<HTMLInputElement>("월 예산 (USD)").value).toBe(
    "",
  );
});

test("서비스별 API 사용액은 확정 금액과 예산 비중을, 추정·미확인은 아래 줄에 따로 보여 준다", async () => {
  stubInternalBudgetApi({ detail: { status: 200, body: RICH_DETAIL } });
  renderAt(PANEL);

  const dialog = within(await panel());
  const list = within(
    dialog.getByRole("list", { name: "서비스별 API 사용액" }),
  );
  expect(list.getByText("고객센터 챗봇")).toBeTruthy();
  expect(list.getByText("1,320.00")).toBeTruthy();
  expect(list.getByText("33%")).toBeTruthy();
  expect(list.getByText("추정 ≈ 310.00 · 미확인 2건")).toBeTruthy();
  expect(list.getByText("160.00")).toBeTruthy();
  expect(list.queryByText(/추정 ≈ 0\.00/)).toBeNull();
});

test("귀속 구독료는 서버 합계와 함께 구독마다 상태 배지와 금액을 보여 준다", async () => {
  stubInternalBudgetApi({ detail: { status: 200, body: RICH_DETAIL } });
  renderAt(PANEL);

  const dialog = within(await panel());
  expect(dialog.getByText("합계 800.00 USD")).toBeTruthy();
  const list = within(dialog.getByRole("list", { name: "귀속 구독료" }));
  expect(list.getByText("Cursor Business")).toBeTruthy();
  expect(list.getByText("사용 중")).toBeTruthy();
  expect(list.getByText("480.00")).toBeTruthy();
  expect(list.getByText("ChatGPT Team")).toBeTruthy();
  expect(list.getByText("해지")).toBeTruthy();
  expect(list.getByText("320.00")).toBeTruthy();
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
