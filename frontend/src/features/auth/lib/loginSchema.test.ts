import { expect, test } from "vitest";
import { loginSchema } from "./loginSchema";

function errorsOf(input: unknown) {
  const result = loginSchema.safeParse(input);
  return result.success
    ? []
    : result.error.issues.map((issue) => issue.message);
}

test("이메일과 비밀번호가 있으면 통과하고 이메일 앞뒤 공백은 뺀다", () => {
  const result = loginSchema.safeParse({
    email: "  admin@patron.dev ",
    password: " pw ",
  });

  expect(result.success).toBe(true);
  // 비밀번호의 공백은 사용자가 넣은 값이라 그대로 둔다.
  expect(result.data).toEqual({ email: "admin@patron.dev", password: " pw " });
});

test("비어 있으면 무엇을 입력해야 하는지 알려 준다", () => {
  expect(errorsOf({ email: "", password: "" })).toEqual([
    "이메일을 입력해 주세요.",
    "비밀번호를 입력해 주세요.",
  ]);
});

test("이메일 형식이 아니면 형식 오류만 알려 준다", () => {
  expect(errorsOf({ email: "admin", password: "pw" })).toEqual([
    "이메일 형식이 올바르지 않아요.",
  ]);
});

test("공백만 넣은 이메일은 입력하지 않은 것으로 본다", () => {
  expect(errorsOf({ email: "   ", password: "pw" })).toEqual([
    "이메일을 입력해 주세요.",
  ]);
});
