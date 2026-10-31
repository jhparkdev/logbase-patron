// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { SubscriptionForm } from "./SubscriptionForm";

afterEach(cleanup);

const submit = () => screen.getByRole("button", { name: "등록" });

test("비어 있는 필수 칸을 등록할 때 한꺼번에 알려 준다", async () => {
  const onSubmit = vi.fn();
  render(
    <SubscriptionForm
      defaultMonth="2026-10"
      onSubmit={onSubmit}
      onClose={vi.fn()}
    />,
  );

  fireEvent.click(submit());

  expect(await screen.findByText("도구명을 입력해 주세요.")).toBeTruthy();
  expect(screen.getByText("금액을 입력해 주세요.")).toBeTruthy();
  expect(onSubmit).not.toHaveBeenCalled();
});

test("올바르게 입력하면 입력한 값으로 등록을 요청한다", async () => {
  const onSubmit = vi.fn();
  render(
    <SubscriptionForm
      defaultMonth="2026-10"
      onSubmit={onSubmit}
      onClose={vi.fn()}
    />,
  );

  fireEvent.change(screen.getByLabelText("도구명"), {
    target: { value: "Claude Team" },
  });
  fireEvent.change(screen.getByLabelText("금액 (USD)"), {
    target: { value: "300" },
  });
  fireEvent.click(screen.getByRole("radio", { name: "해지" }));
  fireEvent.click(submit());

  await waitFor(() =>
    expect(onSubmit).toHaveBeenCalledWith({
      toolName: "Claude Team",
      month: "2026-10",
      amount: "300",
      status: "cancelled",
      note: "",
    }),
  );
});

test("등록 함수가 없으면 등록 버튼을 막는다", () => {
  render(<SubscriptionForm defaultMonth="2026-10" onClose={vi.fn()} />);

  expect((submit() as HTMLButtonElement).disabled).toBe(true);
});
