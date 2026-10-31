import { Skeleton } from "../../../shared/components/ui/Skeleton";

const SUMMARY_LABELS = [
  "API 확정 비용",
  "API 추정 비용",
  "월 구독료",
  "총 관리 비용 (추정 포함)",
] as const;

/** 비용 요약 카드 4개를 불러오는 동안의 모양. 카드 이름은 먼저 보여 준다. */
export function SummarySkeleton() {
  return (
    <div className="grid grid-cols-4 gap-4">
      {SUMMARY_LABELS.map((label) => (
        <div
          key={label}
          className="flex flex-col gap-2 rounded-2xl bg-white p-5"
        >
          <p className="text-label font-medium text-grey-600">{label}</p>
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      ))}
    </div>
  );
}
