// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { renderAt } from "../test/renderAt";

test("첫 주소(/)로 들어오면 고객 AI 사용 현황으로 보낸다", async () => {
  renderAt("/");

  expect(
    await screen.findByRole("heading", { level: 1, name: "고객 AI 사용 현황" }),
  ).toBeDefined();
});
