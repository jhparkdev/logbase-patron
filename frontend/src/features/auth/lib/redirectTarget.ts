/** 돌아갈 주소가 없거나 쓸 수 없을 때 가는 화면 */
export const DEFAULT_AFTER_LOGIN = "/customer-usage";

const LOGIN_PATH = "/login";

/**
 * 로그인 뒤 돌아갈 주소를 정한다. 주소의 redirect 값은 외부 입력이라
 * 앱 안의 경로(/로 시작, //나 /\로 시작하지 않음)만 받고 그 밖은 기본 화면으로 보낸다.
 */
export function safeRedirectTarget(value: string | undefined): string {
  if (!value?.startsWith("/")) {
    return DEFAULT_AFTER_LOGIN;
  }
  // "//host"와 "/\host"는 브라우저가 다른 사이트 주소로 해석한다.
  if (value.startsWith("//") || value.startsWith("/\\")) {
    return DEFAULT_AFTER_LOGIN;
  }
  if (value === LOGIN_PATH || value.startsWith(`${LOGIN_PATH}?`)) {
    return DEFAULT_AFTER_LOGIN;
  }
  return value;
}
