import { z } from "zod";
import type { components } from "../../../shared/api/schema";
import { amountForInput } from "../../../shared/lib/budget";
import { monthField, usdAmountField } from "../../../shared/lib/formFields";
import { NEW_PROJECT_VALUE, projectIdOf } from "./newProject";

type Schemas = components["schemas"];

const STATUSES = [
  "ACTIVE",
  "CANCELLED",
] as const satisfies readonly Schemas["SubscriptionStatus"][];

export const subscriptionFormSchema = z
  .object({
    /** 같은 구독을 매달 묶는 값(subscription_reference). 표에 보이는 이름은 도구명이다. */
    reference: z.string().trim().min(1, "구독 식별값을 입력해 주세요."),
    toolName: z.string().trim().min(1, "도구명을 입력해 주세요."),
    type: z.string().trim(),
    month: monthField("적용 월을 골라 주세요."),
    amount: usdAmountField("금액을 입력해 주세요.").refine(
      (value) => !value.startsWith("-"),
      "금액은 0 이상이어야 해요.",
    ),
    /** 귀속 프로젝트 번호. 선택 상자 값이라 문자열이고, 빈 문자열은 미배분, NEW_PROJECT_VALUE는 새 프로젝트다. */
    project: z.string(),
    /** 새 프로젝트를 고른 경우에만 쓰는 이름 */
    newProjectName: z.string().trim(),
    status: z.enum(STATUSES),
    note: z.string().trim(),
  })
  .refine(
    (values) =>
      values.project !== NEW_PROJECT_VALUE || values.newProjectName !== "",
    { path: ["newProjectName"], message: "새 프로젝트 이름을 입력해 주세요." },
  );

export type SubscriptionFormInput = z.input<typeof subscriptionFormSchema>;
export type SubscriptionFormValues = z.output<typeof subscriptionFormSchema>;

/** 등록 폼의 처음 값. 새 구독료는 서버가 "사용 중"으로 저장하므로 상태는 보내지 않는다. */
export function emptySubscription(month: string): SubscriptionFormValues {
  return {
    reference: "",
    toolName: "",
    type: "",
    month,
    amount: "",
    project: "",
    newProjectName: "",
    status: "ACTIVE",
    note: "",
  };
}

function orNull(text: string): string | null {
  return text === "" ? null : text;
}

/** 등록 요청 본문. 프로젝트는 새 프로젝트를 만들거나 찾은 뒤 정해진 번호(미배분은 null)를 받는다. */
export function subscriptionCreateBody(
  values: SubscriptionFormValues,
  projectId: number | null,
): Schemas["SubscriptionCreate"] {
  return {
    subscription_reference: values.reference,
    tool_name: values.toolName,
    subscription_type: orNull(values.type),
    applied_month: values.month,
    amount_usd: values.amount,
    project_id: projectId,
    note: orNull(values.note),
  };
}

/**
 * 수정에서 바꾼 칸만 보낸다. 서버는 보낸 항목만 바꾸므로, 건드리지 않은 칸을 옛 값으로 덮어쓰지 않는다.
 * 바꿀 수 있는 칸은 금액·귀속 프로젝트·상태·메모다. 구독 식별값·도구명·구독 종류·적용 월은 등록 뒤 바꿀 수 없다.
 */
export function subscriptionUpdateBody(
  before: SubscriptionFormValues,
  after: SubscriptionFormValues,
  projectId: number | null,
): Schemas["SubscriptionUpdate"] {
  return {
    ...(after.amount !== before.amount ? { amount_usd: after.amount } : {}),
    ...(projectId !== projectIdOf(before.project)
      ? { project_id: projectId }
      : {}),
    ...(after.status !== before.status ? { status: after.status } : {}),
    ...(after.note !== before.note ? { note: orNull(after.note) } : {}),
  };
}

/** 목록의 행을 수정 폼 값으로 바꾼다. */
export function subscriptionFormValues(
  row: Schemas["SubscriptionRow"],
): SubscriptionFormValues {
  return {
    reference: row.subscription_reference,
    toolName: row.tool_name,
    type: row.subscription_type ?? "",
    month: row.applied_month,
    amount: amountForInput(row.amount_usd),
    project: row.project_id === null ? "" : String(row.project_id),
    newProjectName: "",
    status: row.status,
    note: row.note ?? "",
  };
}
