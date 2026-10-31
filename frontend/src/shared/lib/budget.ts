import { z } from "zod";
import { monthField, usdAmountField } from "./formFields";

const ZERO = /^-?0+(\.0+)?$/;

/** 월 예산 입력. 고객 예산(P-01)과 프로젝트 예산(P-02)이 같은 budgets 테이블이라 규칙이 같다. */
export const budgetFormSchema = z.object({
  amount: usdAmountField("월 예산을 입력해 주세요.").refine(
    (value) => !value.startsWith("-") && !ZERO.test(value),
    "월 예산은 0보다 커야 해요.",
  ),
  /** 한 번 정하면 다음 달에도 그대로 적용된다. */
  effectiveFrom: monthField("적용 시작 월을 골라 주세요."),
});

export type BudgetFormValues = z.output<typeof budgetFormSchema>;
