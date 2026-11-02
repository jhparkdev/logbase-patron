// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { DETAIL, stubModelsApi, UNPRICED_DETAIL } from "../../test/modelsApi";
import { renderAt } from "../../test/renderAt";

const TABLE = "등록된 AI 모델";
const INACTIVE_DETAIL = {
  ...DETAIL,
  status: "INACTIVE",
  deactivated_at: "2026-11-01T01:00:00Z",
};

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
});

afterEach(() => vi.restoreAllMocks());

async function openPanel(path: string, name: string) {
  renderAt(path);
  return within(await screen.findByRole("dialog", { name }));
}

const buttonNames = (panel: ReturnType<typeof within>) =>
  panel
    .queryAllByRole("button")
    .map((button: HTMLElement) => button.textContent)
    .filter(
      (text: string | null) => text === "사용 시작" || text === "사용 중단",
    );

const patches = (requests: { url: URL; method: string; body: unknown }[]) =>
  requests.filter(({ method }) => method === "PATCH");

test("사용 중인 모델은 사용 중단 버튼만 보인다", async () => {
  stubModelsApi();
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  expect(buttonNames(panel)).toEqual(["사용 중단"]);
});

test("검증 중인 모델은 사용 시작과 사용 중단을 모두 고를 수 있다", async () => {
  stubModelsApi({ detail: { status: 200, body: UNPRICED_DETAIL } });
  const panel = await openPanel("/models?model=4", "Mistral Small");

  expect(buttonNames(panel)).toEqual(["사용 시작", "사용 중단"]);
});

test("사용 중단된 모델은 사용 시작 버튼만 보인다", async () => {
  stubModelsApi({ detail: { status: 200, body: INACTIVE_DETAIL } });
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  expect(buttonNames(panel)).toEqual(["사용 시작"]);
});

test("버튼을 누르면 확인창이 열리고 확인하기 전에는 요청하지 않는다", async () => {
  const { requests } = stubModelsApi();
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  fireEvent.click(panel.getByRole("button", { name: "사용 중단" }));

  const dialog = within(screen.getByRole("dialog", { name: "사용 중단" }));
  expect(
    dialog.getByText(/“GPT-4o mini” 모델을 사용 중단할까요\?/),
  ).toBeTruthy();
  expect(patches(requests)).toHaveLength(0);
});

test("확인하면 상태를 바꾸고, 창을 닫고, 응답으로 패널을 갱신하며, 목록을 다시 불러온다", async () => {
  const { requests } = stubModelsApi({
    status: { status: 200, body: INACTIVE_DETAIL },
  });
  const panel = await openPanel("/models?model=3", "GPT-4o mini");
  await screen.findByRole("table", { name: TABLE });
  const listRequests = () =>
    requests.filter(({ url }) => url.pathname === "/api/models").length;
  const before = listRequests();

  fireEvent.click(panel.getByRole("button", { name: "사용 중단" }));
  const dialog = within(screen.getByRole("dialog", { name: "사용 중단" }));
  fireEvent.click(dialog.getByRole("button", { name: "사용 중단" }));

  await waitFor(() =>
    expect(screen.queryByRole("dialog", { name: "사용 중단" })).toBeNull(),
  );
  expect(patches(requests)).toHaveLength(1);
  expect(patches(requests)[0].url.pathname).toBe("/api/models/3/status");
  expect(patches(requests)[0].body).toEqual({ status: "INACTIVE" });
  expect(buttonNames(panel)).toEqual(["사용 시작"]);
  expect(panel.getByText("2026-11-01 10:00:00")).toBeTruthy();
  await waitFor(() => expect(listRequests()).toBe(before + 1));
});

test("서버가 거절하면 서버 문구를 창 안에 보여 주고 상태는 그대로다", async () => {
  stubModelsApi({
    detail: { status: 200, body: UNPRICED_DETAIL },
    status: {
      status: 409,
      body: {
        code: "TEST_NOT_PASSED",
        message: "24시간 안에 성공한 연결 테스트가 없어 바꿀 수 없습니다.",
      },
    },
  });
  const panel = await openPanel("/models?model=4", "Mistral Small");

  fireEvent.click(panel.getByRole("button", { name: "사용 시작" }));
  const dialog = within(screen.getByRole("dialog", { name: "사용 시작" }));
  fireEvent.click(dialog.getByRole("button", { name: "사용 시작" }));

  expect((await dialog.findByRole("alert")).textContent).toBe(
    "24시간 안에 성공한 연결 테스트가 없어 바꿀 수 없습니다.",
  );
  expect(buttonNames(panel)).toContain("사용 시작");
  expect(panel.getByText("검증 중")).toBeTruthy();
});

test("닫기를 누르면 요청 없이 창이 닫힌다", async () => {
  const { requests } = stubModelsApi();
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  fireEvent.click(panel.getByRole("button", { name: "사용 중단" }));
  const dialog = within(screen.getByRole("dialog", { name: "사용 중단" }));
  fireEvent.click(dialog.getByRole("button", { name: "닫기" }));

  await waitFor(() =>
    expect(screen.queryByRole("dialog", { name: "사용 중단" })).toBeNull(),
  );
  expect(patches(requests)).toHaveLength(0);
});
