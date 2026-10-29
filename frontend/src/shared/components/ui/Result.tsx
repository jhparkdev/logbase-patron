import type { ReactNode } from "react";

type ResultProps = {
  title: string;
  description?: string;
  /** 다시 시도 버튼처럼 다음에 할 일 */
  action?: ReactNode;
};

/** 데이터 블록 자리에 결과 없음이나 조회 실패를 알린다. */
export function Result({ title, description, action }: ResultProps) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
      <p className="font-semibold">{title}</p>
      {description && (
        <p className="text-body-sm text-grey-600">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
