// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";
import {
  PROJECT_CREATED,
  SUBSCRIPTIONS,
  stubInternalBudgetApi,
} from "../../test/internalBudgetApi";
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

/** 등록 패널을 열고 새 프로젝트 이름까지 채운다. 등록 버튼은 누르지 않는다. */
async function fillWithNewProject(name: string) {
  const dialog = await screen.findByRole("dialog", { name: "구독료 등록" });
  const project =
    within(dialog).getByLabelText<HTMLSelectElement>("귀속 프로젝트");
  await waitFor(() => expect(project.disabled).toBe(false));
  fireEvent.change(within(dialog).getByLabelText("구독 식별값"), {
    target: { value: "claude-team" },
  });
  fireEvent.change(within(dialog).getByLabelText("도구명"), {
    target: { value: "Claude Team" },
  });
  fireEvent.change(within(dialog).getByLabelText("금액 (USD)"), {
    target: { value: "300" },
  });
  fireEvent.change(project, { target: { value: "new" } });
  fireEvent.change(within(dialog).getByLabelText("새 프로젝트 이름"), {
    target: { value: name },
  });
  return dialog;
}

test("새 프로젝트 이름을 적어 등록하면 프로젝트를 먼저 만들고 그 번호로 구독료를 등록한 뒤 선택지를 다시 불러온다", async () => {
  const { requests } = stubInternalBudgetApi();
  renderAt(`${OCTOBER}&subscription=new`);
  const dialog = await fillWithNewProject("신규 프로젝트");
  const optionsBefore = countOf(requests, "/api/subscriptions/options");

  fireEvent.click(within(dialog).getByRole("button", { name: "등록" }));

  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  const posts = requests.filter(({ method }) => method === "POST");
  expect(posts.map(({ url }) => url.pathname)).toEqual([
    "/api/projects",
    "/api/subscriptions",
  ]);
  expect(posts[0].body).toMatchObject({ name: "신규 프로젝트" });
  expect(posts[1].body).toMatchObject({
    project_id: PROJECT_CREATED.project_id,
  });
  await waitFor(() => {
    expect(countOf(requests, "/api/subscriptions/options")).toBeGreaterThan(
      optionsBefore,
    );
    expect(countOf(requests, "/api/usage/internal/options")).toBeGreaterThan(1);
  });
});

test("새 프로젝트 이름이 선택지에 있는 이름이면(띄어쓰기·대소문자 무시) 만들지 않고 그 프로젝트에 귀속한다", async () => {
  const { requests } = stubInternalBudgetApi();
  renderAt(`${OCTOBER}&subscription=new`);
  const dialog = await fillWithNewProject("문서요약");

  fireEvent.click(within(dialog).getByRole("button", { name: "등록" }));

  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  const posts = requests.filter(({ method }) => method === "POST");
  expect(posts.map(({ url }) => url.pathname)).toEqual(["/api/subscriptions"]);
  expect(posts[0].body).toMatchObject({ project_id: 2 });
});

test("프로젝트 등록이 중복(409)이면 서버가 알려 준 기존 프로젝트 번호로 구독료를 등록한다", async () => {
  const { requests } = stubInternalBudgetApi({
    projectCreate: {
      status: 409,
      body: {
        code: "PROJECT_DUPLICATE",
        message: "이미 있는 프로젝트입니다. 목록에서 선택해 주세요.",
        existing: { ...PROJECT_CREATED, project_id: 7 },
      },
    },
  });
  renderAt(`${OCTOBER}&subscription=new`);
  const dialog = await fillWithNewProject("신규 프로젝트");

  fireEvent.click(within(dialog).getByRole("button", { name: "등록" }));

  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  const subscription = requests.find(
    ({ method, url }) =>
      method === "POST" && url.pathname === "/api/subscriptions",
  );
  expect(subscription?.body).toMatchObject({ project_id: 7 });
});

test("프로젝트 등록이 다른 이유로 실패하면 구독료를 등록하지 않고 서버 문구를 보여 준다", async () => {
  const { requests } = stubInternalBudgetApi({
    projectCreate: {
      status: 422,
      body: {
        code: "VALIDATION_ERROR",
        message: "프로젝트 이름이 너무 길어요.",
      },
    },
  });
  renderAt(`${OCTOBER}&subscription=new`);
  const dialog = await fillWithNewProject("신규 프로젝트");

  fireEvent.click(within(dialog).getByRole("button", { name: "등록" }));

  expect((await within(dialog).findByRole("alert")).textContent).toBe(
    "프로젝트 이름이 너무 길어요.",
  );
  expect(
    requests.some(
      ({ method, url }) =>
        method === "POST" && url.pathname === "/api/subscriptions",
    ),
  ).toBe(false);
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

test("표의 도구명을 누르면 그 구독료를 단건 조회해 수정 패널에 채우고, 저장하면 바꾼 칸만 보낸다", async () => {
  const { requests } = stubInternalBudgetApi();
  const router = renderAt(OCTOBER);

  const table = await screen.findByRole("table", { name: "구독료 관리" });
  fireEvent.click(within(table).getByRole("link", { name: "Notion AI" }));

  const dialog = await screen.findByRole("dialog", { name: "구독료 수정" });
  expect(routeMatch(router, ROUTE_ID)?.search.subscription).toBe(2);
  expect(await within(dialog).findByText("notion-ai")).toBeTruthy();
  expect(countOf(requests, "/api/subscriptions/2")).toBe(1);
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

test("저장한 뒤 같은 구독료를 다시 열면 새로 불러온 값을 보여 준다", async () => {
  const { replies } = stubInternalBudgetApi();
  renderAt(OCTOBER);

  const table = await screen.findByRole("table", { name: "구독료 관리" });
  fireEvent.click(within(table).getByRole("link", { name: "Notion AI" }));
  const dialog = await screen.findByRole("dialog", { name: "구독료 수정" });
  fireEvent.change(await within(dialog).findByLabelText("금액 (USD)"), {
    target: { value: "25" },
  });
  replies.subscription = {
    status: 200,
    body: { ...SUBSCRIPTIONS.items[1], amount_usd: "25.0000" },
  };
  fireEvent.click(within(dialog).getByRole("button", { name: "저장" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

  fireEvent.click(within(table).getByRole("link", { name: "Notion AI" }));
  const reopened = await screen.findByRole("dialog", { name: "구독료 수정" });
  await waitFor(() =>
    expect(
      within(reopened).getByLabelText<HTMLInputElement>("금액 (USD)").value,
    ).toBe("25"),
  );
});

test("없는 구독료 번호로 열면 찾을 수 없다고 알리고 저장 버튼을 두지 않는다", async () => {
  stubInternalBudgetApi({
    subscription: {
      status: 404,
      body: { code: "NOT_FOUND", message: "구독료를 찾을 수 없습니다." },
    },
  });
  renderAt(`${OCTOBER}&subscription=99`);

  const dialog = await screen.findByRole("dialog", { name: "구독료 수정" });
  expect(
    await within(dialog).findByText("구독료를 찾을 수 없어요"),
  ).toBeTruthy();
  expect(within(dialog).queryByRole("button", { name: "저장" })).toBeNull();
  expect(
    within(dialog).queryByRole("button", { name: "다시 시도" }),
  ).toBeNull();
});

test("단건 조회가 실패하면 다시 시도 버튼으로 다시 불러온다", async () => {
  const { replies } = stubInternalBudgetApi({
    subscription: { status: 500, body: {} },
  });
  renderAt(`${OCTOBER}&subscription=2`);

  const dialog = await screen.findByRole("dialog", { name: "구독료 수정" });
  expect(
    await within(dialog).findByText("구독료를 불러오지 못했어요"),
  ).toBeTruthy();
  delete replies.subscription;
  fireEvent.click(within(dialog).getByRole("button", { name: "다시 시도" }));

  expect(await within(dialog).findByText("notion-ai")).toBeTruthy();
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
