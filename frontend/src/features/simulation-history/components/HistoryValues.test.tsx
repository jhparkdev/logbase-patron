// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { HistoryCost, HistoryCostStatus } from "./HistoryValues";

afterEach(cleanup);
test("미확인 합계를 0이나 대시로 바꾸지 않는다", () => {
  render(
    <HistoryCost
      cost={{
        confirmed: null,
        estimated: null,
        unknownCount: 3,
        checking: false,
      }}
    />,
  );
  expect(screen.getByText("미확인")).toBeDefined();
  expect(screen.getByText("미확인 3건 미반영")).toBeDefined();
  expect(screen.queryByText(/\$0/)).toBeNull();
});
test("확정된 0은 유효한 금액으로 표시하고 진행 중 비용 확인을 별도로 안내한다", () => {
  render(
    <>
      <HistoryCost
        cost={{
          confirmed: "0",
          estimated: null,
          unknownCount: 0,
          checking: false,
        }}
      />
      <HistoryCostStatus
        cost={{
          confirmed: null,
          estimated: null,
          unknownCount: 1,
          checking: true,
        }}
      />
    </>,
  );
  expect(screen.getByText("$0.00")).toBeDefined();
  expect(screen.getByText("확인 중")).toBeDefined();
  expect(screen.getByText("미확인 포함")).toBeDefined();
});
test("추정 비용은 ≈와 추정 포함으로 구분한다", () => {
  render(
    <>
      <HistoryCost
        cost={{
          confirmed: null,
          estimated: "0.5",
          unknownCount: 0,
          checking: false,
        }}
      />
      <HistoryCostStatus
        cost={{
          confirmed: null,
          estimated: "0.5",
          unknownCount: 0,
          checking: false,
        }}
      />
    </>,
  );
  expect(screen.getByText("≈ $0.50")).toBeDefined();
  expect(screen.getByText("추정 포함")).toBeDefined();
});
test("확정과 추정이 함께 있으면 더하지 않고 두 금액을 따로 표시한다", () => {
  render(
    <HistoryCost
      cost={{
        confirmed: "0.25",
        estimated: "0.5",
        unknownCount: 0,
        checking: false,
      }}
    />,
  );
  expect(screen.getByText("$0.25")).toBeDefined();
  expect(screen.getByText("≈ $0.50")).toBeDefined();
  expect(screen.queryByText(/0\.75/)).toBeNull();
});
