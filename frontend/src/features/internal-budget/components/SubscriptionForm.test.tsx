// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { SUBSCRIPTIONS } from "../../../test/internalBudgetApi";
import { subscriptionFormValues } from "../lib/forms";
import { SubscriptionForm } from "./SubscriptionForm";

afterEach(cleanup);

const PROJECTS = [
  { project_id: 1, name: "사내 챗봇 구축" },
  { project_id: 2, name: "문서 요약" },
];

test("등록 폼은 비어 있는 필수 칸을 한꺼번에 알려 주고 상태 선택은 두지 않는다", async () => {
  const onSubmit = vi.fn();
  render(
    <SubscriptionForm
      defaultMonth="2026-10"
      projects={PROJECTS}
      onSubmit={onSubmit}
      onClose={vi.fn()}
    />,
  );

  expect(screen.queryByRole("radio", { name: "해지" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "등록" }));

  expect(await screen.findByText("구독 식별값을 입력해 주세요.")).toBeTruthy();
  expect(screen.getByText("도구명을 입력해 주세요.")).toBeTruthy();
  expect(screen.getByText("금액을 입력해 주세요.")).toBeTruthy();
  expect(onSubmit).not.toHaveBeenCalled();
});

test("등록 폼을 채우면 입력한 값으로 등록을 요청한다", async () => {
  const onSubmit = vi.fn();
  render(
    <SubscriptionForm
      defaultMonth="2026-10"
      projects={PROJECTS}
      onSubmit={onSubmit}
      onClose={vi.fn()}
    />,
  );

  fireEvent.change(screen.getByLabelText("구독 식별값"), {
    target: { value: "claude-team" },
  });
  fireEvent.change(screen.getByLabelText("도구명"), {
    target: { value: "Claude Team" },
  });
  fireEvent.change(screen.getByLabelText("구독 종류 (선택)"), {
    target: { value: "Team" },
  });
  fireEvent.change(screen.getByLabelText("금액 (USD)"), {
    target: { value: "300" },
  });
  fireEvent.change(screen.getByLabelText("귀속 프로젝트"), {
    target: { value: "2" },
  });
  fireEvent.click(screen.getByRole("button", { name: "등록" }));

  await waitFor(() =>
    expect(onSubmit).toHaveBeenCalledWith({
      reference: "claude-team",
      toolName: "Claude Team",
      type: "Team",
      month: "2026-10",
      amount: "300",
      project: "2",
      status: "ACTIVE",
      note: "",
    }),
  );
});

test("수정 폼은 구독 식별값·도구명·구독 종류·적용 월을 글자로만 보여 주고 상태를 바꿀 수 있다", async () => {
  const onSubmit = vi.fn();
  render(
    <SubscriptionForm
      editing={subscriptionFormValues(SUBSCRIPTIONS.items[0])}
      projects={PROJECTS}
      onSubmit={onSubmit}
      onClose={vi.fn()}
    />,
  );

  expect(screen.queryByLabelText("구독 식별값")).toBeNull();
  expect(screen.getByText("command-code-team")).toBeTruthy();
  expect(screen.getByText("Command Code")).toBeTruthy();
  expect(screen.getByText("Team")).toBeTruthy();
  expect(screen.getByText("2026-10")).toBeTruthy();
  expect(screen.getByLabelText<HTMLInputElement>("금액 (USD)").value).toBe(
    "100",
  );
  expect(screen.getByLabelText<HTMLSelectElement>("귀속 프로젝트").value).toBe(
    "1",
  );
  fireEvent.click(screen.getByRole("radio", { name: "해지" }));
  fireEvent.click(screen.getByRole("button", { name: "저장" }));

  await waitFor(() =>
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ status: "CANCELLED", amount: "100" }),
    ),
  );
});

test("저장하는 동안에는 제출 버튼을 막는다", () => {
  render(
    <SubscriptionForm
      defaultMonth="2026-10"
      projects={PROJECTS}
      submitting
      onSubmit={vi.fn()}
      onClose={vi.fn()}
    />,
  );

  expect(
    screen.getByRole<HTMLButtonElement>("button", { name: "등록" }).disabled,
  ).toBe(true);
});
