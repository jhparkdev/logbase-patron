// @vitest-environment jsdom
import {
  createMemoryHistory,
  createRootRoute,
  createRouter,
  RouterContextProvider,
} from "@tanstack/react-router";
import {
  cleanup,
  fireEvent,
  render as renderDom,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import type { HistoryDetailView, HistoryRow } from "../lib/presentation";
import { historySearchSchema } from "../lib/search";
import { HistoryPage } from "./HistoryPage";

function render(ui: ReactNode) {
  const router = createRouter({
    routeTree: createRootRoute(),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  return renderDom(ui, {
    wrapper: ({ children }) => (
      <RouterContextProvider router={router}>{children}</RouterContextProvider>
    ),
  });
}

afterEach(cleanup);
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
const search = historySearchSchema.parse({
  from: "2026-10-01",
  to: "2026-10-30",
});
const row: HistoryRow = {
  key: "run-1",
  requestedAt: "2026-10-22T01:00:00Z",
  scenario: "기존 시나리오",
  modelCount: 3,
  status: { label: "일부 성공", tone: "yellow" },
  cost: { total: "0.125", estimated: true, unknownCount: 1, checking: false },
  inactiveModelCount: 1,
};
const detail: HistoryDetailView = {
  key: row.key,
  input: {
    kind: "available",
    prompt: "과거 Prompt 원문",
    text: "저장한 입력",
    schema: "{}",
    attachments: [],
  },
  settings: [{ label: "Temperature", value: "0.3" }],
  models: [
    {
      key: "a:p",
      name: "비활성 모델",
      provider: "p",
      currentState: "inactive",
    },
  ],
};

test("API 미연결 상태와 실제 조회 결과 없음은 구분하고 페이지네이션은 렌더링하지 않는다", () => {
  const first = render(<HistoryPage search={search} onSearch={vi.fn()} />);
  expect(screen.getByText("이력 조회를 준비하고 있어요")).toBeDefined();
  expect(screen.queryByText("조건에 맞는 실행 이력이 없어요")).toBeNull();
  expect(screen.queryByRole("navigation", { name: /페이지/ })).toBeNull();
  first.unmount();
  render(
    <HistoryPage
      search={search}
      onSearch={vi.fn()}
      view={{ kind: "ready", items: [], total: 0 }}
    />,
  );
  expect(screen.getByText("조건에 맞는 실행 이력이 없어요")).toBeDefined();
});

test("공통 페이지 이동으로 서버 행을 유지하고 페이지와 선택 상태를 갱신한다", () => {
  const onSearch = vi.fn();
  render(
    <HistoryPage
      search={{ ...search, page: 2, selected: row.key }}
      onSearch={onSearch}
      view={{ kind: "ready", items: [row], total: 12 }}
    />,
  );
  expect(screen.getByRole("button", { name: row.key })).toBeDefined();
  const pagination = within(screen.getByRole("navigation", { name: "페이지" }));
  expect(
    pagination.getByRole("button", { name: "2" }).getAttribute("aria-current"),
  ).toBe("page");
  expect(
    pagination
      .getByRole("button", { name: "다음 페이지" })
      .hasAttribute("disabled"),
  ).toBe(true);
  fireEvent.click(pagination.getByRole("button", { name: "이전 페이지" }));
  expect(onSearch).toHaveBeenCalledWith({
    ...search,
    page: 1,
    selected: undefined,
    detail: false,
  });
});

test("두 번째 페이지에서 조회하면 첫 페이지로 돌아간다", async () => {
  const onSearch = vi.fn();
  render(<HistoryPage search={{ ...search, page: 2 }} onSearch={onSearch} />);
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() =>
    expect(onSearch).toHaveBeenCalledWith(expect.objectContaining({ page: 1 })),
  );
});
test("필터는 조회할 때 제출하고 역전된 날짜를 입력하면 URL 변경을 막는다", async () => {
  const onSearch = vi.fn();
  render(<HistoryPage search={search} onSearch={onSearch} />);
  fireEvent.change(screen.getByLabelText("조회 시작일"), {
    target: { value: "2026-10-31" },
  });
  expect(onSearch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  expect(
    await screen.findByText("시작일은 종료일보다 늦을 수 없어요."),
  ).toBeDefined();
  expect(onSearch).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("조회 시작일"), {
    target: { value: "2026-10-01" },
  });
  fireEvent.change(screen.getByLabelText("Simulation ID"), {
    target: { value: " run-1 " },
  });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() =>
    expect(onSearch).toHaveBeenCalledWith(
      expect.objectContaining({
        simulationId: "run-1",
        selected: undefined,
        detail: false,
      }),
    ),
  );
});
test("서버가 준 순서를 유지하며 모든 데이터 열의 정렬 요청을 전달한다", () => {
  const onSearch = vi.fn();
  render(
    <HistoryPage
      search={search}
      onSearch={onSearch}
      view={{
        kind: "ready",
        items: [
          row,
          { ...row, key: "run-2", requestedAt: "2026-10-23T01:00:00Z" },
        ],
        total: 12,
      }}
    />,
  );
  const rows = screen.getAllByRole("row");
  expect(within(rows[1]).getByRole("button", { name: "run-1" })).toBeDefined();
  for (const label of [
    "실행 시각",
    "Simulation ID",
    "시나리오",
    "모델 수",
    "실행 상태",
    "비용 상태",
    "총 비용 (USD)",
  ]) {
    fireEvent.click(screen.getByRole("button", { name: `${label} 정렬` }));
  }
  expect(onSearch).toHaveBeenCalledTimes(7);
  expect(onSearch).toHaveBeenLastCalledWith(
    expect.objectContaining({ sort: "totalCost", direction: "asc" }),
  );
  expect(within(rows[1]).getByText("추정 포함")).toBeDefined();
  expect(within(rows[1]).getByText("미확인 1건 미반영")).toBeDefined();
});
test("시나리오·모델·상태의 복합 선택을 조회 조건으로 전달한다", async () => {
  const onSearch = vi.fn();
  render(
    <HistoryPage
      search={search}
      onSearch={onSearch}
      scenarios={[{ key: "3", name: "데이터 요약" }]}
      models={[{ key: "a:p", name: "모델 A" }]}
    />,
  );
  fireEvent.change(screen.getByRole("combobox", { name: "시나리오" }), {
    target: { value: "3" },
  });
  fireEvent.change(screen.getByRole("combobox", { name: "모델" }), {
    target: { value: "a:p" },
  });
  fireEvent.change(screen.getByRole("combobox", { name: "실행 상태" }), {
    target: { value: "SUCCESS" },
  });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() =>
    expect(onSearch).toHaveBeenCalledWith(
      expect.objectContaining({
        scenario: "3",
        model: "a:p",
        status: "SUCCESS",
      }),
    ),
  );
});
test("상세 열기와 닫기는 검색·정렬 조건을 유지한다", () => {
  const onSearch = vi.fn();
  const props = {
    search,
    onSearch,
    view: { kind: "ready" as const, items: [row], total: 1 },
  };
  const page = render(<HistoryPage {...props} />);
  fireEvent.click(screen.getByRole("button", { name: "run-1" }));
  expect(onSearch).toHaveBeenLastCalledWith({
    ...search,
    selected: row.key,
    detail: true,
  });
  page.rerender(
    <HistoryPage
      {...props}
      search={{ ...search, selected: row.key, detail: true }}
      detail={{ kind: "ready", value: detail }}
    />,
  );
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", { name: "닫기" }),
  );
  expect(onSearch).toHaveBeenLastCalledWith({
    ...search,
    selected: row.key,
    detail: false,
  });
});
test("실행 상세 우상단 닫기 버튼도 검색 조건과 선택한 실행을 유지한다", () => {
  const onSearch = vi.fn();
  const selectedSearch = { ...search, selected: row.key, detail: true };
  render(
    <HistoryPage
      search={selectedSearch}
      onSearch={onSearch}
      detail={{ kind: "ready", value: detail }}
    />,
  );
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", { name: "창 닫기" }),
  );
  expect(onSearch).toHaveBeenCalledWith({ ...selectedSearch, detail: false });
});
test("당시 입력과 설정을 표시하고 재실행은 명시적 선택 후에만 요청한다", () => {
  const onRerun = vi.fn();
  render(
    <HistoryPage
      search={{ ...search, selected: row.key, detail: true }}
      onSearch={vi.fn()}
      view={{ kind: "ready", items: [row], total: 1 }}
      detail={{ kind: "ready", value: detail }}
      onRerun={onRerun}
      renderResults={() => <p>원본 모델 결과</p>}
    />,
  );
  const dialog = within(screen.getByRole("dialog"));
  expect(dialog.getByText("과거 Prompt 원문")).toBeDefined();
  expect(dialog.getByText("저장한 입력")).toBeDefined();
  expect(dialog.getByText("0.3")).toBeDefined();
  expect(dialog.getByText("원본 모델 결과")).toBeDefined();
  expect(onRerun).not.toHaveBeenCalled();
  fireEvent.click(
    dialog.getByRole("button", { name: "이 조건으로 다시 준비" }),
  );
  expect(onRerun).toHaveBeenCalledWith(row.key);
});
test("재실행 원본이 누락되었거나 다른 ID의 상세 응답이면 잘못된 원문을 표시하지 않는다", () => {
  const props = {
    search: { ...search, selected: row.key, detail: true },
    onSearch: vi.fn(),
    onRerun: vi.fn(),
  };
  const page = render(
    <HistoryPage
      {...props}
      detail={{
        kind: "ready",
        value: { ...detail, input: { kind: "missing" } },
      }}
    />,
  );
  expect(
    screen
      .getByRole("button", { name: "이 조건으로 다시 준비" })
      .hasAttribute("disabled"),
  ).toBe(true);
  expect(
    screen.getByText("저장된 입력을 확인할 수 없어 재실행할 수 없어요."),
  ).toBeDefined();
  page.rerender(
    <HistoryPage
      {...props}
      detail={{ kind: "ready", value: { ...detail, key: "old-run" } }}
    />,
  );
  expect(screen.queryByText("과거 Prompt 원문")).toBeNull();
});
