import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { Skeleton } from "../../../shared/components/ui/Skeleton";

/** 일별 작업 건수와 확정·추정 비용 추이. 그래프는 일별 추이 API를 연결할 때 그린다. */
export function UsageTrendCard() {
  return (
    <SectionCard title="사용량·비용 추이">
      <div className="px-6 pb-6">
        <Skeleton className="h-64" />
      </div>
    </SectionCard>
  );
}
