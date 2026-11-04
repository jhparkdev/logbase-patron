import { Button } from "../../../shared/components/ui/Button";

/** 조건 입력 화면 맨 아래의 실행 띠. 왜 실행할 수 없는지를 버튼 옆에 적는다. */
export function RunBar({
  summary,
  modelCount,
  reason,
  issues,
  disabled,
  submitting,
}: {
  summary: string;
  modelCount: number;
  /** 버튼이 비활성인 이유. 실행할 수 있으면 없다 */
  reason?: string;
  /** 제출한 뒤 드러난 차단 사유 */
  issues: readonly string[];
  disabled: boolean;
  submitting: boolean;
}) {
  return (
    <section
      aria-label="비교 실행"
      className="flex flex-wrap items-center gap-4 rounded-2xl border border-grey-200 bg-white px-6 py-4"
    >
      <div className="flex min-w-0 flex-1 basis-80 flex-col gap-1">
        <p className="text-body-sm">
          <span className="text-grey-600">실행 조건</span>&nbsp; 모델{" "}
          <strong className="tabular-nums">{modelCount}</strong>개 · {summary}
        </p>
        {reason && <p className="text-caption text-red-600">{reason}</p>}
        {issues.length > 0 && (
          <div role="alert" className="text-caption text-red-600">
            <ul className="list-inside list-disc">
              {issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <p className="ml-auto text-caption text-grey-600">
        실행하면 모델 호출 비용이 발생해요. 확인창에서 한 번 더 물어볼게요.
      </p>
      <Button type="submit" disabled={disabled}>
        {submitting ? "실행 요청 중" : "비교 실행"}
      </Button>
    </section>
  );
}
