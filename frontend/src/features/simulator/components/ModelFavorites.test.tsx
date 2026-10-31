// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import type { ModelFavoritesView } from "../lib/favorites";
import type { ModelChoice } from "../lib/presentation";
import { ModelPickerDialog } from "./ModelPickerDialog";

const choices: ModelChoice[] = [0, 1, 2].map((index) => ({
  key: `a:p${index}`,
  name: "모델 A",
  provider: `Provider ${index}`,
  selectable: index !== 2,
  supportsImages: false,
  supportedParameters: [],
  creator: "mistralai",
}));
const onApply = vi.fn();
const onClose = vi.fn();
function picker(favorites?: ModelFavoritesView) {
  return (
    <ModelPickerDialog
      choices={choices}
      selections={["a:p0", "a:p1"]}
      unavailable={false}
      favorites={favorites}
      onApply={onApply}
      onClose={onClose}
    />
  );
}
function favoriteList() {
  fireEvent.click(screen.getByRole("button", { name: "즐겨찾기 목록" }));
}
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});

test("즐겨찾기는 모델·Provider별로 구별하며 저장 이벤트와 비교 선택을 분리한다", () => {
  const onSet = vi.fn();
  const page = render(picker({ kind: "ready", keys: [], onSet }));
  fireEvent.click(
    screen.getByRole("button", { name: "모델 A · Provider 0 즐겨찾기" }),
  );
  expect(onSet).toHaveBeenCalledWith("a:p0", true);
  expect(onApply).not.toHaveBeenCalled();
  // 상태는 외부 저장 담당자가 전달한다. 이벤트만으로 저장 성공을 만들지 않는다.
  expect(
    screen
      .getByRole("button", { name: "모델 A · Provider 0 즐겨찾기" })
      .getAttribute("aria-pressed"),
  ).toBe("false");
  page.rerender(picker({ kind: "ready", keys: ["a:p0"], onSet }));
  favoriteList();
  expect(screen.getAllByRole("checkbox")).toHaveLength(1);
  expect(
    screen.getByRole("checkbox", { name: "모델 A · Provider 0" }),
  ).toBeDefined();
  fireEvent.click(
    screen.getByRole("button", { name: "모델 A · Provider 0 즐겨찾기" }),
  );
  expect(onSet).toHaveBeenLastCalledWith("a:p0", false);
  page.rerender(picker({ kind: "ready", keys: [], onSet }));
  expect(screen.getByText("아직 즐겨찾기한 모델이 없습니다")).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "선택 적용" }));
  expect(onApply).toHaveBeenCalledWith(["a:p0", "a:p1"]);
});

test("같은 제작사의 여러 실행 Provider는 같은 배지로 구분하며 Provider 이름은 유지한다", () => {
  render(picker());
  const badges = screen.getAllByText("mistralai");
  expect(badges.length).toBeGreaterThanOrEqual(choices.length);
  expect(new Set(badges.map((badge) => badge.className)).size).toBe(1);
  for (const choice of choices)
    expect(screen.getByText(choice.provider)).toBeDefined();
});

test("즐겨찾기 목록에서도 검색하고 결과 없음과 빈 즐겨찾기를 구분한다", async () => {
  render(picker({ kind: "ready", keys: ["a:p0", "a:p1"], onSet: vi.fn() }));
  favoriteList();
  fireEvent.change(screen.getByRole("searchbox"), {
    target: { value: "Provider 1" },
  });
  await screen.findByText("검색 결과 1개");
  expect(screen.getAllByRole("checkbox")).toHaveLength(1);
  fireEvent.change(screen.getByRole("searchbox"), {
    target: { value: "없는 모델" },
  });
  expect(await screen.findByText("검색 결과가 없습니다")).toBeDefined();
  expect(screen.queryByText("아직 즐겨찾기한 모델이 없습니다")).toBeNull();
});

test("저장 중인 즐겨찾기만 비활성화하고 비교 선택과 다른 즐겨찾기는 유지한다", () => {
  const onSet = vi.fn();
  render(picker({ kind: "ready", keys: [], savingKeys: ["a:p0"], onSet }));
  const saving = screen.getByRole("button", {
    name: "모델 A · Provider 0 즐겨찾기",
  });
  expect(saving.hasAttribute("disabled")).toBe(true);
  expect(saving.getAttribute("aria-busy")).toBe("true");
  expect(
    screen
      .getByRole("checkbox", { name: "모델 A · Provider 0" })
      .hasAttribute("disabled"),
  ).toBe(false);
  fireEvent.click(
    screen.getByRole("button", { name: "모델 A · Provider 1 즐겨찾기" }),
  );
  expect(onSet).toHaveBeenCalledWith("a:p1", true);
});

test("변경 실패를 해당 모델에 안내하고 다시 누르면 동일한 변경을 요청한다", () => {
  const onSet = vi.fn();
  render(
    picker({ kind: "ready", keys: ["a:p0"], failedKeys: ["a:p0"], onSet }),
  );
  expect(screen.getByRole("alert").textContent).toContain(
    "즐겨찾기를 변경하지 못했습니다",
  );
  fireEvent.click(
    screen.getByRole("button", { name: "모델 A · Provider 0 즐겨찾기" }),
  );
  expect(onSet).toHaveBeenCalledWith("a:p0", false);
});

test.each(["loading", "unavailable"] as const)(
  "즐겨찾기 %s 상태에서 카탈로그 선택은 가능하고 저장 성공을 표시하지 않는다",
  (kind) => {
    render(picker({ kind }));
    expect(
      screen.getByRole("checkbox", { name: "모델 A · Provider 0" }),
    ).toBeDefined();
    expect(
      screen
        .getByRole("button", { name: "모델 A · Provider 0 즐겨찾기" })
        .hasAttribute("disabled"),
    ).toBe(true);
    favoriteList();
    expect(
      screen.getByText(
        kind === "loading"
          ? "즐겨찾기를 불러오고 있습니다"
          : "즐겨찾기를 준비하고 있습니다",
      ),
    ).toBeDefined();
    expect(screen.queryByRole("checkbox")).toBeNull();
  },
);

test("조회 실패는 빈 목록과 구별하고 다시 시도할 수 있다", () => {
  const onRetry = vi.fn();
  render(picker({ kind: "error", onRetry }));
  favoriteList();
  expect(screen.getByText("즐겨찾기를 불러오지 못했습니다")).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
  expect(onRetry).toHaveBeenCalledTimes(1);
});

test("즐겨찾기 해제는 비활성 모델에서도 가능하고 모달 닫기는 저장 취소를 요청하지 않는다", () => {
  const onSet = vi.fn();
  render(picker({ kind: "ready", keys: ["a:p2"], onSet }));
  favoriteList();
  expect(
    screen
      .getByRole("checkbox", { name: "모델 A · Provider 2" })
      .hasAttribute("disabled"),
  ).toBe(true);
  fireEvent.click(
    screen.getByRole("button", { name: "모델 A · Provider 2 즐겨찾기" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "닫기" }));
  expect(onSet).toHaveBeenCalledExactlyOnceWith("a:p2", false);
  expect(onClose).toHaveBeenCalledOnce();
});
