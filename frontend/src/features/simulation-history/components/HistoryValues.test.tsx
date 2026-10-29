// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { HistoryCost, HistoryCostStatus } from "./HistoryValues";

afterEach(cleanup);
test("미확인 합계를 0이나 대시로 바꾸지 않는다", () => {
  render(
    <HistoryCost
      cost={{ total: null, estimated: false, unknownCount: 3, checking: false }}
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
          total: "0",
          estimated: false,
          unknownCount: 0,
          checking: false,
        }}
      />
      <HistoryCostStatus
        cost={{
          total: null,
          estimated: false,
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
