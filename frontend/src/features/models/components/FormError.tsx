import { ApiError } from "../../../shared/api/client";

type FormErrorProps = {
  error: Error;
  /** 서버 문구가 없는 오류(네트워크 등)에 보여 줄 일반 문구 */
  fallback: string;
};

/** 서버가 거절한 이유를 폼 위에 알림 */
export function FormError({ error, fallback }: FormErrorProps) {
  return (
    <p
      role="alert"
      className="rounded-xl bg-danger-weak p-3 text-label font-medium text-red-600"
    >
      {error instanceof ApiError ? error.message : fallback}
    </p>
  );
}
