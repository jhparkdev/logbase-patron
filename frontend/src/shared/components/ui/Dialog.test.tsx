// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { Dialog } from "./Dialog";

afterEach(cleanup);
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
test("긴 상세 창을 열면 제목에 포커스를 두어 맨 아래 버튼으로 건너뛰지 않는다", () => {
  render(
    <Dialog open title="실행 상세" onClose={vi.fn()}>
      <p>긴 원문</p>
      <button type="button">아래쪽 동작</button>
    </Dialog>,
  );
  expect(document.activeElement).toBe(
    screen.getByRole("heading", { name: "실행 상세" }),
  );
});
test("중첩 응답 창의 Escape가 바깥 실행 상세까지 닫지 않는다", () => {
  const outerClose = vi.fn();
  const innerClose = vi.fn();
  render(
    <Dialog open title="실행 상세" onClose={outerClose}>
      <Dialog open title="전체 응답" onClose={innerClose}>
        <p>원문</p>
      </Dialog>
    </Dialog>,
  );
  fireEvent(
    screen.getByRole("dialog", { name: "전체 응답" }),
    new Event("cancel", { bubbles: true, cancelable: true }),
  );
  expect(innerClose).toHaveBeenCalledTimes(1);
  expect(outerClose).not.toHaveBeenCalled();
});
