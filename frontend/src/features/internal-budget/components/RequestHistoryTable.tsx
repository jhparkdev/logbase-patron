import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { useListSort } from "../hooks/useListSort";
import type { ListColumn, PagingControls } from "../lib/list";
import { NoUsageResult } from "./NoUsageResult";
import { PendingTable } from "./PendingTable";
import { ViewAllLink } from "./ViewAllLink";

const TITLE = "상세 API 사용 이력";

const COLUMNS: ListColumn<"requests">[] = [
  { key: "requestedAt", header: "일시" },
  { key: "project", header: "프로젝트" },
  { key: "model", header: "모델" },
  { key: "tokens", header: "사용량 (Token)", align: "right" },
  { key: "cost", header: "비용 (USD)", align: "right" },
  { key: "origin", header: "구분" },
  { key: "status", header: "실행 상태" },
];

/**
 * 조회 조건에 맞는 호출 이력. 요약 화면에서는 최근 20건(그 20건 안에서 정렬), paging이 있으면 전체보기다.
 * 고객 사용은 넣지 않고, 구분 칸에 호출 출처를 보여 준다.
 */
export function RequestHistoryTable({ paging }: { paging?: PagingControls }) {
  const sorting = useListSort("requests");
  return (
    <SectionCard
      title={TITLE}
      description={paging ? undefined : "최근 20건"}
      action={
        paging ? undefined : <ViewAllLink view="requests" title={TITLE} />
      }
    >
      <PendingTable
        caption={TITLE}
        columns={COLUMNS}
        empty={<NoUsageResult />}
        sorting={sorting}
        paging={paging}
      />
    </SectionCard>
  );
}
