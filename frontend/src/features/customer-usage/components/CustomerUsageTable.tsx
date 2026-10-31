import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { TableSkeleton } from "../../../shared/components/ui/TableSkeleton";

/** 불러오는 동안 보여 줄 회색 행 수 */
const LOADING_ROWS = 5;

/**
 * 고객·서비스별 사용량과 고객 예산 사용률. 행은 고객별 사용 현황 API를 연결할 때 그린다.
 * 예산은 월 단위라 제목 옆에 비교하는 달을 알린다.
 */
export function CustomerUsageTable({ budgetMonth }: { budgetMonth: string }) {
  return (
    <SectionCard title="고객별 사용 현황" description={`${budgetMonth} 기준`}>
      <TableSkeleton rows={LOADING_ROWS} />
    </SectionCard>
  );
}
