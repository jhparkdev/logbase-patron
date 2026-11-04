import { z } from "zod";

// 백엔드(schemas/model_register.py)의 표시 이름·용도 길이와 동일. 넘으면 요청 거절
const MAX_DISPLAY_NAME_LENGTH = 100;
const MAX_PURPOSE_LENGTH = 200;

// 앞뒤 공백은 지움
const displayNameField = z
  .string()
  .trim()
  .min(1, "표시 이름을 입력해 주세요.")
  .max(
    MAX_DISPLAY_NAME_LENGTH,
    `표시 이름은 ${MAX_DISPLAY_NAME_LENGTH}자 이하로 입력해 주세요.`,
  );

/** 용도는 비워도 됨. 비우면 서버가 용도를 지움 */
const purposeField = z
  .string()
  .trim()
  .max(
    MAX_PURPOSE_LENGTH,
    `용도는 ${MAX_PURPOSE_LENGTH}자 이하로 입력해 주세요.`,
  );

/** 한 항목을 수정하는 폼의 값 */
export type InfoFormValues = { value: string };

export const displayNameFormSchema = z.object({ value: displayNameField });
export const purposeFormSchema = z.object({ value: purposeField });

/** 신규 등록 폼. 표시 이름과 용도를 한 번에 받음 */
export const registerFormSchema = z.object({
  displayName: displayNameField,
  purpose: purposeField,
});

export type RegisterFormValues = z.output<typeof registerFormSchema>;
