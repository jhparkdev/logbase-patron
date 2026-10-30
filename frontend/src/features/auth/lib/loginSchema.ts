import { z } from "zod";

export const loginSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "이메일을 입력해 주세요.")
    .pipe(z.email("이메일 형식이 올바르지 않아요.")),
  // 비밀번호는 공백도 값의 일부라 다듬지 않는다. 길이 제한은 서버가 검증한다.
  password: z.string().min(1, "비밀번호를 입력해 주세요."),
});

export type LoginInput = z.input<typeof loginSchema>;
export type LoginValues = z.output<typeof loginSchema>;
