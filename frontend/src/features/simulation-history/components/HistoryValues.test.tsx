// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import type { HistoryRow } from "../lib/presentation";
import { HistoryCost, HistoryCostStatus } from "./HistoryValues";

afterEach(cleanup);
const cost = (overrides: Partial<HistoryRow["cost"]>): HistoryRow["cost"] => ({
  confirmed: null,
  estimated: null,
  unknownCount: 0,
  checkStatus: "확정",
  ...overrides,
});

test("미확인 합계를 0이나 대시로 바꾸지 않는다", () => {
  render(
    <HistoryCost
      cost={cost({ unknownCount: 3, checkStatus: "미확인 포함" })}
    />,
  );
  expect(screen.getByText("미확인")).toBeDefined();
  expect(screen.getByText("미확인 3건 미반영")).toBeDefined();
  expect(screen.queryByText(/\$0/)).toBeNull();
});
test("확정된 0은 유효한 금액으로 표시한다", () => {
  render(<HistoryCost cost={cost({ confirmed: "0" })} />);
  expect(screen.getByText("$0.00")).toBeDefined();
});
test.each(["확인 중", "미확인 포함", "추정 포함", "확정"] as const)(
  "비용 상태는 서버가 준 %s 하나만 표시한다",
  (checkStatus) => {
    const { container } = render(
      <HistoryCostStatus
        cost={cost({ checkStatus, unknownCount: 1, estimated: "0.5" })}
      />,
    );
    expect(screen.getByText(checkStatus)).toBeDefined();
    expect(container.firstElementChild?.childElementCount).toBe(1);
  },
);
test("추정 비용은 ≈로 구분하고 비용 상태와 추정 포함을 겹쳐 쓰지 않는다", () => {
  const value = cost({ estimated: "0.5", checkStatus: "추정 포함" });
  render(
    <>
      <HistoryCost cost={value} />
      <HistoryCostStatus cost={value} />
    </>,
  );
  expect(screen.getByText("≈ $0.50")).toBeDefined();
  expect(screen.getAllByText("추정 포함")).toHaveLength(1);
});
test("비용 상태가 미확인 포함이어도 추정이 있으면 금액 쪽에 추정 포함을 남긴다", () => {
  render(
    <HistoryCost
      cost={cost({
        estimated: "0.5",
        unknownCount: 1,
        checkStatus: "미확인 포함",
      })}
    />,
  );
  expect(screen.getByText("≈ $0.50")).toBeDefined();
  expect(screen.getByText("추정 포함")).toBeDefined();
  expect(screen.getByText("미확인 1건 미반영")).toBeDefined();
});
test("확정과 추정이 함께 있으면 더하지 않고 두 금액을 따로 표시한다", () => {
  render(
    <HistoryCost
      cost={cost({
        confirmed: "0.25",
        estimated: "0.5",
        checkStatus: "추정 포함",
      })}
    />,
  );
  expect(screen.getByText("$0.25")).toBeDefined();
  expect(screen.getByText("≈ $0.50")).toBeDefined();
  expect(screen.queryByText(/0\.75/)).toBeNull();
});
