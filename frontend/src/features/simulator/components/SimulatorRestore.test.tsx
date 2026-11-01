// @vitest-environment jsdom
import {
  createMemoryHistory,
  createRootRoute,
  createRouter,
  RouterContextProvider,
} from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeAll, expect, test } from "vitest";
import { createComparisons } from "../lib/comparisons";
import { createDefaultValues } from "../lib/form";
import { dbMock } from "./dbMock.fixture";
import { SimulatorRestore } from "./SimulatorRestore";

afterEach(cleanup);
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
function show(ui: ReactNode) {
  const router = createRouter({
    routeTree: createRootRoute(),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  return render(ui, {
    wrapper: ({ children }) => (
      <RouterContextProvider router={router}>{children}</RouterContextProvider>
    ),
  });
}
test("API 미연결 상태에서는 복원 성공으로 표시하거나 빈 폼에서 실행하지 않는다", () => {
  show(<SimulatorRestore sourceKey="run-1" />);
  expect(
    screen.getByText("재실행 조건 불러오기를 준비하고 있습니다"),
  ).toBeDefined();
  expect(screen.queryByLabelText("Prompt")).toBeNull();
});
test("원문과 파라미터를 P-04에 복원하고 원본 결과 없이 새 비교를 준비한다", () => {
  const source = createDefaultValues({
    prompt: "저장한 Prompt",
    text: "저장한 자료",
    temperature: "0.3",
    maxTokens: "512",
    comparisons: createComparisons(
      dbMock.choices
        .filter((m) => m.selectable)
        .slice(0, 2)
        .map((m) => m.key),
    ),
  });
  const page = show(
    <SimulatorRestore
      sourceKey="run-1"
      view={{
        kind: "ready",
        key: "run-1",
        values: source,
        choices: dbMock.choices,
        scenarios: dbMock.scenarios,
      }}
    />,
  );
  expect((screen.getByLabelText("Prompt") as HTMLTextAreaElement).value).toBe(
    "저장한 Prompt",
  );
  fireEvent.click(screen.getByRole("button", { name: /^공통 설정 선택사항$/ }));
  expect(
    (screen.getByLabelText("공통 Temperature") as HTMLInputElement).value,
  ).toBe("0.3");
  expect(screen.getByText("아직 실행 결과가 없습니다")).toBeDefined();
  expect(
    screen.getByRole("button", { name: "비교 실행" }).hasAttribute("disabled"),
  ).toBe(true);
  page.rerender(
    <SimulatorRestore
      sourceKey="run-2"
      view={{
        kind: "ready",
        key: "run-1",
        values: source,
        choices: dbMock.choices,
        scenarios: dbMock.scenarios,
      }}
    />,
  );
  expect(screen.queryByLabelText("Prompt")).toBeNull();
});
