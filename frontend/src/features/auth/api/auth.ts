import { queryOptions } from "@tanstack/react-query";
import { api, toApiError } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";

export type CurrentUser = components["schemas"]["CurrentUserRead"];
export type LoginRequest = components["schemas"]["LoginRequest"];

/** 로그인. 성공하면 서버가 세션 쿠키를 설정하고 사용자 정보를 돌려준다. 실패는 ApiError로 던진다. */
export async function login(body: LoginRequest): Promise<CurrentUser> {
  const { data, error, response } = await api.POST("/api/auth/login", {
    body,
  });
  if (data) {
    return data;
  }
  throw toApiError(response.status, error);
}

/** 로그인한 사용자. 세션이 없거나 만료되었으면(401) null이다. */
export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  const { data, error, response } = await api.GET("/api/auth/me");
  if (data) {
    return data;
  }
  if (response.status === 401) {
    return null;
  }
  throw toApiError(response.status, error);
}

/** 화면을 옮길 때마다 서버에 다시 묻지 않는 시간. 세션 만료는 보호된 API의 401로도 드러난다. */
const CURRENT_USER_STALE_TIME_MS = 5 * 60 * 1000;

export const currentUserQueryOptions = queryOptions({
  queryKey: ["auth", "me"],
  queryFn: fetchCurrentUser,
  staleTime: CURRENT_USER_STALE_TIME_MS,
  // 401은 재시도해도 같으므로 바로 로그인 화면으로 보낸다.
  retry: false,
});

/** 로그아웃. 서버가 이 세션을 지우고 쿠키를 비운다. 실패는 ApiError로 던진다. */
export async function logout(): Promise<void> {
  const { error, response } = await api.POST("/api/auth/logout");
  if (!response.ok) {
    throw toApiError(response.status, error);
  }
}
