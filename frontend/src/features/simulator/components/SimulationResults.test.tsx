// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import type { RunView, SlotView } from "../lib/presentation";
import { SimulationResults } from "./SimulationResults";

afterEach(cleanup);
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
const slot = (overrides: Partial<SlotView> = {}): SlotView => ({
  key: "slot-1",
  name: "테스트 모델",
  provider: "Provider A",
  status: { label: "성공", tone: "green" },
  durationMs: 1234,
  inputTokens: 100,
  outputTokens: 20,
  cost: { kind: "confirmed", amount: "0" },
  jsonValidation: "성공",
  schemaValidation: "실패",
  response: "<script>원문 그대로</script>\n두 번째 줄",
  ...overrides,
});
const run = (slots: SlotView[]): RunView => ({
  key: "run-1",
  status: { label: "부분 성공", tone: "yellow" },
  requestedAt: "2026-10-29T00:00:00Z",
  durationMs: 3000,
  modelCount: 3,
  successCount: 1,
  failureCount: 2,
  confirmedCost: "0",
  estimatedCost: "0.012",
  totalCost: "0.012",
  unknownCostCount: 1,
  slots,
});

test("서버가 합계를 주지 않으면 금액이 있어도 합계를 미확인으로 표시하지 않는다", () => {
  const page = render(
    <SimulationResults
      view={{ kind: "ready", run: { ...run([]), totalCost: null } }}
    />,
  );
  expect(screen.queryByText(/비교 비용 합계/)).toBeNull();
  expect(screen.getByText("추정 포함")).toBeDefined();
  page.rerender(
    <SimulationResults
      view={{
        kind: "ready",
        run: {
          ...run([]),
          confirmedCost: null,
          estimatedCost: null,
          totalCost: null,
        },
      }}
    />,
  );
  expect(screen.getByText(/비교 비용 합계/).textContent).toContain("미확인");
});

test("실행·비용·검증 상태를 독립적으로 표시하고 원문을 보존한다", () => {
  render(
    <SimulationResults
      view={{
        kind: "ready",
        run: run([
          slot(),
          slot({
            key: "slot-2",
            name: "시간 초과 모델",
            status: { label: "시간 초과", tone: "yellow" },
            cost: { kind: "unknown", amount: null },
            response: null,
            jsonValidation: "미실행",
            schemaValidation: "미실행",
          }),
          slot({
            key: "slot-3",
            name: "추정 모델",
            cost: { kind: "estimated", amount: "0.012" },
            schemaValidation: "미적용",
          }),
        ]),
      }}
    />,
  );
  expect(screen.getByText("미확인 1건 미반영")).toBeDefined();
  expect(screen.getAllByText("추정 포함").length).toBeGreaterThan(0);
  expect(screen.getAllByText("$0.0000").length).toBeGreaterThan(0);
  expect(screen.getAllByText("미확인").length).toBeGreaterThan(0);
  expect(screen.getAllByText("미적용").length).toBeGreaterThan(0);
  expect(screen.getAllByText("미실행").length).toBeGreaterThan(0);
  fireEvent.click(
    screen.getByRole("button", {
      name: "테스트 모델 · Provider A 전체 응답 보기",
    }),
  );
  const dialog = screen.getByRole("dialog", {
    name: "테스트 모델 · Provider A 전체 응답",
  });
  expect(within(dialog).getByText(/원문 그대로/).textContent).toBe(
    "<script>원문 그대로</script>\n두 번째 줄",
  );
  expect(dialog.querySelector("script")).toBeNull();
  fireEvent.click(within(dialog).getByRole("button", { name: "닫기" }));
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("취소는 이벤트만 전달하고 서버 상태·비용을 바꾸지 않는다", async () => {
  const cancelAll = vi.fn();
  const cancelSlot = vi.fn();
  const current = run([
    slot({
      status: { label: "진행 중", tone: "grey", ongoing: true },
      cost: { kind: "unknown", amount: null },
    }),
  ]);
  current.status = { label: "진행 중", tone: "grey", ongoing: true };
  render(
    <SimulationResults
      view={{ kind: "ready", run: current }}
      onCancelAll={cancelAll}
      onCancelSlot={cancelSlot}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "전체 취소" }));
  await vi.waitFor(() =>
    expect(
      screen
        .getByRole("button", { name: "테스트 모델 · Provider A 실행 취소" })
        .hasAttribute("disabled"),
    ).toBe(false),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "테스트 모델 · Provider A 실행 취소" }),
  );
  expect(cancelAll).toHaveBeenCalledWith("run-1");
  expect(cancelSlot).toHaveBeenCalledWith("run-1", "slot-1");
  expect(screen.getAllByText("진행 중").length).toBeGreaterThan(0);
  expect(screen.queryByText("취소됨")).toBeNull();
});

test("다시 조회 중에도 기존 결과를 유지하고 정렬은 콜백으로만 전달한다", () => {
  const onSort = vi.fn();
  render(
    <SimulationResults
      view={{ kind: "ready", run: run([slot()]), refreshing: true }}
      sort={{ key: "duration", direction: "asc" }}
      onSort={onSort}
    />,
  );
  expect(screen.getAllByText("테스트 모델").length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: /응답 시간/ }));
  expect(onSort).toHaveBeenCalledWith({ key: "duration", direction: "desc" });
});

test.each(["loading", "error", "empty"] as const)(
  "결과 상태 %s 구분",
  (kind) => {
    render(<SimulationResults view={{ kind }} />);
    expect(
      screen.getByText(
        kind === "loading"
          ? "실행 결과를 불러오고 있습니다"
          : kind === "error"
            ? "실행 결과를 불러오지 못했습니다"
            : "아직 실행 결과가 없습니다",
      ),
    ).toBeDefined();
  },
);
