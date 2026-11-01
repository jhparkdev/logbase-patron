import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { TableSkeleton } from "../../../shared/components/ui/TableSkeleton";
import { ViewAllLink } from "./ViewAllLink";

const TITLE = "상세 API 호출 내역";

/** 불러오는 동안 보여 줄 회색 행 수 */
const LOADING_ROWS = 5;

/**
 * 조회 조건에 맞는 AI 호출. 실패·Timeout도 넣는다. 행은 호출 이력 API를 연결할 때 그린다.
 * 요약 화면에서는 최근 20건, 전체보기에서는 조건에 맞는 전체다.
 */
export function RequestTable({ fullView = false }: { fullView?: boolean }) {
  return (
    <SectionCard
      title={TITLE}
      description={fullView ? undefined : "최근 20건"}
      action={
        fullView ? undefined : <ViewAllLink view="requests" title={TITLE} />
      }
    >
      <TableSkeleton rows={LOADING_ROWS} />
    </SectionCard>
  );
}
