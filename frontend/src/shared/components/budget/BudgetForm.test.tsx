// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { BudgetForm } from "./BudgetForm";

afterEach(cleanup);

const HINT = "한 번 정하면 다음 달에도 그대로 적용돼요.";

const save = () => screen.getByRole("button", { name: "예산 저장" });
const amount = () => screen.getByLabelText("월 예산 (USD)");

test("저장을 누르면 검증하고, 잘못된 칸 아래에 문구를 보여 준다", async () => {
  const onSubmit = vi.fn();
  render(
    <BudgetForm
      defaultMonth="2026-10"
      onSubmit={onSubmit}
      onClose={vi.fn()}
      hint={HINT}
    />,
  );

  fireEvent.change(amount(), { target: { value: "0" } });
  expect(screen.queryByText("월 예산은 0보다 커야 해요.")).toBeNull();
  fireEvent.click(save());

  expect(await screen.findByText("월 예산은 0보다 커야 해요.")).toBeTruthy();
  expect(amount().getAttribute("aria-invalid")).toBe("true");
  expect(onSubmit).not.toHaveBeenCalled();
});

test("올바르게 입력하면 입력한 값으로 저장을 요청한다", async () => {
  const onSubmit = vi.fn();
  render(
    <BudgetForm
      defaultMonth="2026-10"
      onSubmit={onSubmit}
      onClose={vi.fn()}
      hint={HINT}
    />,
  );

  fireEvent.change(amount(), { target: { value: " 5000 " } });
  fireEvent.click(save());

  await waitFor(() =>
    expect(onSubmit).toHaveBeenCalledWith({
      amount: "5000",
      effectiveFrom: "2026-10",
    }),
  );
});

test("저장 함수가 없으면 저장 버튼을 막는다", () => {
  render(<BudgetForm defaultMonth="2026-10" onClose={vi.fn()} hint={HINT} />);

  expect((save() as HTMLButtonElement).disabled).toBe(true);
});
