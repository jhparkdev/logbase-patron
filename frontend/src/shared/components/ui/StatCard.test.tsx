// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { StatCard } from "./StatCard";

afterEach(cleanup);

const base = { label: "작업 건수", value: "1,482", icon: "icon.svg" } as const;

test("증가는 ▲와 함께 화면 낭독기에 '증가'로 알린다", () => {
  render(<StatCard {...base} trend={{ direction: "up", rate: "12%" }} />);

  const trend = screen.getByText("12%").parentElement;
  expect(trend?.textContent).toBe("▲12% 증가 전월 대비");
  expect(screen.getByText("▲").getAttribute("aria-hidden")).toBe("true");
});

test("감소는 ▼와 함께 화면 낭독기에 '감소'로 알린다", () => {
  render(<StatCard {...base} trend={{ direction: "down", rate: "3%" }} />);

  const trend = screen.getByText("3%").parentElement;
  expect(trend?.textContent).toBe("▼3% 감소 전월 대비");
});

test("증감 값이 없으면 전월 대비를 보여 주지 않는다", () => {
  render(<StatCard {...base} />);

  expect(screen.queryByText(/전월 대비/)).toBeNull();
});
