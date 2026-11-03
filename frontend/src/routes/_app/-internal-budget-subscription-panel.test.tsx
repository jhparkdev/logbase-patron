// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";
import { stubInternalBudgetApi } from "../../test/internalBudgetApi";
import { renderAt, routeMatch } from "../../test/renderAt";

const ROUTE_ID = "/_app/internal-budget";
const OCTOBER = "/internal-budget?from=2026-10-01&to=2026-10-31";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
});

beforeEach(() => {
  stubInternalBudgetApi();
});

afterEach(() => vi.restoreAllMocks());

function countOf(requests: { url: URL; method: string }[], pathname: string) {
  return requests.filter(
    ({ url, method }) => method === "GET" && url.pathname === pathname,
  ).length;
}

test("등록 패널에서 채운 값을 보내고, 성공하면 패널을 닫고 구독료 표와 요약을 다시 불러온다", async () => {
  const { requests } = stubInternalBudgetApi();
  const router = renderAt(`${OCTOBER}&subscription=new`);

  const dialog = await screen.findByRole("dialog", { name: "구독료 등록" });
  await screen.findByRole("table", { name: "구독료 관리" });
  await screen.findByText("1,240.50");
  const project =
    within(dialog).getByLabelText<HTMLSelectElement>("귀속 프로젝트");
  await waitFor(() => expect(project.disabled).toBe(false));
  const before = {
    list: countOf(requests, "/api/subscriptions"),
    summary: countOf(requests, "/api/usage/internal/summary"),
  };

  fireEvent.change(within(dialog).getByLabelText("구독 식별값"), {
    target: { value: "claude-team" },
  });
  fireEvent.change(within(dialog).getByLabelText("도구명"), {
    target: { value: "Claude Team" },
  });
  fireEvent.change(within(dialog).getByLabelText("금액 (USD)"), {
    target: { value: "300" },
  });
  fireEvent.change(project, { target: { value: "2" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "등록" }));

  await waitFor(() =>
    expect(requests.find(({ method }) => method === "POST")?.body).toEqual({
      subscription_reference: "claude-team",
      tool_name: "Claude Team",
      subscription_type: null,
      applied_month: "2026-10",
      amount_usd: "300",
      project_id: 2,
      note: null,
    }),
  );
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(routeMatch(router, ROUTE_ID)?.search.subscription).toBeUndefined();
  await waitFor(() => {
    expect(countOf(requests, "/api/subscriptions")).toBeGreaterThan(
      before.list,
    );
    expect(countOf(requests, "/api/usage/internal/summary")).toBeGreaterThan(
      before.summary,
    );
  });
});

test("서버가 중복이라고 거절하면 그 이유를 폼 위에 보여 주고 패널은 열어 둔다", async () => {
  stubInternalBudgetApi({
    subscriptionCreate: {
      status: 409,
      body: {
        code: "SUBSCRIPTION_DUPLICATE",
        message:
          "이미 등록된 구독입니다. 구독 식별값과 적용 월을 확인해 주세요.",
      },
    },
  });
  renderAt(`${OCTOBER}&subscription=new`);

  const dialog = await screen.findByRole("dialog", { name: "구독료 등록" });
  fireEvent.change(within(dialog).getByLabelText("구독 식별값"), {
    target: { value: "command-code-team" },
  });
  fireEvent.change(within(dialog).getByLabelText("도구명"), {
    target: { value: "Command Code" },
  });
  fireEvent.change(within(dialog).getByLabelText("금액 (USD)"), {
    target: { value: "100" },
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "등록" }));

  expect((await within(dialog).findByRole("alert")).textContent).toBe(
    "이미 등록된 구독입니다. 구독 식별값과 적용 월을 확인해 주세요.",
  );
  expect(screen.getByRole("dialog", { name: "구독료 등록" })).toBeTruthy();
});

test("표의 도구명을 누르면 수정 패널이 열리고, 저장하면 바꾼 칸만 보낸다", async () => {
  const { requests } = stubInternalBudgetApi();
  const router = renderAt(OCTOBER);

  const table = await screen.findByRole("table", { name: "구독료 관리" });
  fireEvent.click(within(table).getByRole("link", { name: "Notion AI" }));

  const dialog = await screen.findByRole("dialog", { name: "구독료 수정" });
  expect(routeMatch(router, ROUTE_ID)?.search.subscription).toBe(2);
  expect(within(dialog).getByText("notion-ai")).toBeTruthy();
  expect(
    within(dialog).getByLabelText<HTMLInputElement>("금액 (USD)").value,
  ).toBe("20");
  expect(
    within(dialog).getByRole<HTMLInputElement>("radio", { name: "해지" })
      .checked,
  ).toBe(true);
  fireEvent.change(within(dialog).getByLabelText("금액 (USD)"), {
    target: { value: "25" },
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "저장" }));

  await waitFor(() => {
    const patch = requests.find(({ method }) => method === "PATCH");
    expect(patch?.url.pathname).toBe("/api/subscriptions/2");
    expect(patch?.body).toEqual({ amount_usd: "25" });
  });
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

test("지금 목록에 없는 구독료 번호면 목록에서 열어 달라고 알린다", async () => {
  renderAt(`${OCTOBER}&subscription=99`);

  const dialog = await screen.findByRole("dialog", { name: "구독료 수정" });
  expect(
    await within(dialog).findByText("이 구독료는 지금 목록에 없어요"),
  ).toBeTruthy();
  expect(within(dialog).queryByRole("button", { name: "저장" })).toBeNull();
});

test("표의 도구명으로 수정 패널을 열어도 화면을 맨 위로 올리지 않는다", async () => {
  const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  renderAt(OCTOBER);
  const table = await screen.findByRole("table", { name: "구독료 관리" });
  scrollTo.mockClear();

  fireEvent.click(within(table).getByRole("link", { name: "Notion AI" }));
  await screen.findByRole("dialog", { name: "구독료 수정" });

  expect(scrollTo).not.toHaveBeenCalled();
});
