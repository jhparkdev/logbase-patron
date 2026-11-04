// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { UsageBar } from "./UsageBar";

afterEach(cleanup);

function meter() {
  return screen.getByRole<HTMLMeterElement>("meter", { name: "사용률" });
}

test("사용률만큼 채우고 %를 보여 준다", () => {
  render(<UsageBar usage={{ status: "normal", percent: 68 }} />);

  expect(screen.getByText("68%")).toBeTruthy();
  expect(meter().value).toBe(68);
});

test("100%를 넘으면 꽉 찬 채로 두고 실제 사용률을 보여 준다", () => {
  render(<UsageBar usage={{ status: "over", percent: 108 }} />);

  expect(screen.getByText("108%")).toBeTruthy();
  expect(meter().value).toBe(100);
  expect(meter().getAttribute("aria-valuetext")).toBe("108%");
});

test("예산이 없으면 0%가 아니라 막대 없이 안내 문구를 보여 준다", () => {
  const { container } = render(<UsageBar usage={{ status: "unset" }} />);

  expect(screen.queryByRole("meter")).toBeNull();
  expect(container.textContent).toBe("예산을 정하면 사용률이 보여요");
});

test("주의 기준을 받으면 막대 위 그 위치에 기준선을 둔다", () => {
  const { container } = render(
    <UsageBar usage={{ status: "normal", percent: 30 }} warningAt={80} />,
  );

  const mark = container.querySelector<HTMLElement>("[data-mark='warning']");
  expect(mark?.style.left).toBe("80%");
});

test("예산이 없으면 주의 기준을 받아도 기준선을 두지 않는다", () => {
  const { container } = render(
    <UsageBar usage={{ status: "unset" }} warningAt={80} />,
  );

  expect(container.querySelector("[data-mark='warning']")).toBeNull();
});
