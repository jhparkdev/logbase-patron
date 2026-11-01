import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { TableSkeleton } from "../../../shared/components/ui/TableSkeleton";
import { ViewAllLink } from "./ViewAllLink";

const TITLE = "고객별 사용 현황";

/** 불러오는 동안 보여 줄 회색 행 수 */
const LOADING_ROWS = 5;

type CustomerUsageTableProps = {
  budgetMonth: string;
  /** 전체보기에서는 전체보기 링크를 두지 않는다. */
  fullView?: boolean;
};

/**
 * 고객·서비스별 사용량과 고객 예산 사용률. 행은 고객별 사용 현황 API를 연결할 때 그린다.
 * 예산은 월 단위라 제목 옆에 비교하는 달을 알린다.
 */
export function CustomerUsageTable({
  budgetMonth,
  fullView = false,
}: CustomerUsageTableProps) {
  return (
    <SectionCard
      title={TITLE}
      description={`${budgetMonth} 기준`}
      action={
        fullView ? undefined : <ViewAllLink view="customers" title={TITLE} />
      }
    >
      <TableSkeleton rows={LOADING_ROWS} />
    </SectionCard>
  );
}
