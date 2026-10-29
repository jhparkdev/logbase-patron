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
} from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { routeTree } from "../../routeTree.gen";

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
function show(path: string) {
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(<RouterProvider router={router} />);
  return router;
}
test("주소로 복원한 상세를 닫아도 조회 기간·필터·정렬·선택 ID를 유지한다", async () => {
  const router = show(
    "/simulation-history?from=2026-10-01&to=2026-10-29&status=FAILED&sort=totalCost&direction=asc&selected=run-1&detail=true",
  );
  await screen.findByRole("dialog", { name: "시뮬레이션 실행 상세" });
  fireEvent.click(screen.getByRole("button", { name: "닫기" }));
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      from: "2026-10-01",
      to: "2026-10-29",
      status: "FAILED",
      sort: "totalCost",
      direction: "asc",
      selected: "run-1",
      detail: false,
    }),
  );
  expect((screen.getByLabelText("조회 시작일") as HTMLInputElement).value).toBe(
    "2026-10-01",
  );
  expect(screen.getByText("이력 조회를 준비하고 있어요")).toBeDefined();
});
test("서비스의 재실행 주소에는 원본 ID만 전달하고 API가 없으면 복원 완료로 표시하지 않는다", async () => {
  const router = show("/simulator?sourceRun=run-1");
  expect(
    await screen.findByText("재실행 조건 불러오기를 준비하고 있어요"),
  ).toBeDefined();
  expect(screen.queryByLabelText("Prompt")).toBeNull();
  fireEvent.click(screen.getByRole("link", { name: "새 조건으로 준비하기" }));
  await waitFor(() =>
    expect(router.state.location.search.sourceRun).toBeUndefined(),
  );
  expect(await screen.findByLabelText("Prompt")).toBeDefined();
});
