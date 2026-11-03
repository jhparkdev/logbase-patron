import { describe, expect, test } from "vitest";
import { SUBSCRIPTIONS } from "../../../test/internalBudgetApi";
import { schemaErrors } from "../../../test/schemaErrors";
import {
  subscriptionCreateBody,
  subscriptionFormSchema,
  subscriptionFormValues,
  subscriptionUpdateBody,
} from "./forms";
import { NEW_PROJECT_VALUE } from "./newProject";

const VALID = {
  reference: "chatgpt-team",
  toolName: "ChatGPT Team",
  type: "",
  month: "2026-10",
  amount: "600",
  project: "",
  newProjectName: "",
  status: "ACTIVE",
  note: "",
};

describe("subscriptionFormSchema", () => {
  test("새 프로젝트 추가를 골랐는데 이름이 비면 이름 칸에 알려 준다", () => {
    expect(
      schemaErrors(subscriptionFormSchema, {
        ...VALID,
        project: NEW_PROJECT_VALUE,
        newProjectName: " ",
      }),
    ).toEqual({ newProjectName: "새 프로젝트 이름을 입력해 주세요." });
    expect(
      schemaErrors(subscriptionFormSchema, {
        ...VALID,
        project: NEW_PROJECT_VALUE,
        newProjectName: "신규 프로젝트",
      }),
    ).toEqual({});
  });

  test("필수 칸을 채우면 통과하고 금액 0도 받는다", () => {
    expect(schemaErrors(subscriptionFormSchema, VALID)).toEqual({});
    expect(
      schemaErrors(subscriptionFormSchema, { ...VALID, amount: "0" }),
    ).toEqual({});
  });

  test("구독 식별값·도구명·적용 월·금액이 비면 각각 알려 준다", () => {
    expect(
      schemaErrors(subscriptionFormSchema, {
        ...VALID,
        reference: " ",
        toolName: " ",
        month: "",
        amount: "",
      }),
    ).toEqual({
      reference: "구독 식별값을 입력해 주세요.",
      toolName: "도구명을 입력해 주세요.",
      month: "적용 월을 골라 주세요.",
      amount: "금액을 입력해 주세요.",
    });
  });

  test("음수 금액은 거절한다", () => {
    expect(
      schemaErrors(subscriptionFormSchema, { ...VALID, amount: "-10" }),
    ).toEqual({ amount: "금액은 0 이상이어야 해요." });
  });
});

describe("등록·수정 요청 본문", () => {
  test("등록은 빈 구독 종류·프로젝트·메모를 null로 보내고 상태는 보내지 않는다", () => {
    expect(
      subscriptionCreateBody(subscriptionFormSchema.parse(VALID), null),
    ).toEqual({
      subscription_reference: "chatgpt-team",
      tool_name: "ChatGPT Team",
      subscription_type: null,
      applied_month: "2026-10",
      amount_usd: "600",
      project_id: null,
      note: null,
    });
  });

  test("수정은 바꾼 칸만 보낸다. 바꿀 수 있는 칸은 금액·프로젝트·상태·메모다", () => {
    const before = subscriptionFormSchema.parse(VALID);
    expect(
      subscriptionUpdateBody(
        before,
        {
          ...before,
          amount: "650.5",
          project: "2",
          status: "CANCELLED",
          note: "11월부터 해지",
        },
        2,
      ),
    ).toEqual({
      amount_usd: "650.5",
      project_id: 2,
      status: "CANCELLED",
      note: "11월부터 해지",
    });
    expect(
      subscriptionUpdateBody(before, { ...before, amount: "700" }, null),
    ).toEqual({ amount_usd: "700" });
  });

  test("수정에서 새 프로젝트를 만들어 귀속하면 정해진 번호를 보낸다", () => {
    const before = subscriptionFormSchema.parse(VALID);
    expect(
      subscriptionUpdateBody(
        before,
        { ...before, project: "new", newProjectName: "신규" },
        3,
      ),
    ).toEqual({ project_id: 3 });
  });

  test("수정에서 프로젝트·메모를 비우면 null로 보내 지운다", () => {
    const before = subscriptionFormSchema.parse({
      ...VALID,
      project: "2",
      note: "메모",
    });
    expect(
      subscriptionUpdateBody(
        before,
        { ...before, project: "", note: "" },
        null,
      ),
    ).toEqual({ project_id: null, note: null });
  });
});

test("subscriptionFormValues는 목록 행을 폼 값으로 바꾼다", () => {
  expect(subscriptionFormValues(SUBSCRIPTIONS.items[0])).toEqual({
    reference: "command-code-team",
    toolName: "Command Code",
    type: "Team",
    month: "2026-10",
    amount: "100",
    project: "1",
    newProjectName: "",
    status: "ACTIVE",
    note: "",
  });
  expect(subscriptionFormValues(SUBSCRIPTIONS.items[1])).toMatchObject({
    type: "",
    project: "",
    note: "9월에 해지",
  });
});
