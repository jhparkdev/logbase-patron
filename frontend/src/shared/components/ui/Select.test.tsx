// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { Select } from "./Select";

afterEach(cleanup);

const OPTIONS = [{ value: "", label: "전체 프로젝트" }];

test("기본은 이름을 화면에 보이지 않고 화면 낭독기에만 알린다", () => {
  render(
    <Select label="프로젝트" value="" options={OPTIONS} onChange={() => {}} />,
  );

  expect(screen.getByRole("combobox", { name: "프로젝트" })).toBeTruthy();
  expect(screen.queryByText("프로젝트")).toBeNull();
});

for (const labelPosition of ["top", "side"] as const) {
  test(`labelPosition이 ${labelPosition}이면 보이는 라벨을 두고 상자와 연결한다`, () => {
    render(
      <Select
        label="프로젝트"
        labelPosition={labelPosition}
        value=""
        options={OPTIONS}
        onChange={() => {}}
      />,
    );

    expect(screen.getByText("프로젝트").tagName).toBe("LABEL");
    expect(screen.getByRole("combobox", { name: "프로젝트" })).toBeTruthy();
  });
}
