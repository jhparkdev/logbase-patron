import { Skeleton } from "../../../shared/components/ui/Skeleton";

/** 요약 카드 순서와 이름. 미확인 건수 카드에는 전월 대비 증감이 없다. */
const SUMMARY_CARDS = [
  { label: "작업 건수", trend: true },
  { label: "API 호출 수", trend: true },
  { label: "확정 API 비용 (USD)", trend: true },
  { label: "추정 API 비용 (USD)", trend: true },
  { label: "비용 미확인 건수", trend: false },
] as const;

/** 요약 카드 5개를 불러오는 동안의 모양. 카드 이름은 먼저 보여 주고, 크기는 StatCard와 맞춘다. */
export function SummarySkeleton() {
  return (
    <div className="grid grid-cols-5 gap-4">
      {SUMMARY_CARDS.map((card) => (
        <div key={card.label} className="flex gap-4 rounded-2xl bg-white p-5">
          {/* Skeleton의 기본 모서리를 덮지 않고, 원 모양 틀로 잘라 아이콘 자리를 만든다. */}
          <span className="size-11 shrink-0 overflow-hidden rounded-full">
            <Skeleton className="size-full" />
          </span>
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <p className="text-label font-medium text-grey-600">{card.label}</p>
            <Skeleton className="h-9 w-2/3" />
            {card.trend && <Skeleton className="h-5 w-1/2" />}
          </div>
        </div>
      ))}
    </div>
  );
}
