// @vitest-environment jsdom
import {
  createMemoryHistory,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { historyPreviewTree } from "./routes";

afterEach(cleanup);
beforeAll(() => {
  window.scrollTo = vi.fn();
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
const runKey = "01a1611f-3e80-73c5-a130-3efa5a1f75de";
function show() {
  const router = createRouter({
    routeTree: historyPreviewTree,
    history: createMemoryHistory({
      initialEntries: ["/simulation-history-preview.html"],
    }),
  });
  render(<RouterProvider router={router} />);
  return router;
}
test("기존 12개 실행을 표시하고 상세에서 당시 원문과 모델별 결과를 확인한다", async () => {
  const fetch = vi.spyOn(globalThis, "fetch");
  show();
  fireEvent.click(await screen.findByRole("button", { name: runKey }));
  const dialog = within(
    await screen.findByRole("dialog", { name: "시뮬레이션 실행 상세" }),
  );
  expect(dialog.getByText(/린넨 셔츠 원피스/)).toBeDefined();
  expect(dialog.getByText("당시 입력과 설정")).toBeDefined();
  expect(
    dialog.getByRole("heading", { name: "시뮬레이션 결과 요약" }),
  ).toBeDefined();
  expect(fetch).not.toHaveBeenCalled();
  fetch.mockRestore();
});
test("다시 준비하면 원문은 URL에 넣지 않고 P-04 폼으로 복원한다", async () => {
  const router = show();
  fireEvent.click(await screen.findByRole("button", { name: runKey }));
  fireEvent.click(
    within(await screen.findByRole("dialog")).getByRole("button", {
      name: "이 조건으로 다시 준비",
    }),
  );
  const prompt = await screen.findByLabelText("Prompt");
  expect((prompt as HTMLTextAreaElement).value).toContain(
    "다음 데이터를 5줄 이내로 요약하세요.",
  );
  expect(
    (screen.getByLabelText(/입력 텍스트/) as HTMLTextAreaElement).value,
  ).toContain("린넨 셔츠 원피스");
  expect(router.state.location.search).toMatchObject({ rerun: runKey });
  expect(router.state.location.href).not.toContain("린넨");
  expect(screen.getByText("아직 실행 결과가 없어요")).toBeDefined();
  expect(
    screen.getByRole("button", { name: "비교 실행" }).hasAttribute("disabled"),
  ).toBe(true);
});
test("예시의 필터 변경과 브라우저 뒤로가기를 반영한다", async () => {
  const router = show();
  await screen.findByRole("button", { name: runKey });
  fireEvent.change(screen.getByLabelText("Simulation ID"), {
    target: { value: runKey },
  });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      simulationId: runKey,
    }),
  );
  expect(screen.getAllByRole("row")).toHaveLength(2);
  router.history.back();
  await waitFor(() => expect(screen.getAllByRole("row")).toHaveLength(13));
  expect(
    (screen.getByLabelText("Simulation ID") as HTMLInputElement).value,
  ).toBe("");
});
test("숫자로만 된 시나리오 ID도 문자열로 유지해 다른 조건과 함께 조회한다", async () => {
  const router = show();
  await screen.findByRole("button", { name: runKey });
  fireEvent.change(screen.getByRole("combobox", { name: "시나리오" }), {
    target: { value: "3" },
  });
  fireEvent.change(screen.getByRole("combobox", { name: "실행 상태" }), {
    target: { value: "SUCCESS" },
  });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      scenario: "3",
      status: "SUCCESS",
    }),
  );
  expect(screen.getAllByRole("row")).toHaveLength(3);
});
