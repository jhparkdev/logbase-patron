import type { z } from "zod";

/** 폼 스키마로 검증했을 때 칸마다 첫 번째 오류 문구. 오류가 없는 칸은 빠진다. */
export function schemaErrors(
  schema: z.ZodType,
  values: Record<string, unknown>,
) {
  const result = schema.safeParse(values);
  const messages: Record<string, string> = {};
  for (const issue of result.error?.issues ?? []) {
    messages[String(issue.path[0])] ??= issue.message;
  }
  return messages;
}
