import { expect, test } from "vitest";
import { ApiError } from "../../../shared/api/client";
import { LOGIN_FAILED_MESSAGE, loginErrorMessage } from "./loginErrorMessage";

test("아이디·비밀번호 불일치는 서버가 준 문구를 그대로 보여 준다", () => {
  const error = new ApiError(
    401,
    "INVALID_CREDENTIALS",
    "이메일 또는 비밀번호가 올바르지 않습니다.",
  );

  expect(loginErrorMessage(error)).toBe(
    "이메일 또는 비밀번호가 올바르지 않습니다.",
  );
});

test("그 밖의 실패는 내부 문구 대신 다시 시도하라는 안내를 보여 준다", () => {
  expect(
    loginErrorMessage(new ApiError(500, "INTERNAL_ERROR", "Traceback ...")),
  ).toBe(LOGIN_FAILED_MESSAGE);
  expect(loginErrorMessage(new TypeError("Failed to fetch"))).toBe(
    LOGIN_FAILED_MESSAGE,
  );
  expect(loginErrorMessage("unknown")).toBe(LOGIN_FAILED_MESSAGE);
});
