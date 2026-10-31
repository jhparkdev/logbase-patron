import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { NoUsageResult } from "./NoUsageResult";

/** 일별 API 비용 추이. 그래프는 일별 비용 API가 생기면 그린다. */
export function CostTrendCard() {
  return (
    <SectionCard
      title="비용 추이"
      description="일별 API 비용이에요. 구독료는 날짜별로 나누지 않아 그래프에 넣지 않아요."
    >
      <NoUsageResult />
    </SectionCard>
  );
}
