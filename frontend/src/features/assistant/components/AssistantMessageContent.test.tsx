// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { AssistantMessageContent } from "./AssistantMessageContent";

afterEach(cleanup);

test("renders readable dates, emphasis, lists and code as distinct content", () => {
  const { container } = render(
    <AssistantMessageContent
      content={
        '최근 호출은 **2026-11-02T07:11:38.580827Z**입니다.\n\n- 성공 1200건\n- 비용 미확인\n\n```json\n{"max_tokens":2048}\n```'
      }
    />,
  );
  expect(screen.getByText("2026년 11월 2일 16:11:38 (한국시간)").tagName).toBe(
    "STRONG",
  );
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
  expect(screen.getByText("성공 1,200건")).toBeTruthy();
  expect(container.querySelector("pre code")?.textContent).toBe(
    '{"max_tokens":2048}',
  );
  expect(container.textContent).not.toContain("**");
});

test("HTML and generated link syntax remain inert text", () => {
  const { container } = render(
    <AssistantMessageContent
      content={
        "<img src=x onerror=alert(1)>\n\n[눌러주세요](javascript:alert(1))\n\n**<script>alert(1)</script>**"
      }
    />,
  );
  expect(container.querySelectorAll("img, script, a")).toHaveLength(0);
  expect(container.textContent).toContain("<img src=x onerror=alert(1)>");
});
