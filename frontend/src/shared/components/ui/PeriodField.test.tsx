// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { PeriodField } from "./PeriodField";

afterEach(cleanup);

function inputs() {
  const group = screen.getByRole("group", { name: "기간" });
  return {
    group,
    from: screen.getByLabelText<HTMLInputElement>("시작일"),
    to: screen.getByLabelText<HTMLInputElement>("종료일"),
  };
}

test("기간 묶음 안에 시작일과 종료일 칸을 보여 준다", () => {
  render(
    <PeriodField
      label="기간"
      fromInput={{ defaultValue: "2026-10-01" }}
      toInput={{ defaultValue: "2026-10-31" }}
    />,
  );

  const { group, from, to } = inputs();
  expect(group.contains(from) && group.contains(to)).toBe(true);
  expect(from.value).toBe("2026-10-01");
  expect(to.value).toBe("2026-10-31");
  expect(from.getAttribute("aria-invalid")).toBe("false");
  expect(from.getAttribute("aria-describedby")).toBeNull();
});

test("오류 문구의 id를 받으면 두 칸을 잘못된 입력으로 표시하고 문구와 연결한다", () => {
  render(
    <PeriodField
      label="기간"
      fromInput={{}}
      toInput={{}}
      errorId="period-error"
    />,
  );

  for (const input of [inputs().from, inputs().to]) {
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(input.getAttribute("aria-describedby")).toBe("period-error");
  }
});
