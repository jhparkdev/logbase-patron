import { Result } from "../../../shared/components/ui/Result";
import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { PendingTable } from "./PendingTable";

const TITLE = "프로젝트별 예산 현황";

/** 프로젝트별 월 예산과 사용률. month는 예산을 비교하는 달("YYYY-MM")이다. */
export function ProjectBudgetTable({ month }: { month: string }) {
  return (
    <SectionCard
      title={TITLE}
      description={`${month} 기준 · 프로젝트명을 누르면 상세 내역과 예산을 볼 수 있어요.`}
    >
      <PendingTable
        caption={TITLE}
        columns={[
          { key: "project", header: "프로젝트명" },
          { key: "budget", header: "월 예산 (USD)", align: "right" },
          { key: "used", header: "사용액 (USD, 추정 포함)", align: "right" },
          { key: "usage", header: "사용률" },
          { key: "status", header: "상태" },
        ]}
        empty={
          <Result
            title="등록된 프로젝트가 없어요"
            description="프로젝트가 등록되면 여기에서 예산을 정할 수 있어요."
          />
        }
      />
    </SectionCard>
  );
}
