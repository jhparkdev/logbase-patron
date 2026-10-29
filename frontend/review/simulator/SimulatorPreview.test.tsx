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
  render,
  screen,
  within,
} from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { SimulatorPage } from "../../src/features/simulator/components/SimulatorPage";
import { previewData } from "./preview-data.fixture";
import { SimulatorPreview } from "./SimulatorPreview";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
function renderPage(ui: ReactNode) {
  const router = createRouter({
    routeTree: createRootRoute(),
    history: createMemoryHistory({
      initialEntries: ["/simulator-preview.html"],
    }),
  });
  return render(ui, {
    wrapper: ({ children }) => (
      <RouterContextProvider router={router}>{children}</RouterContextProvider>
    ),
  });
}

test("P-04의 입력·모델 선택·결과를 같은 mock 실행 한 건으로 채운다", () => {
  renderPage(<SimulatorPreview />);
  expect(
    screen.getByRole("heading", { name: "AI 모델 시뮬레이터", level: 1 }),
  ).toBeDefined();
  expect((screen.getByLabelText("Prompt") as HTMLTextAreaElement).value).toBe(
    previewData.initialValues.prompt,
  );
  expect(
    (screen.getByLabelText("입력 텍스트 (선택사항)") as HTMLTextAreaElement)
      .value,
  ).toBe(previewData.initialValues.text);
  for (const [index, key] of previewData.initialValues.selections.entries()) {
    expect(
      (screen.getByLabelText(`비교 모델 ${index + 1}`) as HTMLSelectElement)
        .value,
    ).toBe(key);
  }
  expect(
    screen.getByRole("heading", { name: "시뮬레이션 결과 요약" }),
  ).toBeDefined();
  expect(screen.getByText(/2026-10-22 10:00:00/)).toBeDefined();
  expect(screen.queryByLabelText("검토할 실행")).toBeNull();
  expect(screen.queryByLabelText("실행 상태")).toBeNull();
  expect(screen.queryByRole("button", { name: "다음 기록" })).toBeNull();
});

test("편집과 전체 응답 열기는 가능하고 실행·DB 호출은 하지 않는다", () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  const original = JSON.stringify(previewData.run);
  renderPage(<SimulatorPreview />);
  fireEvent.change(screen.getByLabelText("Prompt"), {
    target: { value: "입력 편집 확인" },
  });
  expect(
    screen.getByRole("button", { name: "비교 실행" }).hasAttribute("disabled"),
  ).toBe(true);
  const slot = previewData.run.slots[0];
  fireEvent.click(
    screen.getByRole("button", {
      name: `${slot.name} · ${slot.provider} 전체 응답 보기`,
    }),
  );
  const dialog = screen.getByRole("dialog", {
    name: `${slot.name} · ${slot.provider} 전체 응답`,
  });
  expect(dialog.querySelector("pre")?.textContent).toBe(slot.response);
  fireEvent.click(within(dialog).getByRole("button", { name: "닫기" }));
  expect(fetch).not.toHaveBeenCalled();
  expect(JSON.stringify(previewData.run)).toBe(original);
});

test("고급 설정은 기본 접힘이고 저장된 설정을 표시한다", () => {
  renderPage(<SimulatorPreview />);
  const toggle = screen.getByRole("button", { name: /고급 설정/ });
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(toggle);
  expect((screen.getByLabelText("Temperature") as HTMLInputElement).value).toBe(
    "0.3",
  );
  expect(
    (screen.getByLabelText("최대 출력 토큰") as HTMLInputElement).value,
  ).toBe("512");
});

test("미리보기를 열어도 실제 서비스 페이지의 초기 데이터는 바뀌지 않는다", () => {
  const preview = renderPage(<SimulatorPreview />);
  preview.unmount();
  renderPage(<SimulatorPage />);
  expect((screen.getByLabelText("Prompt") as HTMLTextAreaElement).value).toBe(
    "",
  );
  expect(
    (screen.getByLabelText("입력 텍스트 (선택사항)") as HTMLTextAreaElement)
      .value,
  ).toBe("");
  expect(screen.getByText("아직 실행 결과가 없어요")).toBeDefined();
});
