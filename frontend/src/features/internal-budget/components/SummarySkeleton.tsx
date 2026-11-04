import { Skeleton } from "../../../shared/components/ui/Skeleton";
import { SUMMARY_LABELS } from "../lib/summary";

/** 비용 요약 카드 4개를 불러오는 동안의 모양. 카드 이름은 먼저 보여 준다. */
export function SummarySkeleton() {
  return (
    <div className="grid grid-cols-4 gap-4">
      {Object.values(SUMMARY_LABELS).map((label) => (
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
