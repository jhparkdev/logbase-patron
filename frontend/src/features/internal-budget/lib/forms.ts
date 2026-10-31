import { z } from "zod";
import { monthField, usdAmountField } from "../../../shared/lib/formFields";

export const subscriptionFormSchema = z.object({
  toolName: z.string().trim().min(1, "도구명을 입력해 주세요."),
  month: monthField("적용 월을 골라 주세요."),
  amount: usdAmountField("금액을 입력해 주세요.").refine(
    (value) => !value.startsWith("-"),
    "금액은 0 이상이어야 해요.",
  ),
  // 화면의 선택 값이다. 구독료 API가 생기면 백엔드 상태 값(enum)으로 바꿔 보낸다.
  status: z.enum(["active", "cancelled"]),
  note: z.string().trim(),
});

export type SubscriptionFormValues = z.output<typeof subscriptionFormSchema>;
