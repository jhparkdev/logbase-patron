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
  expect(screen.queryByRole("alert")).toBeNull();
});

test("오류가 있으면 문구를 보여 주고 두 칸을 잘못된 입력으로 표시한다", () => {
  const message = "기간은 최대 366일까지 조회할 수 있어요. 기간을 줄여 주세요.";
  render(
    <PeriodField label="기간" fromInput={{}} toInput={{}} error={message} />,
  );

  const alert = screen.getByRole("alert");
  expect(alert.textContent).toBe(message);
  for (const input of [inputs().from, inputs().to]) {
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(input.getAttribute("aria-describedby")).toBe(alert.id);
  }
});
