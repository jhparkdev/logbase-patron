import { z } from "zod";

// 백엔드(schemas/model_test.py)의 테스트 문장 길이와 동일. 실제 비용이 드는 호출이라 상한이 있음
export const MAX_TEST_PROMPT_LENGTH = 1000;

/** 연결 테스트 Prompt. 비우면 서버가 기본 문장을 씀. 앞뒤 공백은 지움 */
export const testPromptFormSchema = z.object({
  prompt: z
    .string()
    .trim()
    .max(
      MAX_TEST_PROMPT_LENGTH,
      `Prompt는 ${MAX_TEST_PROMPT_LENGTH}자 이하로 입력해 주세요.`,
    ),
});

export type TestPromptValues = z.output<typeof testPromptFormSchema>;
