import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { NoUsageResult } from "./NoUsageResult";
import { PendingTable } from "./PendingTable";

const TITLE = "상세 API 사용 이력";

/** 조회 조건에 맞는 최근 호출 20건. 고객 사용은 넣지 않고, 구분 칸에 호출 출처를 보여 준다. */
export function RecentRequestTable() {
  return (
    <SectionCard title={TITLE} description="최근 20건">
      <PendingTable
        caption={TITLE}
        columns={[
          { key: "requestedAt", header: "일시" },
          { key: "project", header: "프로젝트" },
          { key: "model", header: "모델" },
          { key: "tokens", header: "사용량 (Token)", align: "right" },
          { key: "cost", header: "비용 (USD)", align: "right" },
          { key: "origin", header: "구분" },
          { key: "status", header: "실행 상태" },
        ]}
        empty={<NoUsageResult />}
      />
    </SectionCard>
  );
}
