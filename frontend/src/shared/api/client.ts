import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

type ErrorCode = components["schemas"]["ErrorCode"];
type ErrorResponse = components["schemas"]["ErrorResponse"];

/** 응답이 오류 계약(ErrorResponse)과 다를 때 쓰는 문구. 내부 오류 내용은 화면에 내보내지 않는다. */
const UNEXPECTED_RESPONSE_MESSAGE =
  "요청을 처리하지 못했어요. 다시 시도해 주세요.";

/** 서버가 오류 응답으로 거절했을 때 던진다. message는 서버가 사용자에게 보여 주라고 준 문구다. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: ErrorCode | undefined,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "code" in value &&
    typeof value.code === "string" &&
    "message" in value &&
    typeof value.message === "string"
  );
}

/** openapi-fetch가 돌려준 error 값을 ApiError로 바꾼다. 계약과 다른 형식이면 일반 문구를 쓴다. */
export function toApiError(status: number, error: unknown): ApiError {
  if (isErrorResponse(error)) {
    return new ApiError(status, error.code, error.message);
  }
  return new ApiError(status, undefined, UNEXPECTED_RESPONSE_MESSAGE);
}

/**
 * 생성된 OpenAPI 타입과 연결된 클라이언트. 경로는 모두 /api로 시작한다.
 * baseUrl은 화면의 출처라서 같은 출처(쿠키 포함)로 보낸다. 상대 경로만 주면 Request를 만들지 못하는 실행 환경이 있어 출처를 붙인다.
 * fetch는 호출 시점의 것을 쓴다. 모듈을 읽을 때 붙잡아 두면 이후에 바뀐 fetch(테스트 스텁 등)를 보지 못한다.
 */
export const api = createClient<paths>({
  baseUrl: globalThis.location?.origin ?? "",
  fetch: (request: Request) => globalThis.fetch(request),
});
