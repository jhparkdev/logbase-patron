import { ApiError } from "../../../shared/api/client";

export const LOGIN_FAILED_MESSAGE = "로그인하지 못했어요. 다시 시도해 주세요.";

/**
 * 로그인 실패를 화면 문구로 바꾼다.
 * 자격 증명 불일치는 서버가 계정 유무를 드러내지 않게 다듬은 문구를 그대로 쓰고,
 * 그 밖(서버 오류, 네트워크 실패)은 내부 내용을 숨기고 다시 시도하라고 안내한다.
 */
export function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.code === "INVALID_CREDENTIALS") {
    return error.message;
  }
  return LOGIN_FAILED_MESSAGE;
}
