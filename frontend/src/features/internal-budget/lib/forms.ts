import { z } from "zod";

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;
const DECIMAL = /^-?\d+(\.\d+)?$/;
const ZERO = /^-?0+(\.0+)?$/;

/** 금액은 숫자로 바꾸지 않고 문자열 그대로 검증하고 보낸다(float 오차 방지). */
function usdAmount(emptyMessage: string) {
  return z
    .string()
    .trim()
    .min(1, emptyMessage)
    .regex(DECIMAL, "숫자로 입력해 주세요.");
}

export const budgetFormSchema = z.object({
  amount: usdAmount("월 예산을 입력해 주세요.").refine(
    (value) => !value.startsWith("-") && !ZERO.test(value),
    "월 예산은 0보다 커야 해요.",
  ),
  /** "YYYY-MM". 한 번 정하면 다음 달에도 그대로 적용된다. */
  effectiveFrom: z.string().regex(MONTH, "적용 시작 월을 골라 주세요."),
});

export const subscriptionFormSchema = z.object({
  toolName: z.string().trim().min(1, "도구명을 입력해 주세요."),
  /** "YYYY-MM" */
  month: z.string().regex(MONTH, "적용 월을 골라 주세요."),
  amount: usdAmount("금액을 입력해 주세요.").refine(
    (value) => !value.startsWith("-"),
    "금액은 0 이상이어야 해요.",
  ),
  // 화면의 선택 값이다. 구독료 API가 생기면 백엔드 상태 값(enum)으로 바꿔 보낸다.
  status: z.enum(["active", "cancelled"]),
  note: z.string().trim(),
});

export type BudgetFormValues = z.output<typeof budgetFormSchema>;
export type SubscriptionFormValues = z.output<typeof subscriptionFormSchema>;
