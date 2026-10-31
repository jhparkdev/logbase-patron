import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { TableSkeleton } from "../../../shared/components/ui/TableSkeleton";

/** 불러오는 동안 보여 줄 회색 행 수 */
const LOADING_ROWS = 5;

/** 조회 조건에 맞는 최근 AI 호출. 실패·Timeout도 넣는다. 행은 호출 이력 API를 연결할 때 그린다. */
export function RequestTable() {
  return (
    <SectionCard title="상세 API 호출 내역" description="최근 20건">
      <TableSkeleton rows={LOADING_ROWS} />
    </SectionCard>
  );
}
