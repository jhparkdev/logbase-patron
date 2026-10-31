// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { CostAmount } from "./CostAmount";

afterEach(cleanup);

test("확정 비용은 숫자만 보여 준다", () => {
  const { container } = render(
    <CostAmount
      cost={{ kind: "confirmed", amount: "12.5" }}
      precision="perCall"
    />,
  );

  expect(container.textContent).toBe("12.5000");
});

test("추정 비용은 ≈와 추정 배지를 붙인다", () => {
  const { container } = render(
    <CostAmount
      cost={{ kind: "estimated", amount: "0.09815" }}
      precision="perCall"
    />,
  );

  expect(container.textContent).toBe("≈ 0.0982추정");
  expect(screen.getByText("추정")).toBeTruthy();
});

test("미확인 비용은 금액 없이 미확인 배지만 보여 준다", () => {
  const { container } = render(
    <CostAmount cost={{ kind: "unknown", amount: null }} precision="summary" />,
  );

  expect(container.textContent).toBe("미확인");
});
