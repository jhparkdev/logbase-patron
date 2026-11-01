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
function show(path = "/simulation-history-preview.html") {
  const router = createRouter({
    routeTree: historyPreviewTree,
    history: createMemoryHistory({
      initialEntries: [path],
    }),
  });
  render(<RouterProvider router={router} />);
  return router;
}

function currentMenu() {
  return within(screen.getByRole("navigation", { name: "주 메뉴" }))
    .getAllByRole("link")
    .filter((link) => link.getAttribute("aria-current") === "page")
    .map((link) => link.textContent);
}

test("10건씩 페이지를 나누고 주소·뒤로가기와 상세 닫기에 현재 페이지를 보존한다", async () => {
  const router = show();
  const pagination = within(
    await screen.findByRole("navigation", { name: "페이지" }),
  );
  expect(screen.getAllByRole("row")).toHaveLength(11);
  expect(
    pagination
      .getByRole("button", { name: "이전 페이지" })
      .hasAttribute("disabled"),
  ).toBe(true);
  const firstKeys = screen
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("button")[0].textContent);
  fireEvent.click(pagination.getByRole("button", { name: "다음 페이지" }));
  await waitFor(() => expect(router.state.location.search.page).toBe(2));
  expect(screen.getAllByRole("row")).toHaveLength(3);
  const run = within(screen.getAllByRole("row")[1]).getAllByRole("button")[0];
  expect(firstKeys).not.toContain(run.textContent);
  expect(
    pagination.getByRole("button", { name: "2" }).getAttribute("aria-current"),
  ).toBe("page");
  expect(
    pagination
      .getByRole("button", { name: "다음 페이지" })
      .hasAttribute("disabled"),
  ).toBe(true);
  fireEvent.click(run);
  const dialog = await screen.findByRole("dialog");
  fireEvent.click(within(dialog).getByRole("button", { name: "닫기" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(router.state.location.search).toMatchObject({
    page: 2,
    detail: false,
  });
  router.history.back();
  await screen.findByRole("dialog");
  router.history.back();
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  router.history.back();
  await waitFor(() => expect(router.state.location.search.page).toBe(1));
  expect(screen.getAllByRole("row")).toHaveLength(11);
});

test("두 번째 페이지에서 정렬·검색하면 첫 페이지로 돌아가고 뒤로가기로 복원한다", async () => {
  const router = show("/simulation-history-preview.html?page=2");
  const sort = await screen.findByRole("button", { name: "모델 수 정렬" });
  expect(screen.getAllByRole("row")).toHaveLength(3);
  fireEvent.click(sort);
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      page: 1,
      sort: "modelCount",
      direction: "asc",
    }),
  );
  router.history.back();
  await waitFor(() => expect(router.state.location.search.page).toBe(2));
  fireEvent.change(screen.getByRole("combobox", { name: "실행 상태" }), {
    target: { value: "FAILED" },
  });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      page: 1,
      status: "FAILED",
    }),
  );
  expect(screen.getAllByRole("row")).toHaveLength(2);
  router.history.back();
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      page: 2,
      status: "all",
    }),
  );
  expect(screen.getAllByRole("row")).toHaveLength(3);
});

test.each([
  ["page=999", 2, 3],
  ["page=999&status=FAILED", 1, 2],
  ["page=999&simulationId=00000000-0000-7000-8000-000000000000", 1, 0],
])("결과 범위를 벗어난 페이지를 보정한다: %s", async (query, page, rows) => {
  const router = show(`/simulation-history-preview.html?${query}`);
  await screen.findByRole("heading", {
    name: "시뮬레이션 결과 이력",
    level: 1,
  });
  await waitFor(() => expect(router.state.location.search.page).toBe(page));
  expect(screen.queryAllByRole("row")).toHaveLength(rows);
});

test.each([
  ["실행 시각", "requestedAt"],
  ["Simulation ID", "id"],
  ["시나리오", "scenario"],
  ["모델 수", "modelCount"],
  ["실행 상태", "status"],
  ["비용 상태", "costStatus"],
])(
  "%s 정렬 방향을 바꿔도 화면 상단으로 이동하지 않고 버튼 포커스를 유지한다",
  async (label, sort) => {
    const router = show();
    const button = await screen.findByRole("button", { name: `${label} 정렬` });
    await waitFor(() => expect(router.state.status).toBe("idle"));
    for (const direction of ["asc", "desc"]) {
      vi.mocked(window.scrollTo).mockClear();
      button.focus();
      fireEvent.click(button);
      await waitFor(() => {
        expect(router.state.location.search).toMatchObject({ sort, direction });
        expect(button.closest("th")?.getAttribute("aria-sort")).toBe(
          direction === "asc" ? "ascending" : "descending",
        );
      });
      expect(window.scrollTo).not.toHaveBeenCalled();
      expect(document.activeElement).toBe(button);
    }
  },
);

test("다시 준비로 화면이 바뀔 때는 상단에서 시작한다", async () => {
  show();
  fireEvent.click(await screen.findByRole("button", { name: runKey }));
  const dialog = await screen.findByRole("dialog");
  vi.mocked(window.scrollTo).mockClear();
  fireEvent.click(
    within(dialog).getByRole("button", { name: "이 조건으로 다시 준비" }),
  );
  await screen.findByLabelText("Prompt");
  expect(window.scrollTo).toHaveBeenCalledWith(
    expect.objectContaining({ top: 0, left: 0 }),
  );
});

test("이력과 다시 준비 화면, 돌아가기와 브라우저 이동에 맞춰 메뉴를 선택한다", async () => {
  const router = show();
  fireEvent.click(await screen.findByRole("button", { name: runKey }));
  expect(currentMenu()).toEqual(["시뮬레이션 결과 이력"]);
  fireEvent.click(
    within(await screen.findByRole("dialog")).getByRole("button", {
      name: "이 조건으로 다시 준비",
    }),
  );
  await screen.findByLabelText("Prompt");
  expect(currentMenu()).toEqual(["AI 모델 시뮬레이터"]);
  fireEvent.click(screen.getByRole("button", { name: "이력으로 돌아가기" }));
  await screen.findByRole("dialog");
  expect(currentMenu()).toEqual(["시뮬레이션 결과 이력"]);
  router.history.back();
  await screen.findByLabelText("Prompt");
  expect(currentMenu()).toEqual(["AI 모델 시뮬레이터"]);
  router.history.forward();
  await screen.findByRole("dialog");
  expect(currentMenu()).toEqual(["시뮬레이션 결과 이력"]);
});

test("다시 준비 주소로 직접 진입해도 시뮬레이터 메뉴를 선택한다", async () => {
  show(`/simulation-history-preview.html?rerun=${runKey}`);
  await screen.findByLabelText("Prompt");
  expect(currentMenu()).toEqual(["AI 모델 시뮬레이터"]);
});
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
  expect(screen.getByText("아직 실행 결과가 없습니다")).toBeDefined();
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
  await waitFor(() => expect(screen.getAllByRole("row")).toHaveLength(11));
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
