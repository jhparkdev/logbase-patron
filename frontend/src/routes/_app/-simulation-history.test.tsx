// @vitest-environment jsdom
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { renderAt } from "../../test/renderAt";

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

test("실제 이력 화면의 조회 조건을 바꿔도 스크롤을 초기화하지 않는다", async () => {
  const router = renderAt("/simulation-history?page=2");
  const filter = await screen.findByLabelText("Simulation ID");
  await waitFor(() => expect(router.state.status).toBe("idle"));
  fireEvent.change(filter, { target: { value: "run-1" } });
  const button = screen.getByRole("button", { name: "조회" });
  vi.mocked(window.scrollTo).mockClear();
  fireEvent.click(button);
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      simulationId: "run-1",
      page: 1,
    }),
  );
  expect(window.scrollTo).not.toHaveBeenCalled();
});
test("주소로 복원한 상세를 닫아도 조회 기간·필터·정렬·선택 ID를 유지한다", async () => {
  const router = renderAt(
    "/simulation-history?from=2026-10-01&to=2026-10-29&status=FAILED&sort=totalCost&direction=asc&page=2&selected=run-1&detail=true",
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
      page: 2,
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
  const router = renderAt("/simulator?sourceRun=run-1");
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
