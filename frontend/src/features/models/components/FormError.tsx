import { ApiError } from "../../../shared/api/client";

const FALLBACK_MESSAGE = "저장하지 못했어요. 다시 시도해 주세요.";

/** 서버가 거절한 이유를 폼 위에 알림. 서버 문구가 없는 오류(네트워크 등)는 일반 문구 */
export function FormError({ error }: { error: Error }) {
  return (
    <p
      role="alert"
      className="rounded-xl bg-danger-weak p-3 text-label font-medium text-red-600"
    >
      {error instanceof ApiError ? error.message : FALLBACK_MESSAGE}
    </p>
  );
}
